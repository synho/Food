"""
Entity Resolution Agent — merges duplicate nodes that differ only by case or variant naming.

Post-ingest script that:
  1. Queries all entity nodes (dynamically from ENTITY_TYPES)
  2. Groups by toLower(name) within same label — finds duplicates
  3. Picks canonical name (from CANONICAL_ENTITY_NAMES or most frequent)
  4. Transfers all relationships from duplicates to the canonical node
  5. Deletes orphaned duplicate nodes

Also provides:
  - cleanup_nonstandard_labels(): re-label nodes with non-standard types
  - cleanup_orphans(): remove nodes with zero relationships

Usage:
    python src/entity_resolver.py                          # resolve duplicates (all labels)
    python src/entity_resolver.py --labels Disease,Food    # resolve only specific labels
    python src/entity_resolver.py --dry-run                # report only, no changes
    python src/entity_resolver.py --cleanup-labels         # re-label non-standard type nodes
    python src/entity_resolver.py --cleanup-labels --dry-run
    python src/entity_resolver.py --cleanup-orphans        # remove zero-relationship nodes
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

from ontology import CANONICAL_ENTITY_NAMES, ENTITY_TYPES, ENTITY_TYPE_ALIASES, REJECT_ENTITY_TYPES


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


def _get_driver(uri: str, user: str, pw: str):
    from neo4j import GraphDatabase
    return GraphDatabase.driver(uri, auth=(user, pw))


def _build_label_where(labels: list[str]) -> str:
    """Build a WHERE clause matching any of the given labels."""
    return " OR ".join(f"n:{label}" for label in labels)


def resolve_duplicates(
    uri: str = "bolt://localhost:7687",
    user: str = "foodnot4self",
    pw: str = "foodnot4self",
    dry_run: bool = False,
    labels: list[str] | None = None,
) -> dict:
    """Find and merge duplicate nodes. Returns summary stats.

    Args:
        labels: if provided, only resolve duplicates for these labels.
                Defaults to all ENTITY_TYPES.
    """
    driver = _get_driver(uri, user, pw)
    stats = {"groups_found": 0, "nodes_merged": 0, "rels_transferred": 0}

    target_labels = labels or list(ENTITY_TYPES)

    try:
        with driver.session() as session:
            # Find duplicate groups — only merge nodes that share the same primary label
            # to prevent merging "Heart" BodySystem with "Heart" Food
            where_clause = _build_label_where(target_labels)
            result = session.run(f"""
                MATCH (n)
                WHERE {where_clause}
                WITH toLower(n.name) AS key,
                     [l IN labels(n) WHERE l IN $target_labels][0] AS primary_label,
                     collect(n) AS nodes, count(*) AS cnt
                WHERE cnt > 1 AND primary_label IS NOT NULL
                RETURN key, primary_label,
                       [nd IN nodes | {{name: nd.name, id: id(nd), labels: labels(nd)}}] AS dupes
                ORDER BY cnt DESC
            """, target_labels=target_labels)
            groups = [(r["key"], r["primary_label"], r["dupes"]) for r in result]

        stats["groups_found"] = len(groups)
        if not groups:
            print("No duplicate groups found.")
            driver.close()
            return stats

        print(f"Found {len(groups)} duplicate group(s):")
        for key, primary_label, dupes in groups:
            # Filter to only nodes sharing the same primary label
            label_dupes = [d for d in dupes if primary_label in d["labels"]]
            if len(label_dupes) < 2:
                continue

            names = [d["name"] for d in label_dupes]
            canonical = _pick_canonical(names)
            print(f"  [{primary_label}] '{key}' → {len(label_dupes)} nodes: {names} → canonical: '{canonical}'")

            if dry_run:
                continue

            # Find the canonical node (or the first match)
            canon_dupe = next((d for d in label_dupes if d["name"] == canonical), label_dupes[0])
            canon_id = canon_dupe["id"]

            for dupe in label_dupes:
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


def cleanup_nonstandard_labels(
    uri: str = "bolt://localhost:7687",
    user: str = "foodnot4self",
    pw: str = "foodnot4self",
    dry_run: bool = False,
) -> dict:
    """Find nodes with non-standard labels and re-label or delete them.

    For labels with a mapping in ENTITY_TYPE_ALIASES: add the valid label, remove the old one.
    For labels in REJECT_ENTITY_TYPES with 0 rels after relabeling: delete.
    For unmappable labels: report only.
    """
    driver = _get_driver(uri, user, pw)
    valid_labels = set(ENTITY_TYPES)
    stats = {"relabeled": 0, "deleted": 0, "unmapped": []}

    # Build a lookup: lowercased non-standard label → valid label
    alias_lookup: dict[str, str | None] = {}
    for alias_key, valid_type in ENTITY_TYPE_ALIASES.items():
        # Store PascalCase-ish forms too (the way they appear as Neo4j labels)
        alias_lookup[alias_key.lower()] = valid_type

    # Also register reject types
    for rt in REJECT_ENTITY_TYPES:
        alias_lookup[rt.lower()] = None  # None means "delete"

    try:
        with driver.session() as session:
            # Get all labels in the database
            result = session.run("CALL db.labels() YIELD label RETURN label")
            all_labels = [r["label"] for r in result]

        nonstandard = [lb for lb in all_labels if lb not in valid_labels]
        if not nonstandard:
            print("No non-standard labels found.")
            driver.close()
            return stats

        print(f"Non-standard labels found: {nonstandard}")

        for label in nonstandard:
            key = label.replace(" ", "_").replace("-", "_").lower()
            target = alias_lookup.get(key)

            with driver.session() as session:
                nodes = session.run(f"""
                    MATCH (n:{label})
                    RETURN id(n) AS nid, n.name AS name, labels(n) AS all_labels
                """).data()

            if not nodes:
                continue

            if target is None and key in REJECT_ENTITY_TYPES:
                # Reject type — delete nodes that have no rels or only have this label
                print(f"  [{label}] → REJECT ({len(nodes)} nodes)")
                if dry_run:
                    stats["deleted"] += len(nodes)
                    continue
                for node in nodes:
                    with driver.session() as session:
                        # Check if node has relationships
                        rel_count = session.run("""
                            MATCH (n)-[r]-() WHERE id(n) = $nid RETURN count(r) AS cnt
                        """, nid=node["nid"]).single()["cnt"]
                        if rel_count == 0:
                            session.run("MATCH (n) WHERE id(n) = $nid DELETE n", nid=node["nid"])
                            stats["deleted"] += 1
                        else:
                            # Has rels — detach delete since the entity type is noise
                            session.run("MATCH (n) WHERE id(n) = $nid DETACH DELETE n", nid=node["nid"])
                            stats["deleted"] += 1

            elif target is not None:
                # Mappable — re-label
                print(f"  [{label}] → {target} ({len(nodes)} nodes)")
                if dry_run:
                    stats["relabeled"] += len(nodes)
                    continue
                for node in nodes:
                    with driver.session() as session:
                        session.run(f"""
                            MATCH (n) WHERE id(n) = $nid
                            SET n:{target}
                            REMOVE n:{label}
                        """, nid=node["nid"])
                    stats["relabeled"] += 1

            else:
                # Unknown — no mapping found
                print(f"  [{label}] → UNKNOWN ({len(nodes)} nodes) — no mapping")
                stats["unmapped"].append({"label": label, "count": len(nodes)})

    finally:
        driver.close()

    action = "Would" if dry_run else "Did"
    print(f"\n{action}: relabeled {stats['relabeled']} nodes, "
          f"deleted {stats['deleted']} nodes, "
          f"{len(stats['unmapped'])} unmapped labels.")
    return stats


def cleanup_orphans(
    uri: str = "bolt://localhost:7687",
    user: str = "foodnot4self",
    pw: str = "foodnot4self",
    dry_run: bool = False,
) -> dict:
    """Find and remove nodes with zero relationships across all labels."""
    driver = _get_driver(uri, user, pw)
    stats = {"orphans_found": 0, "orphans_deleted": 0}

    try:
        with driver.session() as session:
            result = session.run("""
                MATCH (n)
                WHERE NOT (n)--()
                RETURN id(n) AS nid, n.name AS name, labels(n) AS all_labels
            """)
            orphans = result.data()

        stats["orphans_found"] = len(orphans)
        if not orphans:
            print("No orphan nodes found.")
            driver.close()
            return stats

        print(f"Found {len(orphans)} orphan node(s):")
        for o in orphans:
            print(f"  {o['name']} ({', '.join(o['all_labels'])})")

        if not dry_run:
            with driver.session() as session:
                result = session.run("""
                    MATCH (n) WHERE NOT (n)--()
                    DELETE n
                    RETURN count(n) AS deleted
                """)
                stats["orphans_deleted"] = result.single()["deleted"]
            print(f"\nDeleted {stats['orphans_deleted']} orphan nodes.")
        else:
            print(f"\nWould delete {stats['orphans_found']} orphan nodes.")

    finally:
        driver.close()

    return stats


def main():
    parser = argparse.ArgumentParser(description="Entity Resolution Agent — merge duplicate KG nodes")
    parser.add_argument("--dry-run", action="store_true", help="Report duplicates without merging")
    parser.add_argument("--labels", type=str, default="",
                        help="Comma-separated labels to resolve (default: all ENTITY_TYPES)")
    parser.add_argument("--cleanup-labels", action="store_true",
                        help="Re-label non-standard type nodes")
    parser.add_argument("--cleanup-orphans", action="store_true",
                        help="Remove nodes with zero relationships")
    args = parser.parse_args()

    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "foodnot4self")
    pw = os.getenv("NEO4J_PASSWORD", "foodnot4self")

    if args.cleanup_labels:
        cleanup_nonstandard_labels(uri=uri, user=user, pw=pw, dry_run=args.dry_run)
    elif args.cleanup_orphans:
        cleanup_orphans(uri=uri, user=user, pw=pw, dry_run=args.dry_run)
    else:
        labels = [l.strip() for l in args.labels.split(",") if l.strip()] or None
        resolve_duplicates(uri=uri, user=user, pw=pw, dry_run=args.dry_run, labels=labels)


if __name__ == "__main__":
    main()
