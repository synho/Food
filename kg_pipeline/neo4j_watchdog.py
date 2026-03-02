#!/usr/bin/env python3
"""
neo4j_watchdog.py — Monitor Neo4j container memory; restart and resume on OOM.

Polls the Neo4j Docker container's memory usage every INTERVAL seconds.
If memory exceeds MEMORY_LIMIT_MB, it:
  1. Restarts the container.
  2. Waits for Neo4j to accept connections (bolt).
  3. Resumes the last pipeline batch using the most recent manifest's RUN_ID.

Usage:
    cd kg_pipeline && source venv/bin/activate
    python neo4j_watchdog.py                       # defaults: 2048 MB, 30s interval
    python neo4j_watchdog.py --limit 1500          # custom memory limit in MB
    python neo4j_watchdog.py --interval 60         # check every 60 seconds
    python neo4j_watchdog.py --container my_neo4j  # custom container name
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT        = Path(__file__).resolve().parent
SRC         = ROOT / "src"
LOGS_DIR    = ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)
LOG_FILE    = LOGS_DIR / "overnight_report.log"

NEO4J_CONTAINER = "health_navigation_kg"
NEO4J_URI       = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER      = os.getenv("NEO4J_USER",     "foodnot4self")
NEO4J_PASSWORD  = os.getenv("NEO4J_PASSWORD", "foodnot4self")

BOLT_WAIT_SEC   = 120   # max seconds to wait for Neo4j after restart
BOLT_POLL_SEC   = 5     # poll interval while waiting


# ── Logging ───────────────────────────────────────────────────────────────────

def _log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts}  [watchdog] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


# ── Docker helpers ────────────────────────────────────────────────────────────

def _container_memory_mb(container: str) -> float | None:
    """
    Return current memory usage of the container in MB, or None if unavailable.
    Uses `docker stats --no-stream --format '{{.MemUsage}}'`.
    Example output: "512MiB / 2GiB"
    """
    try:
        result = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", container],
            capture_output=True, text=True, timeout=10,
        )
        raw = result.stdout.strip().split("/")[0].strip()   # e.g. "512MiB"
        if not raw:
            return None
        val = float("".join(c for c in raw if c.isdigit() or c == "."))
        unit = raw.lstrip("0123456789.").upper()
        multipliers = {"B": 1/1024/1024, "KIB": 1/1024, "MIB": 1, "GIB": 1024,
                       "KB": 1/1024, "MB": 1, "GB": 1024}
        return val * multipliers.get(unit, 1)
    except Exception:
        return None


def _restart_container(container: str) -> bool:
    """Restart the Docker container. Returns True on success."""
    _log(f"Restarting container: {container}")
    result = subprocess.run(
        ["docker", "restart", container],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        _log(f"ERROR restarting container: {result.stderr.strip()}")
        return False
    _log(f"Container {container} restarted.")
    return True


# ── Neo4j readiness check ─────────────────────────────────────────────────────

def _wait_for_neo4j(timeout: int = BOLT_WAIT_SEC) -> bool:
    """Poll until Neo4j accepts a bolt connection. Returns True if ready."""
    sys.path.insert(0, str(SRC))
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    try:
        from neo4j import GraphDatabase  # type: ignore
    except ImportError:
        _log("neo4j driver not available — skipping readiness check")
        return True

    _log(f"Waiting for Neo4j to be ready (up to {timeout}s)…")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
            with driver.session() as s:
                s.run("RETURN 1").single()
            driver.close()
            _log("Neo4j is ready.")
            return True
        except Exception:
            time.sleep(BOLT_POLL_SEC)

    _log(f"ERROR: Neo4j did not become ready within {timeout}s.")
    return False


# ── Manifest helpers ──────────────────────────────────────────────────────────

def _latest_run_id() -> str | None:
    """
    Return the RUN_ID from the most recent ingest manifest with status 'ok',
    falling back to the most recent extract manifest.
    """
    manifests_dir = ROOT / "data" / "manifests"
    if not manifests_dir.exists():
        return None

    candidates: list[tuple[float, str, Path]] = []
    for p in manifests_dir.glob("*.json"):
        try:
            data = json.loads(p.read_text())
            agent  = data.get("_agent", "")
            run_id = data.get("_run_id", "")
            status = data.get("status", "")
            if agent in ("ingest", "extract") and run_id:
                # Prefer ingest ok > extract ok > any
                priority = 0 if (agent == "ingest" and status == "ok") else \
                           1 if (agent == "extract" and status == "ok") else 2
                candidates.append((priority, run_id, p))
        except Exception:
            continue

    if not candidates:
        return None
    candidates.sort(key=lambda x: (x[0], x[1]))
    return candidates[0][1]


# ── Resume pipeline ───────────────────────────────────────────────────────────

def _resume_last_batch(run_id: str) -> None:
    """Re-run the ingest step for the given RUN_ID."""
    _log(f"Resuming ingest for RUN_ID={run_id}")
    env = os.environ.copy()
    env["RUN_ID"] = run_id

    venv_python = ROOT / "venv" / "bin" / "python"
    python_bin  = str(venv_python) if venv_python.exists() else sys.executable

    result = subprocess.run(
        [python_bin, "run_pipeline.py", "--steps", "ingest"],
        cwd=str(ROOT), env=env,
        capture_output=True, text=True, timeout=300,
    )
    if result.returncode == 0:
        _log(f"Ingest resumed and completed for RUN_ID={run_id}")
    else:
        _log(f"ERROR: ingest resume failed (exit {result.returncode})")
        last_line = (result.stdout + result.stderr).strip().splitlines()[-1:][0] if \
                    (result.stdout + result.stderr).strip() else "(no output)"
        _log(f"       {last_line}")


# ── Main watchdog loop ────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Neo4j memory watchdog — restart and resume on OOM")
    parser.add_argument("--limit",     type=int, default=2048,
                        help="Memory limit in MB before restart (default: 2048)")
    parser.add_argument("--interval",  type=int, default=30,
                        help="Check interval in seconds (default: 30)")
    parser.add_argument("--container", type=str, default=NEO4J_CONTAINER,
                        help=f"Docker container name (default: {NEO4J_CONTAINER})")
    args = parser.parse_args()

    _log(f"Watchdog started — container={args.container}  limit={args.limit}MB  interval={args.interval}s")

    restart_count = 0

    while True:
        mem_mb = _container_memory_mb(args.container)

        if mem_mb is None:
            _log(f"WARNING: could not read memory for '{args.container}' (container down or docker unavailable)")
        else:
            if mem_mb >= args.limit:
                _log(f"ALERT: memory {mem_mb:.0f}MB >= limit {args.limit}MB — triggering restart")
                if _restart_container(args.container):
                    restart_count += 1
                    if _wait_for_neo4j():
                        run_id = _latest_run_id()
                        if run_id:
                            _resume_last_batch(run_id)
                        else:
                            _log("No recent manifest found — skipping resume")
                    else:
                        _log("Neo4j did not recover — manual intervention required")
            else:
                print(
                    f"{datetime.now().strftime('%H:%M:%S')}  "
                    f"[watchdog] {args.container}: {mem_mb:.0f}MB / {args.limit}MB  "
                    f"(restarts: {restart_count})"
                )

        time.sleep(args.interval)


if __name__ == "__main__":
    sys.path.insert(0, str(SRC))
    main()
