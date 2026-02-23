#!/usr/bin/env python3
"""
Run the full KG pipeline in cascade: each specialized agent runs in order,
writes its manifest; the next agent reads the previous manifest and consumes its output.
RUN_ID ties all artifacts for this run. Set RUN_ID in env to reuse (e.g. re-run only ingest).
Execute from kg_pipeline: python run_pipeline.py [--steps fetch,extract,ingest]
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
    "fetch": ("fetch_papers.py", "1. Fetch agent (papers)"),
    "extract": ("extract_triples.py", "2. Extract agent (ontology-based triples)"),
    "ingest": ("ingest_to_neo4j.py", "3. Ingest agent (Neo4j)"),
}


def main():
    parser = argparse.ArgumentParser(description="Run KG pipeline steps.")
    parser.add_argument(
        "--steps",
        default="fetch,extract,ingest",
        help="Comma-separated list of steps to run: fetch,extract,ingest (default: all)",
    )
    args = parser.parse_args()

    if not (KG_ROOT / "config.yaml").exists():
        print("Run from kg_pipeline directory where config.yaml exists.")
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

    steps = [(script, desc) for key, (script, desc) in ALL_STEPS.items() if key in requested]
    for script, desc in steps:
        if not run(script, desc, env):
            sys.exit(1)

    print(f"\n--- Pipeline complete. RUN_ID={run_id}. Steps: {requested}. Manifests in data/manifests/. ---\n")


if __name__ == "__main__":
    main()
