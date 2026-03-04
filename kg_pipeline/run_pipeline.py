#!/usr/bin/env python3
"""
Run the full KG pipeline in cascade: each specialized agent runs in order,
writes its manifest; the next agent reads the previous manifest and consumes its output.
RUN_ID ties all artifacts for this run. Set RUN_ID in env to reuse (e.g. re-run only ingest).
Execute from kg_pipeline: python run_pipeline.py [--steps fetch,extract,ingest] [--config config.yaml]
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

KG_ROOT = Path(__file__).resolve().parent
SRC = KG_ROOT / "src"


def run(script: str, description: str, env: dict) -> bool:
    print(f"\n--- {description} ---\n")
    result = subprocess.run(
        [sys.executable, str(SRC / script)],
        cwd=KG_ROOT,
        env=env,
    )
    if result.returncode != 0:
        print(f"Failed: {script} exited with {result.returncode}")
        return False
    return True


ALL_STEPS = {
    "fetch": ("fetch_papers.py", "1. Fetch agent (journal sweep)"),
    "smart-fetch": ("smart_fetch.py", "1b. Smart fetch (KG gap-targeted + cluster sweep)"),
    "gap-report": ("kg_gap_analyzer.py", "0. KG gap report (what's missing, no download)"),
    "extract": ("extract_triples.py", "2. Extract agent (ontology-based triples)"),
    "ingest": ("ingest_to_neo4j.py", "3. Ingest agent (Neo4j)"),
    "audit": ("audit_kg_quality.py", "4. KG quality audit (no writes)"),
    "contradictions": ("detect_contradictions.py", "5. Contradiction detection (no writes)"),
}


def main():
    parser = argparse.ArgumentParser(description="Run KG pipeline steps.")
    parser.add_argument(
        "--steps",
        default="fetch,extract,ingest",
        help="Comma-separated list of steps to run: fetch,smart-fetch,extract,ingest (default: fetch,extract,ingest)",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Config file to use (default: config.yaml; use config_phase4.yaml for Phase 4 expansion)",
    )
    args = parser.parse_args()

    config_path = KG_ROOT / args.config
    if not config_path.exists():
        print(f"Config file not found: {config_path}")
        sys.exit(1)

    requested = [s.strip().lower() for s in args.steps.split(",") if s.strip()]
    unknown = [s for s in requested if s not in ALL_STEPS]
    if unknown:
        print(f"Unknown steps: {unknown}. Valid steps: {list(ALL_STEPS.keys())}")
        sys.exit(1)

    run_id = os.environ.get("RUN_ID", "").strip()
    if not run_id:
        from datetime import datetime, timezone
        run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        os.environ["RUN_ID"] = run_id
        print(f"RUN_ID={run_id} (set RUN_ID to reuse for re-runs)")
    env = os.environ.copy()
    env["CONFIG_PATH"] = str(config_path)
    print(f"Using config: {config_path}")

    # Preserve user-specified step order
    steps = [(ALL_STEPS[key][0], ALL_STEPS[key][1]) for key in requested]
    for script, desc in steps:
        if not run(script, desc, env):
            sys.exit(1)

    print(f"\n--- Pipeline complete. RUN_ID={run_id}. Steps: {requested}. Manifests in data/manifests/. ---\n")


if __name__ == "__main__":
    main()
