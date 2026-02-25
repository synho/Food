"""
Re-normalize all extracted triples through the updated ontology and validator.
Fixes entity type normalization issues (e.g. Agerelatedchange → AgeRelatedChange),
maps noise types to valid ontology types, and rejects triples with unknown types.

Usage:
    cd kg_pipeline
    python src/renormalize_graph.py --dry-run     # preview changes
    python src/renormalize_graph.py               # re-normalize and rewrite files
    python src/renormalize_graph.py --reingest    # re-normalize + re-ingest to Neo4j
"""
import argparse
import glob
import json
import os
import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ontology import (
    normalize_entity_type,
    normalize_entity_name,
    normalize_predicate,
    ENTITY_TYPES,
)
from triple_validator import validate_and_score, report as validator_report
from config_loader import get_paths_config


def renormalize_triple(t: dict) -> dict:
    """Re-normalize a single triple through the updated ontology."""
    t["subject_type"] = normalize_entity_type(t.get("subject_type", ""))
    t["object_type"] = normalize_entity_type(t.get("object_type", ""))
    t["predicate"] = normalize_predicate(t.get("predicate", ""))
    t["subject"] = normalize_entity_name(t.get("subject", ""), t.get("subject_type", ""))
    t["object"] = normalize_entity_name(t.get("object", ""), t.get("object_type", ""))
    return t


def main():
    parser = argparse.ArgumentParser(description="Re-normalize extracted triples through updated ontology")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    parser.add_argument("--reingest", action="store_true", help="Also re-ingest into Neo4j after renormalization")
    args = parser.parse_args()

    paths = get_paths_config()
    triple_dir = paths["extracted_triples"]
    master_path = paths.get("master_graph") or os.path.join(triple_dir, "master_graph.json")

    valid_types = set(ENTITY_TYPES)
    type_changes = Counter()  # old_type → new_type
    type_rejections = Counter()  # type → count (types that still don't match)
    files_modified = 0
    total_triples = 0
    total_fixed = 0

    triple_files = sorted(glob.glob(os.path.join(triple_dir, "*_triples.json")))
    print(f"Re-normalizing {len(triple_files)} triple files...")

    all_triples = []

    for fpath in triple_files:
        with open(fpath, "r") as f:
            triples = json.load(f)

        modified = False
        for t in triples:
            total_triples += 1
            old_st = t.get("subject_type", "")
            old_ot = t.get("object_type", "")
            old_pred = t.get("predicate", "")

            renormalize_triple(t)

            if t["subject_type"] != old_st:
                type_changes[f"{old_st} → {t['subject_type']}"] += 1
                modified = True
                total_fixed += 1
            if t["object_type"] != old_ot:
                type_changes[f"{old_ot} → {t['object_type']}"] += 1
                modified = True
                total_fixed += 1
            if t["predicate"] != old_pred:
                modified = True
                total_fixed += 1

            # Track types that are still outside the ontology
            if t["subject_type"] not in valid_types:
                type_rejections[t["subject_type"]] += 1
            if t["object_type"] not in valid_types:
                type_rejections[t["object_type"]] += 1

        all_triples.extend(triples)

        if modified and not args.dry_run:
            with open(fpath, "w") as f:
                json.dump(triples, f, indent=4)
            files_modified += 1

    # Validate all triples
    print(f"\nValidating {len(all_triples)} total triples...")
    valid, rejected, stats = validate_and_score(all_triples)
    print(validator_report(stats))

    print(f"\n=== Re-normalization Summary ===")
    print(f"  Files scanned:  {len(triple_files)}")
    print(f"  Total triples:  {total_triples}")
    print(f"  Types fixed:    {total_fixed}")
    print(f"  Files modified: {files_modified}")
    print(f"  Valid triples:  {len(valid)}")
    print(f"  Rejected:       {len(rejected)}")

    if type_changes:
        print(f"\n  Type changes (top 20):")
        for change, count in type_changes.most_common(20):
            print(f"    {count:5d}  {change}")

    if type_rejections:
        print(f"\n  Types still outside ontology (will be rejected by validator):")
        for typ, count in type_rejections.most_common(20):
            print(f"    {count:5d}  {typ}")

    if args.dry_run:
        print(f"\n  [DRY RUN] No files written.")
        return

    # Write master_graph.json with only valid triples
    print(f"\nWriting master_graph.json with {len(valid)} valid triples...")
    with open(master_path, "w") as f:
        json.dump(valid, f, indent=2)
    print(f"  Written: {master_path}")

    if args.reingest:
        print(f"\nRe-ingesting into Neo4j...")
        # Clear and re-ingest
        from ingest_to_neo4j import KnowledgeGraphIngestor, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
        ingestor = KnowledgeGraphIngestor(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)

        # Drop all existing data and re-ingest clean
        with ingestor.driver.session() as session:
            print("  Clearing existing graph data...")
            session.run("MATCH (n) DETACH DELETE n")
            print("  Graph cleared.")

        ingestor.setup_schema()
        print(f"  Ingesting {len(valid)} valid triples...")
        ingestor.ingest_triples(valid)
        ingestor.close()
        print("  Re-ingestion complete.")


if __name__ == "__main__":
    main()
