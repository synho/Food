"""
Parallel fetch workers for NCBI PMC — safe, rate-limited, adaptive.

NCBI rate limits:
  Without API key : ≤ 3 req/sec  (we target 2.5 to be safe)
  With API key    : ≤ 10 req/sec  (we target 7 to leave headroom)

Safety mechanisms:
  TokenBucket     — per-worker token bucket enforces per-second request cap
  CircuitBreaker  — shared across workers; pauses all workers on surge of 429s
  Adaptive delay  — workers slow down when 429s appear, speed up when clear

Usage:
    from fetch_workers import parallel_search, parallel_fetch_articles

    # Run 8 queries at once, get {query_label: [pmcids]}
    results = parallel_search(queries_dict, max_workers=3)

    # Download 40 papers at once with rate limiting
    fetched = parallel_fetch_articles(pmcids, raw_dir, max_workers=3)
"""
from __future__ import annotations

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import deque
from pathlib import Path

import requests


# ── NCBI configuration ────────────────────────────────────────────────────────

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

_TOOL  = "food-health-navigator"
_EMAIL = "healthnav-pipeline@local"  # identifies bot to NCBI — change to real email if desired

def _get_api_key() -> str:
    return os.getenv("NCBI_API_KEY", "").strip()

def _worker_config() -> dict:
    """Return safe worker limits based on API key availability."""
    key = _get_api_key()
    if key:
        return {"max_workers": 5, "target_rps": 7.0, "min_delay": 0.15, "api_key": key}
    return     {"max_workers": 3, "target_rps": 2.5, "min_delay": 0.40, "api_key": ""}


# ── Token bucket rate limiter ─────────────────────────────────────────────────

class TokenBucket:
    """Thread-safe token bucket. Shared across all workers for a single rate cap."""

    def __init__(self, rate: float = 2.5):
        """rate: max requests per second."""
        self._rate = rate
        self._tokens = rate
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """Block until a token is available."""
        while True:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self._last
                self._tokens = min(self._rate, self._tokens + elapsed * self._rate)
                self._last = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                wait = (1.0 - self._tokens) / self._rate
            time.sleep(wait)


# ── Circuit breaker ───────────────────────────────────────────────────────────

class CircuitBreaker:
    """
    Shared across workers. Opens (pauses all) when consecutive 429s exceed threshold.
    Half-opens after cooldown, resets on success.
    """
    THRESHOLD  = 4    # consecutive failures before opening
    COOLDOWN   = 70   # seconds to wait when open

    def __init__(self):
        self._failures = 0
        self._open_until = 0.0
        self._lock = threading.Lock()

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self.THRESHOLD:
                self._open_until = time.monotonic() + self.COOLDOWN
                print(f"  ⚠ Circuit breaker OPEN — pausing all workers for {self.COOLDOWN}s "
                      f"(consecutive 429s: {self._failures})")

    def wait_if_open(self) -> None:
        """Block until circuit is closed."""
        while True:
            with self._lock:
                remaining = self._open_until - time.monotonic()
                if remaining <= 0:
                    return
            print(f"  ⏸ Circuit breaker: waiting {remaining:.0f}s before retrying…")
            time.sleep(min(remaining, 5))


# ── Shared instances (module-level singletons) ────────────────────────────────

_cfg     = _worker_config()
_bucket  = TokenBucket(rate=_cfg["target_rps"])
_breaker = CircuitBreaker()


# ── Single-article fetch (rate-limited, retriable) ───────────────────────────

def _fetch_one(pmcid: str, min_delay: float, api_key: str, max_retries: int = 3) -> dict | None:
    """Fetch one article from NCBI efetch with rate limiting and retry."""
    import xml.etree.ElementTree as ET

    params: dict = {"db": "pmc", "id": pmcid, "retmode": "xml",
                    "tool": _TOOL, "email": _EMAIL}
    if api_key:
        params["api_key"] = api_key

    for attempt in range(max_retries):
        _breaker.wait_if_open()
        _bucket.acquire()

        try:
            resp = requests.get(EFETCH_URL, params=params, timeout=30)
        except requests.exceptions.RequestException as e:
            print(f"  PMC{pmcid}: network error ({e}) — retry {attempt+1}/{max_retries}")
            time.sleep(2 ** attempt)
            continue

        if resp.status_code == 429:
            _breaker.record_failure()
            wait = min_delay * (4 ** attempt)   # 0.4s, 1.6s, 6.4s
            print(f"  PMC{pmcid}: 429 — backing off {wait:.1f}s (attempt {attempt+1})")
            time.sleep(wait)
            continue

        if resp.status_code != 200:
            print(f"  PMC{pmcid}: HTTP {resp.status_code} — skipping")
            return None

        _breaker.record_success()
        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError as e:
            print(f"  PMC{pmcid}: XML parse error ({e})")
            return None

        title_e  = root.find(".//article-title")
        abstract_e = root.find(".//abstract")
        journal_e = root.find(".//journal-title")
        pub_date_e = root.find(".//pub-date[@date-type='pub']") or root.find(".//pub-date")
        body_e   = root.find(".//body")

        pub_date = "Unknown"
        if pub_date_e is not None:
            year  = pub_date_e.findtext("year", "")
            month = pub_date_e.findtext("month", "01")
            day   = pub_date_e.findtext("day",   "01")
            if year:
                pub_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"

        body_text = ""
        if body_e is not None:
            body_text = "".join(body_e.itertext()).strip()

        return {
            "pmcid":             f"PMC{pmcid}",
            "title":             title_e.text if title_e is not None else "No Title",
            "journal":           journal_e.text if journal_e is not None else "Unknown",
            "date":              pub_date,
            "abstract":          "".join(abstract_e.itertext()).strip() if abstract_e is not None else "",
            "full_text_preview": (body_text[:1000] + "…") if len(body_text) > 1000 else body_text,
        }

    print(f"  PMC{pmcid}: max retries exceeded — skipping")
    return None


# ── Single-query search (rate-limited, retriable) ────────────────────────────

def _search_one(query: str, max_results: int, api_key: str, min_delay: float,
                max_retries: int = 3) -> list[str]:
    """Search PMC with one query, return list of PMCIDs."""
    params: dict = {"db": "pmc", "term": query, "retmode": "json",
                    "retmax": max_results, "sort": "date",
                    "tool": _TOOL, "email": _EMAIL}
    if api_key:
        params["api_key"] = api_key

    for attempt in range(max_retries):
        _breaker.wait_if_open()
        _bucket.acquire()

        try:
            resp = requests.get(ESEARCH_URL, params=params, timeout=30)
        except requests.exceptions.RequestException as e:
            print(f"  Search error ({e}) — retry {attempt+1}/{max_retries}")
            time.sleep(2 ** attempt)
            continue

        if resp.status_code == 429:
            _breaker.record_failure()
            wait = min_delay * (3 ** attempt)
            print(f"  Search 429 — backing off {wait:.1f}s (attempt {attempt+1})")
            time.sleep(wait)
            continue

        if resp.status_code != 200:
            print(f"  Search HTTP {resp.status_code} — skipping")
            return []

        _breaker.record_success()
        try:
            data = resp.json()
            return data.get("esearchresult", {}).get("idlist", [])
        except Exception as e:
            print(f"  Search JSON error: {e}")
            return []

    return []


# ── Public API ────────────────────────────────────────────────────────────────

def parallel_search(
    queries: dict[str, str],   # {label: query_string}
    max_results_per_query: int = 5,
    max_workers: int | None = None,
) -> dict[str, list[str]]:
    """
    Run multiple PMC search queries concurrently.

    Args:
        queries: {label: query_string} dict
        max_results_per_query: max PMCIDs per query
        max_workers: override default (auto from API key availability)

    Returns:
        {label: [pmcid, ...]}
    """
    cfg = _worker_config()
    workers = max_workers or cfg["max_workers"]
    api_key = cfg["api_key"]
    min_delay = cfg["min_delay"]

    results: dict[str, list[str]] = {}

    if not queries:
        return results

    print(f"  Parallel search: {len(queries)} queries × {workers} workers"
          + (" (with API key)" if api_key else " (no API key — 3 req/s)"))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_label = {
            pool.submit(_search_one, query, max_results_per_query, api_key, min_delay): label
            for label, query in queries.items()
        }
        for future in as_completed(future_to_label):
            label = future_to_label[future]
            try:
                pmcids = future.result()
                results[label] = pmcids
                print(f"  [{label}] → {len(pmcids)} results")
            except Exception as e:
                print(f"  [{label}] error: {e}")
                results[label] = []

    return results


def parallel_fetch_articles(
    pmcids: list[str],
    raw_dir: str,
    already_fetched: set[str] | None = None,
    max_workers: int | None = None,
) -> list[str]:
    """
    Download multiple PMC articles concurrently.

    Args:
        pmcids:          list of numeric PMCIDs to download
        raw_dir:         directory to write JSON files
        already_fetched: set of PMCIDs already on disk (skipped)
        max_workers:     override default

    Returns:
        list of successfully downloaded PMCIDs
    """
    cfg = _worker_config()
    workers = max_workers or cfg["max_workers"]
    api_key = cfg["api_key"]
    min_delay = cfg["min_delay"]

    already = already_fetched or set()
    new_pmcids = [p for p in pmcids if p not in already]

    if not new_pmcids:
        return []

    os.makedirs(raw_dir, exist_ok=True)
    fetched: list[str] = []
    lock = threading.Lock()

    print(f"  Parallel download: {len(new_pmcids)} papers × {workers} workers"
          + (" (API key)" if api_key else " (no key)"))

    def _download(pmcid: str) -> str | None:
        article = _fetch_one(pmcid, min_delay, api_key)
        if article:
            out = os.path.join(raw_dir, f"PMC{pmcid}.json")
            with open(out, "w", encoding="utf-8") as f:
                json.dump(article, f, indent=4)
            with lock:
                fetched.append(pmcid)
                already.add(pmcid)
            return pmcid
        return None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_download, p): p for p in new_pmcids}
        done = 0
        for future in as_completed(futures):
            done += 1
            result = future.result()
            if result:
                print(f"  [{done}/{len(new_pmcids)}] PMC{result} ✓")
            else:
                pmcid = futures[future]
                print(f"  [{done}/{len(new_pmcids)}] PMC{pmcid} ✗ (skipped)")

    return fetched
