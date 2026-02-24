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
from fetch_workers import parallel_search, parallel_fetch_articles
from kg_gap_analyzer import analyze_kg_gaps


def _load_low_yield_queries() -> set[str]:
    """Load query labels that consistently produce low yield from SQLite."""
    try:
        import sqlite3
        db_path = Path(__file__).resolve().parent.parent.parent / "data" / "health_map.db"
        if not db_path.exists():
            return set()
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT query_label, COUNT(*) AS runs,
                      SUM(triples_produced) AS total_triples,
                      SUM(papers_new) AS total_papers
               FROM fetch_yield
               GROUP BY query_label
               HAVING runs >= 3 AND total_papers > 0
                      AND CAST(total_triples AS REAL) / total_papers < 0.5"""
        ).fetchall()
        conn.close()
        return {r["query_label"] for r in rows}
    except Exception:
        return set()


def _log_yield_for_query(query_label: str, run_id: str | None,
                          papers_returned: int, papers_new: int) -> None:
    """Log per-query yield to SQLite."""
    try:
        import sqlite3
        db_path = Path(__file__).resolve().parent.parent.parent / "data" / "health_map.db"
        if not db_path.exists():
            return
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            """INSERT INTO fetch_yield
               (query_label, run_id, papers_returned, papers_new,
                triples_produced, avg_evidence_strength)
               VALUES (?, ?, ?, ?, 0, NULL)""",
            (query_label, run_id, papers_returned, papers_new),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

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
    # Landmine diseases — P1 priority for avoidance data
    "alzheimers": {
        "entities": ["Alzheimer's disease", "Dementia"],
        "keywords": ["alzheimer", "dementia", "cognitive aging", "neurodegeneration",
                     "MIND diet", "neuroprotective diet", "brain health nutrition",
                     "amyloid diet", "tau protein food"],
        "mesh": ["Alzheimer Disease", "Dementia", "Cognitive Dysfunction"],
    },
    "stroke": {
        "entities": ["Stroke", "Cerebrovascular disease"],
        "keywords": ["stroke", "cerebral infarction", "brain ischemia", "cerebrovascular",
                     "blood pressure diet", "stroke prevention nutrition", "anticoagulant food"],
        "mesh": ["Stroke", "Brain Ischemia", "Cerebrovascular Disorders"],
    },
    "depression": {
        "entities": ["Major depressive disorder", "Depression"],
        "keywords": ["depression", "antidepressant diet", "mood disorder", "mental health diet",
                     "gut brain axis depression", "omega-3 depression", "microbiome mood"],
        "mesh": ["Depressive Disorder, Major", "Depression"],
    },
    "kidney_disease": {
        "entities": ["Chronic kidney disease"],
        "keywords": ["chronic kidney disease", "renal diet", "nephrology nutrition", "CKD",
                     "kidney diet", "dialysis nutrition", "renal protective food"],
        "mesh": ["Renal Insufficiency, Chronic", "Kidney Diseases"],
    },
    "pancreatic_cancer": {
        "entities": ["Pancreatic cancer"],
        "keywords": ["pancreatic cancer", "pancreas diet", "cancer prevention nutrition",
                     "pancreatic cancer diet", "exocrine pancreas nutrition"],
        "mesh": ["Pancreatic Neoplasms", "Pancreas"],
    },
    # Additional disease clusters
    "hypertension": {
        "entities": ["Hypertension"],
        "keywords": ["hypertension", "blood pressure diet", "DASH diet", "sodium reduction",
                     "potassium food", "hypertension prevention"],
        "mesh": ["Hypertension", "Blood Pressure"],
    },
    "metabolic_syndrome": {
        "entities": ["Metabolic syndrome", "Prediabetes", "Insulin resistance"],
        "keywords": ["metabolic syndrome", "insulin resistance diet", "prediabetes nutrition",
                     "glycemic index", "low carb diet metabolic"],
        "mesh": ["Metabolic Syndrome", "Insulin Resistance"],
    },
    "obesity": {
        "entities": ["Obesity"],
        "keywords": ["obesity diet", "weight loss nutrition", "adiposity food",
                     "satiety foods", "anti-obesity diet"],
        "mesh": ["Obesity", "Weight Loss"],
    },
    "longevity": {
        "entities": ["Longevity", "Healthy aging"],
        "keywords": ["longevity diet", "healthy aging nutrition", "blue zone diet",
                     "centenarian diet", "anti-aging food", "lifespan nutrition"],
        "mesh": ["Longevity", "Aging"],
    },
    "liver_disease": {
        "entities": ["Liver disease", "NAFLD", "Fatty liver"],
        "keywords": ["fatty liver diet", "NAFLD nutrition", "liver disease food",
                     "hepatic steatosis diet", "liver protective food"],
        "mesh": ["Non-alcoholic Fatty Liver Disease", "Liver Diseases"],
    },
    "immune_health": {
        "entities": ["Immune dysfunction", "Autoimmune disease"],
        "keywords": ["immune diet", "immunonutrition", "autoimmune diet",
                     "anti-inflammatory foods immunity", "gut immune axis"],
        "mesh": ["Immunity", "Autoimmune Diseases"],
    },
    "bone_density": {
        "entities": ["Osteoporosis", "Fracture risk"],
        "keywords": ["osteoporosis diet", "bone density nutrition", "calcium food",
                     "vitamin D bone", "fracture prevention diet"],
        "mesh": ["Osteoporosis", "Bone Density", "Calcium, Dietary"],
    },
    "cancer_prevention": {
        "entities": ["Cancer", "Colorectal cancer", "Breast cancer"],
        "keywords": ["cancer prevention diet", "anticancer food", "colorectal cancer nutrition",
                     "breast cancer diet", "phytochemicals cancer"],
        "mesh": ["Neoplasms", "Colorectal Neoplasms", "Diet"],
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


# ── Main orchestration ────────────────────────────────────────────────────────

def run_smart_fetch(
    requested_clusters: list[str] | None = None,
    dry_run: bool = False,
    gap_only: bool = False,
) -> dict:
    """
    Three-stage KG-aware parallel fetch:

      Stage 1 — Build query plan:
        Run KG gap analysis + select active clusters. No network yet.

      Stage 2 — Parallel search (all queries at once):
        Run all esearch queries concurrently (workers × queries simultaneously).
        Collect and deduplicate PMCIDs across all queries. Priority order preserved.

      Stage 3 — Parallel download (all new papers at once):
        Download all new articles concurrently. Rate-limited via shared TokenBucket.
        Circuit breaker pauses workers on surge of 429s.

    Result: same papers fetched as before, but in a fraction of the time.
    """
    cfg = get_smart_fetch_config()
    paths = get_paths_config()
    raw_dir = paths["raw_papers"]

    nutrition_journals = cfg["nutrition_journals"] + cfg.get("specialty_journals", [])
    max_per_query  = cfg.get("max_per_cluster", 5)
    days_back      = cfg.get("days_back", 365)
    use_mesh       = cfg.get("use_mesh", True)
    max_gap_queries = cfg.get("max_gap_queries", 8)

    neo4j_uri  = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER",     "foodnot4self")
    neo4j_pw   = os.getenv("NEO4J_PASSWORD", "foodnot4self")

    already_fetched = get_already_fetched_pmcids(raw_dir)
    os.makedirs(raw_dir, exist_ok=True)

    # ── Stage 1: Build query plan ─────────────────────────────────────────────
    all_queries: dict[str, str] = {}   # {label: query_string}
    query_phases: dict[str, str] = {}  # {label: "phase1"|"phase2"}

    if not requested_clusters:
        print("\n=== Stage 1: KG gap analysis ===")
        gap_report = analyze_kg_gaps(
            uri=neo4j_uri, user=neo4j_user, pw=neo4j_pw,
            min_food_recs=cfg.get("gap_threshold", 3),
            days_back=days_back,
            max_per_type=cfg.get("max_gap_queries_per_type", 3),
        )
        print(gap_report.summary())

        for gq in gap_report.generated_queries[:max_gap_queries]:
            label = f"[{gq.gap_type}] {gq.entity}"
            all_queries[label] = gq.query
            query_phases[label] = "phase1"
            if dry_run:
                print(f"\n[DRY RUN] {label}:\n  {gq.query[:160]}…")
    else:
        print("\n=== Stage 1: skipped (specific clusters requested) ===")

    if not gap_only:
        try:
            simple_gaps = _simple_gap_analysis(neo4j_uri, neo4j_user, neo4j_pw,
                                               threshold=cfg.get("gap_threshold", 3))
        except Exception:
            simple_gaps = None

        active = select_active_clusters(simple_gaps, requested_clusters)

        # Skip clusters that historically produce low yield
        low_yield = _load_low_yield_queries()
        deprioritized = [c for c in active if f"cluster:{c}" in low_yield]
        if deprioritized:
            print(f"\n  Deprioritized (low yield over 3+ runs): {deprioritized}")
            active = [c for c in active if f"cluster:{c}" not in low_yield]

        print(f"\n  Active clusters: {active}")
        for cluster_name in active:
            defn = TOPIC_CLUSTERS[cluster_name]
            query = build_targeted_query(defn, nutrition_journals, days_back, use_mesh)
            label = f"cluster:{cluster_name}"
            all_queries[label] = query
            query_phases[label] = "phase2"
            if dry_run:
                print(f"\n[DRY RUN] {label}:\n  {query[:160]}…")

    if dry_run:
        print(f"\n[DRY RUN] {len(all_queries)} queries planned. No papers downloaded.")
        return {"dry_run": True, "queries_planned": len(all_queries)}

    if not all_queries:
        print("No queries to run.")
        return {"total_fetched": 0}

    # ── Stage 2: Parallel search (all queries at once) ────────────────────────
    print(f"\n=== Stage 2: Parallel search ({len(all_queries)} queries) ===")
    search_results = parallel_search(all_queries, max_results_per_query=max_per_query)

    # Collect & deduplicate PMCIDs — phase1 queries have priority (listed first)
    phase1_pmcids: list[str] = []
    phase2_pmcids: list[str] = []
    seen_pmcids: set[str] = set(already_fetched)
    run_id = get_run_id()

    for label, pmcids in search_results.items():
        new_for_query = 0
        for p in pmcids:
            if p not in seen_pmcids:
                seen_pmcids.add(p)
                new_for_query += 1
                if query_phases.get(label) == "phase1":
                    phase1_pmcids.append(p)
                else:
                    phase2_pmcids.append(p)
        # Log per-query yield
        _log_yield_for_query(label, run_id, len(pmcids), new_for_query)

    all_new = phase1_pmcids + phase2_pmcids
    print(f"  Total unique new PMCIDs: {len(all_new)} "
          f"(phase1: {len(phase1_pmcids)}, phase2: {len(phase2_pmcids)})")

    if not all_new:
        print("  No new papers found across all queries.")
        write_manifest("smart_fetch", run_id, {
            "phase1_pmcids": [], "phase2_pmcids": [],
            "pmcids_fetched": [], "total_fetched": 0,
        })
        return {"total_fetched": 0}

    # ── Stage 3: Parallel download (all new papers at once) ───────────────────
    print(f"\n=== Stage 3: Parallel download ({len(all_new)} papers) ===")
    fetched = parallel_fetch_articles(all_new, raw_dir, already_fetched=already_fetched)

    payload = {
        "phase1_pmcids": [f"PMC{p}" for p in phase1_pmcids],
        "phase2_pmcids": [f"PMC{p}" for p in phase2_pmcids],
        "pmcids_fetched": [f"PMC{p}" for p in fetched],
        "file_paths":    [f"PMC{p}.json" for p in fetched],
        "raw_papers_dir": raw_dir,
        "total_fetched": len(fetched),
        "queries_run": len(all_queries),
        "search_results": {k: len(v) for k, v in search_results.items()},
    }
    write_manifest("smart_fetch", run_id, payload)
    print(f"\nSmart fetch complete: {len(fetched)} new papers "
          f"from {len(all_queries)} parallel queries.")
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
