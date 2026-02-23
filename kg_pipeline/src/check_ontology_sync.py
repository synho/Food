#!/usr/bin/env python3
"""
Check that CANONICAL_ENTITY_NAMES in kg_pipeline/src/ontology.py and server/canonical.py
are in sync. Exit 0 if identical, exit 1 if drift detected.

Usage:
    python kg_pipeline/src/check_ontology_sync.py        # from repo root
    python src/check_ontology_sync.py                    # from kg_pipeline/
"""
import sys
from pathlib import Path

# Locate repo root (two levels up from this file: src/ → kg_pipeline/ → repo root)
REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def load_pipeline_names() -> dict:
    """Import CANONICAL_ENTITY_NAMES from ontology.py without modifying sys.path globally."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "ontology",
        REPO_ROOT / "kg_pipeline" / "src" / "ontology.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.CANONICAL_ENTITY_NAMES


def load_server_names() -> dict:
    """Import CANONICAL_ENTITY_NAMES from server/canonical.py."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "canonical",
        REPO_ROOT / "server" / "canonical.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.CANONICAL_ENTITY_NAMES


def main() -> int:
    try:
        pipeline = load_pipeline_names()
    except Exception as e:
        print(f"ERROR: Could not load kg_pipeline/src/ontology.py: {e}")
        return 1

    try:
        server = load_server_names()
    except Exception as e:
        print(f"ERROR: Could not load server/canonical.py: {e}")
        return 1

    pipeline_keys = set(pipeline.keys())
    server_keys = set(server.keys())

    errors: list[str] = []

    # Keys in pipeline but not in server
    only_pipeline = pipeline_keys - server_keys
    for k in sorted(only_pipeline):
        errors.append(f"  MISSING from server/canonical.py: '{k}' -> '{pipeline[k]}'")

    # Keys in server but not in pipeline
    only_server = server_keys - pipeline_keys
    for k in sorted(only_server):
        errors.append(f"  MISSING from kg_pipeline/src/ontology.py: '{k}' -> '{server[k]}'")

    # Keys present in both but with different values
    common = pipeline_keys & server_keys
    for k in sorted(common):
        if pipeline[k] != server[k]:
            errors.append(
                f"  VALUE MISMATCH for '{k}': "
                f"ontology.py='{pipeline[k]}' vs canonical.py='{server[k]}'"
            )

    if errors:
        print("ONTOLOGY SYNC CHECK FAILED — drift detected:")
        for e in errors:
            print(e)
        print(
            "\nFix: update both kg_pipeline/src/ontology.py and server/canonical.py "
            "so CANONICAL_ENTITY_NAMES is identical in both files."
        )
        return 1

    print(f"Ontology sync OK — {len(pipeline)} entries match in both files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
