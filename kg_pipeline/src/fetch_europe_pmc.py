"""
fetch_europe_pmc.py — Europe PMC data source.

Fetches open-access papers from the Europe PMC REST API, which has broader coverage
than NCBI PMC (especially European journals, preprints, grey literature).
Saves in the same format as fetch_papers.py so the existing extract/ingest pipeline
can process them transparently.

Usage:
    python src/fetch_europe_pmc.py
    python src/fetch_europe_pmc.py --days-back 3650 --max-results 1000
    python src/fetch_europe_pmc.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config_loader import get_fetch_config, get_paths_config

EPMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


# ── Query builder ─────────────────────────────────────────────────────────────

def _build_query(journals: list[str], start_date: str, end_date: str,
                 keywords: list[str] | None = None) -> str:
    """Build Europe PMC query string."""
    j_parts = " OR ".join(f'JOURNAL:"{j}"' for j in journals)
    q = f"({j_parts}) AND FIRST_PDATE:[{start_date} TO {end_date}] AND OPEN_ACCESS:y"
    if keywords:
        kw_parts = " OR ".join(f'"{k}"' for k in keywords if k.strip())
        if kw_parts:
            q = f"({q}) AND ({kw_parts})"
    return q


# ── Fetch from API ────────────────────────────────────────────────────────────

def _fetch_page(query: str, cursor: str, page_size: int) -> tuple[list[dict], str | None]:
    """Fetch one page from Europe PMC. Returns (results, next_cursor)."""
    params = {
        "query": query,
        "resultType": "core",
        "format": "json",
        "pageSize": page_size,
        "cursorMark": cursor,
    }
    for attempt in range(3):
        try:
            r = requests.get(EPMC_SEARCH, params=params, timeout=30)
            if r.status_code == 429:
                wait = 10 * (2 ** attempt)
                print(f"  Europe PMC rate limit. Waiting {wait}s...")
                time.sleep(wait)
                continue
            r.raise_for_status()
            data = r.json()
            results = data.get("resultList", {}).get("result", [])
            next_cursor = data.get("nextCursorMark")
            return results, next_cursor
        except requests.exceptions.Timeout:
            print(f"  Timeout on attempt {attempt + 1}/3")
            time.sleep(5)
        except Exception as e:
            print(f"  Europe PMC error: {e}")
            return [], None
    return [], None


def fetch_epmc(query: str, max_results: int, delay: float = 0.5) -> list[dict]:
    """Fetch up to max_results papers from Europe PMC with cursor pagination."""
    papers: list[dict] = []
    cursor = "*"
    page_size = min(100, max_results)

    while len(papers) < max_results:
        results, next_cursor = _fetch_page(query, cursor, page_size)
        if not results:
            break
        papers.extend(results)
        if not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor
        time.sleep(delay)

    return papers[:max_results]


# ── Convert to standard paper format ─────────────────────────────────────────

def _to_paper(result: dict) -> dict | None:
    """Convert Europe PMC result to the raw_papers JSON format."""
    # Require a PMC ID (open-access full text)
    pmcid_raw = result.get("pmcid", "") or result.get("id", "")
    if not pmcid_raw or not str(pmcid_raw).startswith("PMC"):
        return None
    pmcid = str(pmcid_raw).replace("PMC", "").strip()
    if not pmcid:
        return None

    title    = (result.get("title")        or "").strip()
    abstract = (result.get("abstractText") or "").strip()
    journal  = (result.get("journalTitle") or "").strip()
    pub_date = (result.get("firstPublicationDate") or "").strip()

    if not abstract and not title:
        return None

    return {
        "pmcid":             pmcid,
        "title":             title,
        "abstract":          abstract,
        "full_text_preview": "",
        "body":              "",
        "journal":           journal,
        "date":              pub_date,
        "source_type":       "PMC",          # same ingest path as NCBI papers
        "source":            "europepmc",
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def run_fetch(days_back: int | None = None,
              max_results: int | None = None,
              dry_run: bool = False) -> int:
    """Fetch Europe PMC papers. Returns count of new papers saved."""
    fetch_cfg = get_fetch_config()
    paths     = get_paths_config()

    days_back   = days_back   or fetch_cfg.get("days_back",   3650)
    max_results = max_results or fetch_cfg.get("max_results",  500)
    journals    = fetch_cfg.get("journals", [])
    aging_kw    = fetch_cfg.get("aging_keywords", [])
    raw_dir     = paths["raw_papers"]
    os.makedirs(raw_dir, exist_ok=True)

    end_dt   = datetime.now()
    start_dt = end_dt - timedelta(days=days_back)
    start_s  = start_dt.strftime("%Y-%m-%d")
    end_s    = end_dt.strftime("%Y-%m-%d")

    print(f"[europe_pmc] {len(journals)} journals × {days_back} days  ({start_s} → {end_s})")

    # Phase 1: broad journal sweep
    q1 = _build_query(journals, start_s, end_s)
    print(f"[europe_pmc] Phase 1 — broad sweep (up to {max_results})…")
    results = fetch_epmc(q1, max_results)
    print(f"[europe_pmc]   found {len(results)} results")

    # Phase 2: aging/longevity keywords (merged)
    if aging_kw:
        q2 = _build_query(journals, start_s, end_s, aging_kw)
        print(f"[europe_pmc] Phase 2 — longevity keywords (up to {max_results})…")
        r2 = fetch_epmc(q2, max_results)
        print(f"[europe_pmc]   found {len(r2)} results")
        # Merge unique by pmcid
        seen = {(r.get("pmcid") or r.get("id")) for r in results}
        for r in r2:
            key = r.get("pmcid") or r.get("id")
            if key not in seen:
                results.append(r)
                seen.add(key)

    print(f"[europe_pmc] {len(results)} unique results total")

    if dry_run:
        print("[europe_pmc] Dry run — not saving.")
        return 0

    saved = skipped = bad = 0
    for result in results:
        paper = _to_paper(result)
        if not paper:
            bad += 1
            continue
        out = os.path.join(raw_dir, f"PMC{paper['pmcid']}.json")
        if os.path.exists(out):
            skipped += 1
            continue
        with open(out, "w", encoding="utf-8") as f:
            json.dump(paper, f, indent=2, ensure_ascii=False)
        saved += 1

    print(f"[europe_pmc] +{saved} new  ·  {skipped} existing  ·  {bad} no-PMC-ID skipped")
    return saved


def main():
    parser = argparse.ArgumentParser(description="Fetch papers from Europe PMC")
    parser.add_argument("--days-back",   type=int,  default=None)
    parser.add_argument("--max-results", type=int,  default=None)
    parser.add_argument("--dry-run",     action="store_true")
    args = parser.parse_args()
    run_fetch(days_back=args.days_back, max_results=args.max_results, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
