"""
Entity Resolution Agent — merges duplicate nodes that differ only by case or variant naming.

Post-ingest script that:
  1. Queries all Disease/Food/Nutrient/Symptom/Drug/LifestyleFactor nodes
  2. Groups by toLower(name) — finds duplicates
  3. Picks canonical name (from CANONICAL_ENTITY_NAMES or most frequent)
  4. Transfers all relationships from duplicates to the canonical node
  5. Deletes orphaned duplicate nodes

Usage:
    python src/entity_resolver.py              # resolve duplicates
    python src/entity_resolver.py --dry-run    # report only, no changes
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Allow running from kg_pipeline/ or kg_pipeline/src/
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ontology import CANONICAL_ENTITY_NAMES


def _pick_canonical(names: list[str]) -> str:
    """Choose the canonical name from a list of duplicates.
    Priority: CANONICAL_ENTITY_NAMES lookup > most common > first alphabetically."""
    for n in names:
        canonical = CANONICAL_ENTITY_NAMES.get(n.strip().lower())
        if canonical and canonical in names:
            return canonical
        if canonical:
            return canonical
    # Fallback: prefer properly-cased (contains uppercase beyond first char)
    title_cased = [n for n in names if n != n.lower() and n != n.upper()]
    if title_cased:
        return sorted(title_cased)[0]
    return sorted(names)[0]


def resolve_duplicates(
    uri: str = "bolt://localhost:7687",
    user: str = "foodnot4self",
    pw: str = "foodnot4self",
    dry_run: bool = False,
) -> dict:
    """Find and merge duplicate nodes. Returns summary stats."""
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(uri, auth=(user, pw))
    stats = {"groups_found": 0, "nodes_merged": 0, "rels_transferred": 0}

    try:
        with driver.session() as session:
            # Find duplicate groups
            result = session.run("""
                MATCH (n)
                WHERE n:Disease OR n:Food OR n:Nutrient OR n:Symptom
                      OR n:Drug OR n:LifestyleFactor
                WITH toLower(n.name) AS key, collect(n) AS nodes, count(*) AS cnt
                WHERE cnt > 1
                RETURN key,
                       [nd IN nodes | {name: nd.name, id: id(nd), labels: labels(nd)}] AS dupes
                ORDER BY cnt DESC
            """)
            groups = [(r["key"], r["dupes"]) for r in result]

        stats["groups_found"] = len(groups)
        if not groups:
            print("No duplicate groups found.")
            driver.close()
            return stats

        print(f"Found {len(groups)} duplicate group(s):")
        for key, dupes in groups:
            names = [d["name"] for d in dupes]
            canonical = _pick_canonical(names)
            print(f"  '{key}' → {len(dupes)} nodes: {names} → canonical: '{canonical}'")

            if dry_run:
                continue

            # Find the canonical node (or the first match)
            canon_dupe = next((d for d in dupes if d["name"] == canonical), dupes[0])
            canon_id = canon_dupe["id"]

            for dupe in dupes:
                if dupe["id"] == canon_id:
                    continue

                dupe_id = dupe["id"]

                with driver.session() as session:
                    # Transfer outgoing relationships
                    out_rels = session.run("""
                        MATCH (dupe)-[r]->(target)
                        WHERE id(dupe) = $dupe_id AND id(target) <> $canon_id
                        RETURN type(r) AS rel_type, properties(r) AS props, id(target) AS target_id
                    """, dupe_id=dupe_id, canon_id=canon_id).data()

                    for rel in out_rels:
                        rel_type = rel["rel_type"]
                        props = rel["props"] or {}
                        # Only create if this exact relationship doesn't exist
                        session.run(f"""
                            MATCH (canon) WHERE id(canon) = $canon_id
                            MATCH (target) WHERE id(target) = $target_id
                            MERGE (canon)-[r:{rel_type} {{source_id: $source_id}}]->(target)
                            SET r += $props
                        """, canon_id=canon_id, target_id=rel["target_id"],
                            source_id=props.get("source_id", ""),
                            props=props)
                        stats["rels_transferred"] += 1

                    # Transfer incoming relationships
                    in_rels = session.run("""
                        MATCH (source)-[r]->(dupe)
                        WHERE id(dupe) = $dupe_id AND id(source) <> $canon_id
                        RETURN type(r) AS rel_type, properties(r) AS props, id(source) AS source_id_node
                    """, dupe_id=dupe_id, canon_id=canon_id).data()

                    for rel in in_rels:
                        rel_type = rel["rel_type"]
                        props = rel["props"] or {}
                        session.run(f"""
                            MATCH (source) WHERE id(source) = $source_id_node
                            MATCH (canon) WHERE id(canon) = $canon_id
                            MERGE (source)-[r:{rel_type} {{source_id: $source_id}}]->(canon)
                            SET r += $props
                        """, source_id_node=rel["source_id_node"], canon_id=canon_id,
                            source_id=props.get("source_id", ""),
                            props=props)
                        stats["rels_transferred"] += 1

                    # Update canonical name if needed
                    session.run("""
                        MATCH (canon) WHERE id(canon) = $canon_id
                        SET canon.name = $canonical_name
                    """, canon_id=canon_id, canonical_name=canonical)

                    # Delete the duplicate node
                    session.run("""
                        MATCH (dupe) WHERE id(dupe) = $dupe_id
                        DETACH DELETE dupe
                    """, dupe_id=dupe_id)

                stats["nodes_merged"] += 1

    finally:
        driver.close()

    action = "Would merge" if dry_run else "Merged"
    print(f"\n{action}: {stats['nodes_merged']} duplicate nodes across "
          f"{stats['groups_found']} groups, transferred {stats['rels_transferred']} relationships.")
    return stats


def main():
    parser = argparse.ArgumentParser(description="Entity Resolution Agent — merge duplicate KG nodes")
    parser.add_argument("--dry-run", action="store_true", help="Report duplicates without merging")
    args = parser.parse_args()

    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "foodnot4self")
    pw = os.getenv("NEO4J_PASSWORD", "foodnot4self")

    resolve_duplicates(uri=uri, user=user, pw=pw, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
