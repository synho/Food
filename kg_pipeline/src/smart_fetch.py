"""
Smart, KG-gap-aware paper fetcher.

Two-phase fetch strategy:
  Phase 1 (KG-targeted): query Neo4j for specific missing relationships, generate
    entity-level PubMed queries to fill those exact gaps — these run FIRST and with
    highest priority.
  Phase 2 (cluster sweep): broad topic clusters (bone_health, inflammation, etc.)
    targeting underrepresented entities — fills breadth after targeted gaps are covered.

Usage:
    python src/smart_fetch.py                          # full smart fetch (both phases)
    python src/smart_fetch.py --dry-run                # print queries, no download
    python src/smart_fetch.py --clusters sarcopenia,bone_health  # clusters only
    python src/smart_fetch.py --gap-only               # entity-targeted queries only
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
from kg_gap_analyzer import analyze_kg_gaps

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


# (KG gap analysis moved to kg_gap_analyzer.py — imported above)


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


# ── Shared fetch helper ───────────────────────────────────────────────────────

def _fetch_from_query(
    label: str,
    query: str,
    max_results: int,
    raw_dir: str,
    already_fetched: set[str],
    dry_run: bool,
) -> list[str]:
    """Search PMC with query, download new papers, return list of fetched PMCIDs."""
    if dry_run:
        print(f"\n[DRY RUN] {label}:\n  {query[:160]}...")
        return []

    print(f"\nFetching: {label}")
    pmcids = search_pmc(query, max_results=max_results)
    new_pmcids = [p for p in pmcids if p not in already_fetched]
    if not new_pmcids:
        print(f"  No new papers found.")
        return []

    fetched: list[str] = []
    for pmcid in new_pmcids:
        article = fetch_article_data(pmcid)
        if article:
            out_path = os.path.join(raw_dir, f"PMC{pmcid}.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(article, f, indent=4)
            already_fetched.add(pmcid)
            fetched.append(pmcid)

    print(f"  Fetched {len(fetched)} new papers.")
    return fetched


# ── Main orchestration ────────────────────────────────────────────────────────

def run_smart_fetch(
    requested_clusters: list[str] | None = None,
    dry_run: bool = False,
    gap_only: bool = False,
) -> dict:
    """
    Two-phase KG-aware fetch:
      Phase 1 — Entity-targeted: query Neo4j for specific missing relationships,
        generate precise PubMed queries, fetch FIRST (highest priority).
      Phase 2 — Cluster sweep: broad topic clusters for breadth coverage.
        Skipped when gap_only=True or when requested_clusters is specified.
    """
    cfg = get_smart_fetch_config()
    paths = get_paths_config()
    raw_dir = paths["raw_papers"]

    nutrition_journals = cfg["nutrition_journals"]
    max_per_query = cfg.get("max_per_cluster", 5)
    days_back = cfg.get("days_back", 365)
    use_mesh = cfg.get("use_mesh", True)
    max_gap_queries = cfg.get("max_gap_queries", 8)

    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "foodnot4self")
    neo4j_pw = os.getenv("NEO4J_PASSWORD", "foodnot4self")

    already_fetched = get_already_fetched_pmcids(raw_dir)
    os.makedirs(raw_dir, exist_ok=True)

    all_pmcids: list[str] = []
    phase1_results: dict[str, list[str]] = {}
    phase2_results: dict[str, list[str]] = {}

    # ── Phase 1: KG-targeted gap queries (always run unless --clusters specified) ──
    if not requested_clusters:
        print("\n=== Phase 1: KG gap analysis → targeted queries ===")
        gap_report = analyze_kg_gaps(
            uri=neo4j_uri, user=neo4j_user, pw=neo4j_pw,
            min_food_recs=cfg.get("gap_threshold", 3),
            days_back=days_back,
            max_per_type=cfg.get("max_gap_queries_per_type", 3),
        )
        print(gap_report.summary())

        targeted_queries = gap_report.generated_queries[:max_gap_queries]
        if not targeted_queries:
            print("  No targeted queries generated (KG may be unreachable).")
        else:
            print(f"\n  Running {len(targeted_queries)} targeted gap queries (P1 first)...")

        for gq in targeted_queries:
            label = f"[{gq.gap_type}] {gq.entity}"
            fetched = _fetch_from_query(label, gq.query, max_per_query, raw_dir, already_fetched, dry_run)
            phase1_results[label] = [f"PMC{p}" for p in fetched]
            all_pmcids.extend(fetched)
    else:
        print("\n=== Phase 1: skipped (specific clusters requested) ===")

    # ── Phase 2: Topic cluster sweep ──────────────────────────────────────────
    if not gap_only:
        print("\n=== Phase 2: Topic cluster sweep ===")

        # For cluster-based gap analysis, fall back to simple degree-based analysis
        # (used only for cluster selection, not query generation)
        try:
            simple_gaps = _simple_gap_analysis(neo4j_uri, neo4j_user, neo4j_pw,
                                                threshold=cfg.get("gap_threshold", 3))
        except Exception:
            simple_gaps = None

        active = select_active_clusters(simple_gaps, requested_clusters)
        print(f"Active clusters: {active}")

        for cluster_name in active:
            defn = TOPIC_CLUSTERS[cluster_name]
            query = build_targeted_query(defn, nutrition_journals, days_back, use_mesh)
            label = f"cluster:{cluster_name}"
            fetched = _fetch_from_query(label, query, max_per_query, raw_dir, already_fetched, dry_run)
            phase2_results[cluster_name] = [f"PMC{p}" for p in fetched]
            all_pmcids.extend(fetched)

    if dry_run:
        print("\n[DRY RUN] Complete. No papers downloaded.")
        return {"dry_run": True}

    run_id = get_run_id()
    payload = {
        "phase1_targeted": phase1_results,
        "phase2_clusters": phase2_results,
        "pmcids_fetched": [f"PMC{p}" for p in all_pmcids],
        "file_paths": [f"PMC{p}.json" for p in all_pmcids],
        "raw_papers_dir": raw_dir,
        "total_fetched": len(all_pmcids),
    }
    write_manifest("smart_fetch", run_id, payload)
    print(f"\nSmart fetch complete: {len(all_pmcids)} new papers "
          f"({len(phase1_results)} targeted + {len(phase2_results)} cluster queries).")
    return payload


def _simple_gap_analysis(uri: str, user: str, pw: str, threshold: int = 3) -> dict[str, int] | None:
    """Lightweight degree-based gap analysis used only for cluster selection."""
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(uri, auth=(user, pw))
        q = """
        MATCH (n)
        WHERE n:Disease OR n:Symptom OR n:Nutrient OR n:Food
        WITH n, COUNT { (n)--() } AS deg
        WHERE deg < $threshold
        RETURN n.name AS name, deg
        """
        with driver.session() as session:
            result = session.run(q, threshold=threshold)
            gaps = {row["name"]: row["deg"] for row in result if row["name"]}
        driver.close()
        return gaps
    except Exception:
        return None


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Smart KG-gap-aware paper fetcher")
    parser.add_argument(
        "--clusters",
        type=str,
        default="",
        help="Only run these clusters (skips Phase 1 gap queries). e.g. sarcopenia,cardiovascular",
    )
    parser.add_argument(
        "--gap-only",
        action="store_true",
        help="Only run Phase 1 entity-targeted gap queries; skip cluster sweep.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print all queries without downloading anything.",
    )
    args = parser.parse_args()

    requested = [c.strip() for c in args.clusters.split(",") if c.strip()] or None
    run_smart_fetch(requested_clusters=requested, dry_run=args.dry_run, gap_only=args.gap_only)


if __name__ == "__main__":
    # Allow running from kg_pipeline/ or kg_pipeline/src/
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
