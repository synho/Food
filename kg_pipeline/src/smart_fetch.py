"""
Smart, KG-gap-aware paper fetcher.
Runs 8 topic clusters targeting nutrition journals + MeSH terms.
Active clusters are determined by which entities are underrepresented in the KG.

Usage:
    python src/smart_fetch.py                          # full smart fetch
    python src/smart_fetch.py --dry-run                # print queries, no download
    python src/smart_fetch.py --clusters sarcopenia,bone_health
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from config_loader import get_paths_config, get_smart_fetch_config
from artifacts import get_run_id, write_manifest
from fetch_papers import search_pmc, fetch_article_data

# ── Topic cluster definitions ─────────────────────────────────────────────────

TOPIC_CLUSTERS: dict[str, dict] = {
    "sarcopenia": {
        "entities": ["Sarcopenia"],
        "keywords": ["sarcopenia", "muscle mass", "leucine"],
        "mesh": ["Sarcopenia", "Muscle, Skeletal"],
    },
    "bone_health": {
        "entities": ["Osteoporosis"],
        "keywords": ["osteoporosis", "bone density", "calcium"],
        "mesh": ["Osteoporosis", "Bone Density"],
    },
    "cardiovascular": {
        "entities": ["Cardiovascular disease"],
        "keywords": ["cardiovascular", "LDL", "omega-3"],
        "mesh": ["Cardiovascular Diseases", "Fatty Acids, Omega-3"],
    },
    "diabetes": {
        "entities": ["Type 2 diabetes", "Prediabetes"],
        "keywords": ["insulin resistance", "glycemic", "fiber"],
        "mesh": ["Diabetes Mellitus, Type 2"],
    },
    "cognitive": {
        "entities": ["Cognitive decline"],
        "keywords": ["cognitive decline", "dementia", "brain"],
        "mesh": ["Cognitive Dysfunction"],
    },
    # Always-active clusters (no KG entities to check — always run)
    "inflammation": {
        "entities": [],
        "keywords": ["anti-inflammatory", "polyphenols", "CRP"],
        "mesh": ["Inflammation"],
    },
    "gut_health": {
        "entities": [],
        "keywords": ["gut microbiome", "probiotic", "fermented"],
        "mesh": ["Gastrointestinal Microbiome"],
    },
    "drug_substitution": {
        "entities": [],
        "keywords": ["nutraceutical", "supplement vs drug"],
        "mesh": ["Dietary Supplements"],
    },
}


# ── KG gap analysis ───────────────────────────────────────────────────────────

def analyze_kg_gaps(uri: str, user: str, pw: str, threshold: int = 3) -> dict[str, int] | None:
    """
    Query Neo4j for entities with degree < threshold.
    Returns {entity_name: degree}, or None if Neo4j is unreachable (triggers all-clusters fallback).
    """
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(uri, auth=(user, pw))
        # COUNT {} syntax required for Neo4j 5+
        query = """
        MATCH (n)
        WHERE n:Disease OR n:Symptom OR n:Nutrient OR n:Food
        WITH n, COUNT { (n)--() } AS deg
        WHERE deg < $threshold
        RETURN n.name AS name, deg
        """
        with driver.session() as session:
            result = session.run(query, threshold=threshold)
            gaps = {row["name"]: row["deg"] for row in result if row["name"]}
        driver.close()
        print(f"KG gap analysis: {len(gaps)} underrepresented entities (degree < {threshold}).")
        return gaps
    except Exception as e:
        print(f"Warning: KG gap analysis unavailable ({e}). All clusters will be active.")
        return None


# ── Cluster selection ─────────────────────────────────────────────────────────

def select_active_clusters(
    gaps: dict[str, int] | None,
    requested: list[str] | None = None,
) -> list[str]:
    """
    If requested is given, use exactly those clusters (CLI override).
    If gaps is None (KG unreachable), activate all clusters.
    Otherwise: always-active (entities=[]) + clusters where any entity appears in gaps.
    """
    if requested:
        invalid = [c for c in requested if c not in TOPIC_CLUSTERS]
        if invalid:
            print(f"Warning: unknown clusters {invalid}. Valid: {list(TOPIC_CLUSTERS)}")
        return [c for c in requested if c in TOPIC_CLUSTERS]

    # Fallback: KG unreachable → run all clusters
    if gaps is None:
        return list(TOPIC_CLUSTERS.keys())

    active = []
    for name, defn in TOPIC_CLUSTERS.items():
        if not defn["entities"]:
            # Always-active cluster
            active.append(name)
        elif any(e in gaps for e in defn["entities"]):
            active.append(name)
    return active


# ── Query builder ─────────────────────────────────────────────────────────────

def build_targeted_query(
    cluster_def: dict,
    nutrition_journals: list[str],
    days_back: int,
    use_mesh: bool,
) -> str:
    """
    Build a PubMed/PMC query string for a topic cluster.
    Format: (keywords OR MeSH) AND (journal list) AND (date range) AND open access AND humans
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    date_str = (
        f'("{start_date.strftime("%Y/%m/%d")}"[Date - Publication] : '
        f'"{end_date.strftime("%Y/%m/%d")}"[Date - Publication])'
    )

    # Keyword terms
    kw_terms = [f'"{kw}"[Title/Abstract]' for kw in cluster_def["keywords"]]

    # MeSH terms
    if use_mesh and cluster_def.get("mesh"):
        mesh_terms = [f'"{m}"[MeSH Terms]' for m in cluster_def["mesh"]]
        topic_part = "(" + " OR ".join(kw_terms + mesh_terms) + ")"
    else:
        topic_part = "(" + " OR ".join(kw_terms) + ")"

    # Journal list
    journal_part = "(" + " OR ".join(f'"{j}"[Journal]' for j in nutrition_journals) + ")"

    return (
        f"{topic_part} AND {journal_part} AND {date_str} "
        f'AND open access[filter] AND "humans"[MeSH Terms]'
    )


# ── Dedup against already-fetched papers ──────────────────────────────────────

def get_already_fetched_pmcids(raw_dir: str) -> set[str]:
    """Return set of already downloaded PMCIDs (numeric string, no 'PMC' prefix)."""
    existing: set[str] = set()
    if not os.path.isdir(raw_dir):
        return existing
    for fname in os.listdir(raw_dir):
        if fname.startswith("PMC") and fname.endswith(".json"):
            pmcid = fname[3:].replace(".json", "")
            existing.add(pmcid)
    return existing


# ── Main orchestration ────────────────────────────────────────────────────────

def run_smart_fetch(
    requested_clusters: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """
    Orchestrate smart fetch: gap analysis → cluster selection → queries → fetch → manifest.
    Returns summary dict.
    """
    cfg = get_smart_fetch_config()
    paths = get_paths_config()
    raw_dir = paths["raw_papers"]

    nutrition_journals = cfg["nutrition_journals"]
    gap_threshold = cfg.get("gap_threshold", 3)
    max_per_cluster = cfg.get("max_per_cluster", 5)
    days_back = cfg.get("days_back", 365)
    use_mesh = cfg.get("use_mesh", True)

    # Neo4j credentials from env (same as ingest_to_neo4j.py)
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "foodnot4self")
    neo4j_pw = os.getenv("NEO4J_PASSWORD", "foodnot4self")

    # Step 1: KG gap analysis
    gaps = analyze_kg_gaps(neo4j_uri, neo4j_user, neo4j_pw, gap_threshold)

    # Step 2: select active clusters
    active = select_active_clusters(gaps, requested_clusters)
    print(f"Active clusters: {active}")

    already_fetched = get_already_fetched_pmcids(raw_dir)
    os.makedirs(raw_dir, exist_ok=True)

    all_pmcids: list[str] = []
    fetched_files: list[str] = []
    cluster_results: dict[str, list[str]] = {}

    for cluster_name in active:
        defn = TOPIC_CLUSTERS[cluster_name]
        query = build_targeted_query(defn, nutrition_journals, days_back, use_mesh)

        if dry_run:
            print(f"\n[DRY RUN] {cluster_name}:\n  {query}")
            continue

        print(f"\nFetching cluster '{cluster_name}'...")
        pmcids = search_pmc(query, max_results=max_per_cluster)

        new_pmcids = [p for p in pmcids if p not in already_fetched]
        if not new_pmcids:
            print(f"  No new papers for cluster '{cluster_name}'.")
            cluster_results[cluster_name] = []
            continue

        cluster_fetched: list[str] = []
        for pmcid in new_pmcids:
            article = fetch_article_data(pmcid)
            if article:
                out_path = os.path.join(raw_dir, f"PMC{pmcid}.json")
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(article, f, indent=4)
                fetched_files.append(f"PMC{pmcid}.json")
                already_fetched.add(pmcid)
                cluster_fetched.append(f"PMC{pmcid}")
                all_pmcids.append(pmcid)

        cluster_results[cluster_name] = cluster_fetched
        print(f"  Fetched {len(cluster_fetched)} new papers for '{cluster_name}'.")

    if dry_run:
        print("\n[DRY RUN] Complete. No papers downloaded.")
        return {"dry_run": True, "active_clusters": active}

    run_id = get_run_id()
    payload = {
        "active_clusters": active,
        "gap_entities": list(gaps.keys()),
        "pmcids_fetched": [f"PMC{p}" for p in all_pmcids],
        "file_paths": fetched_files,
        "cluster_results": cluster_results,
        "raw_papers_dir": raw_dir,
    }
    write_manifest("smart_fetch", run_id, payload)
    print(f"\nSmart fetch complete: {len(all_pmcids)} papers across {len(active)} clusters.")
    return payload


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Smart KG-gap-aware paper fetcher")
    parser.add_argument(
        "--clusters",
        type=str,
        default="",
        help="Comma-separated cluster names to fetch (e.g. sarcopenia,cardiovascular). Default: auto.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print queries without downloading.",
    )
    args = parser.parse_args()

    requested = [c.strip() for c in args.clusters.split(",") if c.strip()] or None
    run_smart_fetch(requested_clusters=requested, dry_run=args.dry_run)


if __name__ == "__main__":
    # Allow running from kg_pipeline/ or kg_pipeline/src/
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
