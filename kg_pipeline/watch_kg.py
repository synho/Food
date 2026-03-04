#!/usr/bin/env python3
"""
watch_kg.py — Continuous 10-minute KG gap-filling loop.

Each cycle runs two complementary strategies:
  1. Broad sweep   — full pipeline (26 journals × 2 years) catches newly published papers
  2. Gap-targeted  — smart_fetch --gap-only fires entity-level PMC queries for
                     diseases/nutrients/biomarkers with missing relationships

Saturation handling:
  • If 5 consecutive cycles produce 0 new papers via smart_fetch, the low-yield
    query cache is reset so deprioritized clusters get another chance.

Usage:
    cd kg_pipeline && source venv/bin/activate
    python watch_kg.py                  # run forever  (Ctrl+C to stop)
    python watch_kg.py --once           # one cycle then exit
    python watch_kg.py --interval 5     # custom interval in minutes
    python watch_kg.py --gap-only       # skip broad sweep, gap queries only
"""
from __future__ import annotations

import argparse
import os
import re
import signal
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).resolve().parent   # kg_pipeline/
SRC         = ROOT / "src"
VENV_PYTHON = ROOT / "venv" / "bin" / "python"
DATA_ROOT   = ROOT.parent / "data"
DB_PATH     = DATA_ROOT / "health_map.db"
LOGS_DIR    = ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)

_stop = False


def _handle_signal(sig, frame):
    global _stop
    print("\n[watch_kg] Received stop signal — finishing current cycle…")
    _stop = True


# ── Subprocess helper ─────────────────────────────────────────────────────────

def _run(cmd: list[str], timeout: int = 900) -> tuple[int, str]:
    """Run a subprocess in kg_pipeline/, return (returncode, combined_output).

    Uses a process group so timeout kills the entire tree (not just the
    direct child), preventing orphaned grandchild processes.
    """
    try:
        proc = subprocess.Popen(
            cmd, cwd=str(ROOT),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, start_new_session=True,
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            return proc.returncode, (stdout + stderr).strip()
        except subprocess.TimeoutExpired:
            # Kill the entire process group
            import os as _os
            try:
                _os.killpg(proc.pid, signal.SIGTERM)
            except OSError:
                pass
            proc.kill()
            proc.wait()
            return -1, "timeout"
    except Exception as e:
        return -1, str(e)


# ── Output parsers ────────────────────────────────────────────────────────────

def _parse_new_papers_fetch(output: str) -> int:
    """Parse 'fetching X new' or 'downloaded and saved X' from fetch_papers output."""
    for line in output.splitlines():
        m = re.search(r"fetching\s+(\d+)\s+new", line, re.I)
        if m:
            return int(m.group(1))
        m = re.search(r"downloaded and saved\s+(\d+)", line, re.I)
        if m:
            return int(m.group(1))
    return 0


def _parse_new_papers_smart(output: str) -> int:
    """Parse 'Total unique new PMCIDs: X' from smart_fetch output."""
    for line in output.splitlines():
        m = re.search(r"Total unique new PMCIDs:\s*(\d+)", line)
        if m:
            return int(m.group(1))
    return 0


def _parse_valid_triples(output: str) -> int:
    """Parse 'Consolidated X valid triples' from extract output."""
    for line in output.splitlines():
        m = re.search(r"Consolidated\s+(\d+)\s+valid triples", line)
        if m:
            return int(m.group(1))
    return 0


def _tail_lines(output: str, n: int = 4) -> list[str]:
    """Return last N non-empty lines."""
    lines = [l.strip() for l in output.splitlines() if l.strip()]
    return lines[-n:] if lines else []


# ── Neo4j stats (direct driver query) ────────────────────────────────────────

def _kg_counts() -> dict:
    """Return {nodes, rels} from Neo4j, or {error} if unreachable."""
    try:
        sys.path.insert(0, str(SRC))
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
        from neo4j import GraphDatabase  # type: ignore
        uri  = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER",     "foodnot4self")
        pw   = os.getenv("NEO4J_PASSWORD", "foodnot4self")
        driver = GraphDatabase.driver(uri, auth=(user, pw))
        with driver.session() as s:
            nodes = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
            rels  = s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
        driver.close()
        return {"nodes": nodes, "rels": rels}
    except Exception as e:
        return {"error": str(e)}


# ── Low-yield cache reset ─────────────────────────────────────────────────────

def _reset_low_yield_cache() -> int:
    """
    Delete all rows from fetch_yield so smart_fetch will retry every cluster.
    Returns number of rows deleted.
    """
    try:
        if not DB_PATH.exists():
            return 0
        conn = sqlite3.connect(str(DB_PATH))
        deleted = conn.execute("DELETE FROM fetch_yield").rowcount
        conn.commit()
        conn.close()
        return deleted
    except Exception:
        return 0


# ── Gap summary ───────────────────────────────────────────────────────────────

def _gap_summary() -> str:
    """Return a one-line gap summary from kg_gap_analyzer."""
    try:
        sys.path.insert(0, str(SRC))
        from kg_gap_analyzer import analyze_kg_gaps
        g = analyze_kg_gaps()
        counts = {
            "cond_no_food":   len(g.conditions_no_food_recs),
            "disease_no_bmk": len(g.diseases_no_biomarker),
            "nutrient_no_src": len(g.nutrients_no_food),
            "symptom_no_sig": len(g.symptoms_no_early_signal),
        }
        total = sum(counts.values())
        top = sorted(counts.items(), key=lambda x: -x[1])[:3]
        parts = [f"{k}={v}" for k, v in top]
        return f"{total} gap items  ({', '.join(parts)})"
    except Exception as e:
        return f"gap analysis error: {e}"


# ── Overnight report logging ──────────────────────────────────────────────────

def _append_log(log_path: Path, line: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path, "a") as f:
        f.write(f"{ts}  {line}\n")


def _log_cycle_summary(
    log_path: Path,
    cycle: int,
    broad_new: int,
    smart_new: int,
    counts_before: dict,
    counts_after: dict,
) -> None:
    dn = dr = 0
    if "error" not in counts_before and "error" not in counts_after:
        dn = counts_after.get("nodes", 0) - counts_before.get("nodes", 0)
        dr = counts_after.get("rels",  0) - counts_before.get("rels",  0)
    total_nodes = counts_after.get("nodes", "?")
    total_rels  = counts_after.get("rels",  "?")
    _append_log(
        log_path,
        f"[CYCLE {cycle:>4}]  papers +{broad_new + smart_new}"
        f"  nodes +{dn}  rels +{dr}"
        f"  total={total_nodes} nodes / {total_rels} rels",
    )


def _log_hourly_snapshot(log_path: Path) -> None:
    counts = _kg_counts()
    if "error" in counts:
        _append_log(log_path, f"[HOURLY SNAPSHOT]  Neo4j unreachable: {counts['error']}")
    else:
        _append_log(
            log_path,
            f"[HOURLY SNAPSHOT]  {counts['nodes']:,} nodes  {counts['rels']:,} rels",
        )


# ── Single cycle ──────────────────────────────────────────────────────────────

def run_cycle(
    cycle: int,
    empty_smart_streak: int,
    gap_only: bool,
) -> tuple[int, int, dict, dict]:
    """
    Execute one fill cycle.

    Returns:
        (broad_new_papers, smart_new_papers)
    """
    ts = datetime.now().strftime("%H:%M:%S")
    bar = "─" * 58
    print(f"\n{bar}")
    print(f"  Cycle {cycle}  ·  {ts}")
    print(bar)

    counts_before = _kg_counts()
    if "error" not in counts_before:
        print(f"  KG now  : {counts_before['nodes']:,} nodes  ·  {counts_before['rels']:,} rels")
    print(f"  Gaps    : {_gap_summary()}")

    # ── Reset low-yield cache every 5 consecutive empty smart-fetch cycles ──
    if empty_smart_streak > 0 and empty_smart_streak % 5 == 0:
        deleted = _reset_low_yield_cache()
        print(f"  [reset] Cleared {deleted} low-yield records → all clusters will retry")

    broad_new = 0

    # ── Phase 1: Broad journal sweep ──────────────────────────────────────────
    if not gap_only:
        print(f"\n  [1/2] Broad sweep  (88 journals, batched)…")
        code, out = _run(
            [str(VENV_PYTHON), "run_pipeline.py"],
            timeout=3600,
        )
        broad_new = _parse_new_papers_fetch(out)
        triples    = _parse_valid_triples(out)

        if broad_new > 0:
            print(f"       +{broad_new} papers fetched  →  {triples:,} valid triples now")
        else:
            print(f"       No new papers  (corpus current)")

        if code != 0:
            for line in _tail_lines(out, 2):
                print(f"       {line}")

    # ── Phase 2: Smart gap-targeted fetch ─────────────────────────────────────
    print(f"\n  [2/2] Smart gap fetch  (entity-targeted PMC queries)…")
    code, out = _run(
        [str(VENV_PYTHON), "src/smart_fetch.py", "--gap-only"],
        timeout=600,
    )
    smart_new = _parse_new_papers_smart(out)

    if smart_new > 0:
        print(f"       +{smart_new} papers fetched via gap queries → extracting…")
        # Extract only (pipeline already ingested broad papers above)
        _, eout = _run([str(VENV_PYTHON), "src/extract_triples.py"], timeout=1200)
        triples = _parse_valid_triples(eout)
        _, iout = _run([str(VENV_PYTHON), "src/ingest_to_neo4j.py"], timeout=120)
        for line in _tail_lines(iout, 1):
            print(f"       {line}")
        print(f"       {triples:,} valid triples in master graph")
    else:
        # Show the last summary line from smart_fetch
        for line in _tail_lines(out, 1):
            print(f"       {line}")

    # ── KG delta ──────────────────────────────────────────────────────────────
    total_new    = broad_new + smart_new
    counts_after = counts_before  # default: nothing changed
    if total_new > 0:
        counts_after = _kg_counts()
        if "error" not in counts_after and "error" not in counts_before:
            dn = counts_after["nodes"] - counts_before["nodes"]
            dr = counts_after["rels"]  - counts_before["rels"]
            print(
                f"\n  KG delta: +{dn} nodes  +{dr} rels  →  "
                f"{counts_after['nodes']:,} nodes  ·  {counts_after['rels']:,} rels"
            )

    return broad_new, smart_new, counts_before, counts_after


# ── Main loop ─────────────────────────────────────────────────────────────────

def main():
    global _stop

    parser = argparse.ArgumentParser(
        description="Continuous KG gap-filling loop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--once",      action="store_true",
                        help="Run one cycle then exit")
    parser.add_argument("--interval",  type=int, default=10,
                        help="Minutes between cycles (default: 10)")
    parser.add_argument("--gap-only",  action="store_true",
                        help="Skip broad sweep; run smart gap-fetch only")
    parser.add_argument("--overnight", action="store_true",
                        help="Overnight mode: set interval=60m and enable report log")
    parser.add_argument("--log-file",  type=str,
                        default=str(LOGS_DIR / "overnight_report.log"),
                        help="Path for cycle/hourly summary log (default: logs/overnight_report.log)")
    args = parser.parse_args()

    if args.overnight:
        args.interval = 60

    if not VENV_PYTHON.exists():
        print(f"[watch_kg] ERROR: venv not found at {VENV_PYTHON}")
        print("           Run: cd kg_pipeline && python -m venv venv && pip install -r requirements.txt")
        sys.exit(1)

    signal.signal(signal.SIGINT,  _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    log_path           = Path(args.log_file)
    interval_sec       = args.interval * 60
    cycle              = 1
    empty_smart_streak = 0
    last_hourly        = datetime.now()

    print(f"[watch_kg] Starting — interval={args.interval}m  gap-only={args.gap_only}  Ctrl+C to stop")
    print(f"[watch_kg] Venv     : {VENV_PYTHON}")
    print(f"[watch_kg] DB       : {DB_PATH}")
    print(f"[watch_kg] Log      : {log_path}")
    _append_log(log_path, f"[START] watch_kg started  interval={args.interval}m  gap-only={args.gap_only}")

    while not _stop:
        broad_new, smart_new, counts_before, counts_after = run_cycle(
            cycle, empty_smart_streak, args.gap_only
        )

        # Per-cycle summary to log
        _log_cycle_summary(log_path, cycle, broad_new, smart_new, counts_before, counts_after)

        # Hourly snapshot at wall-clock hour boundary
        now = datetime.now()
        if (now - last_hourly).total_seconds() >= 3600:
            _log_hourly_snapshot(log_path)
            last_hourly = now

        if smart_new == 0:
            empty_smart_streak += 1
        else:
            empty_smart_streak = 0

        cycle += 1

        if args.once or _stop:
            break

        next_run = datetime.now() + timedelta(seconds=interval_sec)
        print(
            f"\n  Next run at {next_run.strftime('%H:%M:%S')}"
            f"  (in {args.interval}m)"
            f"  ·  smart-fetch empty streak: {empty_smart_streak}"
        )
        # Sleep in 5-second ticks so Ctrl+C is responsive
        for _ in range(interval_sec // 5):
            if _stop:
                break
            time.sleep(5)

    _append_log(log_path, f"[STOP]  watch_kg stopped after {cycle - 1} cycle(s)")
    print("\n[watch_kg] Stopped.")


if __name__ == "__main__":
    sys.path.insert(0, str(SRC))
    main()
