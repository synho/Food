"""
Load pipeline config from config.yaml (next to kg_pipeline root).
Falls back to defaults if file missing or keys absent.
"""
import os
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

# Defaults (aligned with PIPELINE_STRATEGY Phase 1)
DEFAULT_JOURNALS = [
    "Nat Med", "Lancet", "N Engl J Med", "JAMA", "BMJ",
    "Cell", "Science", "Nature", "Ann Intern Med", "Am J Clin Nutr",
]

DEFAULTS = {
    "fetch": {
        "days_back": 30,
        "max_results": 10,
        "request_delay_sec": 1,
        "skip_existing": True,
        "humans_only": True,  # human studies only; no animal models
        "topic_keywords": ["nutrition", "diet"],  # optional; empty list = no topic filter
        "journals": DEFAULT_JOURNALS,
    },
    "paths": {
        "raw_papers": "data/raw_papers",
        "extracted_triples": "data/extracted_triples",
        "master_graph": "data/extracted_triples/master_graph.json",
        "manifests": "data/manifests",
    },
    "extract": {
        "model": "gemini-2.0-flash-lite",  # cheap first; upgrade after accuracy verification
    },
    "smart_fetch": {
        "nutrition_journals": [
            "Nutrients", "Br J Nutr", "J Nutr", "Eur J Nutr",
            "Nutr Rev", "Clin Nutr", "Front Nutr", "Int J Environ Res Public Health",
        ],
        "gap_threshold": 3,
        "max_per_cluster": 5,
        "days_back": 365,
        "use_mesh": True,
    },
    "continuous_build": {
        "papers_per_run": 3,
        "extract_delay_sec": 45,
        "max_retries": 3,
        "use_api_retry_after": True,
        "max_wait_sec": 120,
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge override into base recursively; override wins."""
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def get_config_path() -> Path:
    """Config path: CONFIG_PATH env var if set, else kg_pipeline/config.yaml."""
    env_path = os.environ.get("CONFIG_PATH", "").strip()
    if env_path:
        return Path(env_path)
    return Path(__file__).resolve().parent.parent / "config.yaml"


def load_config() -> dict:
    """Load config from config file (CONFIG_PATH or default config.yaml) merged with defaults."""
    config = dict(DEFAULTS)
    path = get_config_path()
    if yaml and path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
            config = _deep_merge(config, loaded)
        except Exception as e:
            print(f"Warning: could not load config from {path}: {e}")
    return config


def get_fetch_config():
    """Fetch section of config."""
    return load_config()["fetch"]


def get_paths_config():
    """Paths section of config."""
    return load_config()["paths"]


def get_extract_config():
    """Extract section of config (model, etc.)."""
    return load_config().get("extract", DEFAULTS.get("extract", {"model": "gemini-2.0-flash-lite"}))


def get_smart_fetch_config() -> dict:
    """Smart fetch section of config (nutrition journals, gap threshold, etc.)."""
    cfg = load_config()
    return _deep_merge(DEFAULTS["smart_fetch"], cfg.get("smart_fetch", {}))


def get_continuous_build_config() -> dict:
    """Continuous build section of config (papers per run, delays, retries)."""
    cfg = load_config()
    return _deep_merge(DEFAULTS["continuous_build"], cfg.get("continuous_build", {}))
