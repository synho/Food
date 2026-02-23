#!/usr/bin/env python3
"""
Validate Phase 1 pipeline output: triples (master_graph.json) and optionally Neo4j.
Zero-error rule: every triple should have source_id. Run after run_pipeline.py.
Usage: from kg_pipeline: python src/validate_run.py [--neo4j]
"""
import argparse
import json
import os
import sys
from pathlib import Path

# Run from kg_pipeline root
KG_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config_loader import get_paths_config


def validate_triples(master_path: Path, strict: bool = False) -> bool:
    if not master_path.exists():
        print(f"Missing: {master_path}")
        return False
    with open(master_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        print(f"Expected list of triples, got {type(data).__name__}")
        return False
    triples = data
    total = len(triples)
    with_source = sum(1 for t in triples if t.get("source_id"))
    missing = total - with_source
    print(f"Triples: {total} total, {with_source} with source_id, {missing} missing source_id")
    if total == 0:
        print("No triples to validate.")
        return False
    if missing > 0:
        if strict:
            print(f"STRICT FAIL: {missing} triple(s) missing source_id (zero-error rule). Fix before ingesting.")
            # Print the offending triples for debugging
            for t in triples:
                if not t.get("source_id"):
                    print(f"  Missing source_id: {t.get('subject')} --{t.get('predicate')}--> {t.get('object')}")
            return False
        print("Warning: zero-error rule requires every triple to have source_id. Use --strict to fail on this.")
    else:
        print("OK: all triples have source_id.")
    # Sample keys
    sample = triples[0] if triples else {}
    print(f"Sample keys: {list(sample.keys())}")
    return total > 0


def validate_neo4j() -> bool:
    try:
        from dotenv import load_dotenv
        load_dotenv(KG_ROOT / ".env")
        from neo4j import GraphDatabase
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "foodnot4self")
        password = os.getenv("NEO4J_PASSWORD", "foodnot4self")
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            r = session.run("MATCH (n) RETURN count(n) AS c")
            nodes = r.single()["c"]
            r = session.run("MATCH ()-[r]->() RETURN count(r) AS c")
            rels = r.single()["c"]
        driver.close()
        print(f"Neo4j: {nodes} nodes, {rels} relationships")
        return True
    except Exception as e:
        print(f"Neo4j validation skipped or failed: {e}")
        return False


def main():
    ap = argparse.ArgumentParser(description="Validate pipeline output (triples + optional Neo4j)")
    ap.add_argument("--neo4j", action="store_true", help="Also validate Neo4j node/rel counts")
    ap.add_argument("--strict", action="store_true", help="Fail (exit 1) if any triple is missing source_id")
    args = ap.parse_args()
    paths = get_paths_config()
    base = KG_ROOT
    master = paths.get("master_graph") or os.path.join(paths["extracted_triples"], "master_graph.json")
    master_path = Path(master) if Path(master).is_absolute() else base / master
    print("--- Triples (master_graph) ---")
    ok = validate_triples(master_path, strict=args.strict)
    if args.neo4j:
        print("--- Neo4j ---")
        validate_neo4j()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
