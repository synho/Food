"""
Artifact and manifest handling for the pipeline cascade.
Each agent writes a manifest after its run; the next agent can read the previous manifest
to know what to process. RUN_ID ties all artifacts for one pipeline run together.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from config_loader import get_paths_config, load_config

# Agent names (used as manifest keys and directory names)
AGENT_FETCH = "fetch"
AGENT_EXTRACT = "extract"
AGENT_INGEST = "ingest"


def _manifests_dir() -> Path:
    paths = get_paths_config()
    base = Path(paths.get("manifests", "data/manifests"))
    return base if base.is_absolute() else Path.cwd() / base


def get_run_id() -> str:
    """Current run ID from env RUN_ID, or a new timestamp-based ID."""
    run_id = os.environ.get("RUN_ID", "").strip()
    if run_id:
        return run_id
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def write_manifest(agent: str, run_id: str, payload: dict) -> Path:
    """
    Write a manifest for this agent and run. Overwrites if exists.
    Returns the path to the written manifest file.
    """
    root = _manifests_dir()
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{agent}_{run_id}.json"
    payload["_agent"] = agent
    payload["_run_id"] = run_id
    payload["_ts"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return path


def read_manifest(agent: str, run_id: str | None = None) -> dict | None:
    """
    Read manifest for an agent. If run_id is None, use latest by timestamp (most recent file).
    Returns None if no manifest found.
    """
    root = _manifests_dir()
    if not root.exists():
        return None
    if run_id:
        path = root / f"{agent}_{run_id}.json"
        if not path.exists():
            return None
    else:
        # Latest: glob and pick newest by mtime
        pattern = f"{agent}_*.json"
        files = sorted(root.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            return None
        path = files[0]
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_previous_manifest(agent_order: list[str], current_agent: str, run_id: str | None = None) -> dict | None:
    """
    Read the manifest from the previous agent in the cascade. run_id optional (uses latest).
    """
    try:
        idx = agent_order.index(current_agent)
    except ValueError:
        return None
    if idx == 0:
        return None
    prev_agent = agent_order[idx - 1]
    return read_manifest(prev_agent, run_id)


# Default cascade order (used by run_pipeline and by agents that need "previous" output)
CASCADE_ORDER = [AGENT_FETCH, AGENT_EXTRACT, AGENT_INGEST]
