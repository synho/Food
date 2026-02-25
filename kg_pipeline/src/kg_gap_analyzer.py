"""
KG Gap Analyzer — queries Neo4j to identify what is missing, then generates
targeted PubMed search queries to fill those specific gaps.

Gap types detected:
  1. conditions_no_food_recs   — diseases with no PREVENTS/TREATS/ALLEVIATES from food/nutrient
  2. conditions_no_avoidance   — diseases with no AGGRAVATES/CAUSES from food/nutrient
  3. foods_no_nutrients        — Food nodes with no CONTAINS→Nutrient links
  4. nutrients_no_food         — Nutrient nodes with no Food→CONTAINS link
  5. symptoms_no_early_signal  — Symptom nodes with no EARLY_SIGNAL_OF→Disease

Usage:
    python src/kg_gap_analyzer.py          # print gap report
    python src/kg_gap_analyzer.py --json   # print JSON report
"""
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

# ── Non-nutrition entities to skip (drug trials, rare oncology, etc.) ──────────
_SKIP_CONDITIONS = {
    "ntrk+ disease", "ntrk+ solid tumors", "advanced solid tumors", "vitt",
    "ebv dna quantifications", "persistent ebv infection", "epstein–barr virus (ebv)",
    "autoimmunity",  # too broad without specific subtype
}

# ── Journals to target for different query types ──────────────────────────────
_NUTRITION_JOURNALS = [
    "Nutrients", "Br J Nutr", "J Nutr", "Eur J Nutr",
    "Am J Clin Nutr", "Nutr Rev", "Clin Nutr", "Front Nutr",
    "Int J Environ Res Public Health", "J Acad Nutr Diet",
    "Public Health Nutr", "Int J Food Sci Nutr", "Food Funct",
    "Nutr Metab Cardiovasc Dis", "Nutr Cancer",
]
_MEDICAL_JOURNALS = [
    "Nat Med", "Lancet", "N Engl J Med", "JAMA", "BMJ",
    "Ann Intern Med", "Am J Clin Nutr",
    # Neurology / dementia / stroke
    "JAMA Neurol", "Lancet Neurol", "Alzheimers Dement", "Neurology",
    "J Alzheimers Dis", "Brain", "Ann Neurol",
    # Kidney
    "Kidney Int", "J Am Soc Nephrol", "Clin J Am Soc Nephrol",
    "Nephrol Dial Transplant",
    # Oncology
    "Lancet Oncol", "J Natl Cancer Inst", "Gut",
    "Cancer Epidemiol Biomarkers Prev",
    # Psychiatry
    "JAMA Psychiatry", "Mol Psychiatry", "J Affect Disord",
    # Cardiovascular
    "Eur Heart J", "Circulation", "J Am Coll Cardiol",
    # Diabetes / metabolic
    "Diabetes Care", "Diabetologia",
    # Aging
    "Age Ageing", "J Gerontol A Biol Sci Med Sci",
]
_FOOD_CHEM_JOURNALS = [
    "Food Chem", "J Food Compos Anal", "LWT", "Food Res Int",
    "Nutrients", "Br J Nutr", "J Nutr",
]


@dataclass
class GapQuery:
    entity: str
    gap_type: str           # no_food_recs | no_avoidance | no_nutrients | no_food_source | no_early_signal
    query: str              # PubMed/PMC query string
    priority: int           # 1=high, 2=medium, 3=low
    hint: str = ""          # human-readable description


@dataclass
class GapReport:
    conditions_no_food_recs: list[tuple[str, int]] = field(default_factory=list)   # (name, current_count)
    conditions_no_avoidance: list[str] = field(default_factory=list)
    foods_no_nutrients: list[str] = field(default_factory=list)
    nutrients_no_food: list[str] = field(default_factory=list)
    symptoms_no_early_signal: list[str] = field(default_factory=list)
    # Medical KG layer gaps
    biomarkers_no_food_link: list[str] = field(default_factory=list)
    diseases_no_biomarker: list[str] = field(default_factory=list)
    mechanisms_no_food: list[str] = field(default_factory=list)
    generated_queries: list[GapQuery] = field(default_factory=list)
    as_of: str = ""

    def summary(self) -> str:
        lines = [
            f"KG Gap Report — {self.as_of}",
            f"  Conditions with < 3 food recs:  {len(self.conditions_no_food_recs)}",
            f"  Conditions with no avoidance:   {len(self.conditions_no_avoidance)}",
            f"  Foods with no nutrient links:   {len(self.foods_no_nutrients)}",
            f"  Nutrients with no food source:  {len(self.nutrients_no_food)}",
            f"  Symptoms with no early signal:  {len(self.symptoms_no_early_signal)}",
            f"  Biomarkers w/o food link:       {len(self.biomarkers_no_food_link)}",
            f"  Diseases w/o biomarker:         {len(self.diseases_no_biomarker)}",
            f"  Mechanisms w/o food link:        {len(self.mechanisms_no_food)}",
            f"  Generated targeted queries:     {len(self.generated_queries)}",
        ]
        return "\n".join(lines)


# ── Neo4j gap queries ──────────────────────────────────────────────────────────

def _run_gap_queries(uri: str, user: str, pw: str, min_food_recs: int = 3) -> Optional[GapReport]:
    """Query Neo4j for all gap types. Returns None if Neo4j is unreachable."""
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(uri, auth=(user, pw))
    except Exception as e:
        print(f"Warning: cannot connect to Neo4j ({e}). Skipping KG gap analysis.")
        return None

    report = GapReport(as_of=datetime.now().strftime("%Y-%m-%d %H:%M"))

    try:
        with driver.session() as s:
            # 1. Conditions with fewer than N food-based recommendations
            rows = s.run("""
                MATCH (d:Disease)
                OPTIONAL MATCH (f)-[rel:PREVENTS|TREATS|ALLEVIATES|REDUCES_RISK_OF]->(d)
                WHERE (f:Food OR f:Nutrient) AND rel.source_id IS NOT NULL
                WITH d.name AS name, count(rel) AS recs
                WHERE recs < $min_recs
                RETURN name, recs ORDER BY recs ASC
            """, min_recs=min_food_recs)
            report.conditions_no_food_recs = [
                (r["name"], r["recs"]) for r in rows
                if r["name"] and r["name"].lower() not in _SKIP_CONDITIONS
            ]

            # 2. Conditions with no avoidance data (but have at least 1 other relationship)
            rows = s.run("""
                MATCH (d:Disease)
                WHERE COUNT { (d)--() } > 0
                AND NOT (:Food|Nutrient)-[:AGGRAVATES|CAUSES]->(d)
                RETURN d.name AS name ORDER BY name
            """)
            report.conditions_no_avoidance = [
                r["name"] for r in rows
                if r["name"] and r["name"].lower() not in _SKIP_CONDITIONS
            ]

            # 3. Foods with no CONTAINS→Nutrient links
            rows = s.run("""
                MATCH (f:Food) WHERE NOT (f)-[:CONTAINS]->(:Nutrient)
                RETURN f.name AS name ORDER BY name
            """)
            report.foods_no_nutrients = [r["name"] for r in rows if r["name"]]

            # 4. Nutrients not linked from any food via CONTAINS
            rows = s.run("""
                MATCH (n:Nutrient) WHERE NOT (:Food)-[:CONTAINS]->(n)
                RETURN n.name AS name ORDER BY name
            """)
            # Filter out non-standard nutrient names
            report.nutrients_no_food = [
                r["name"] for r in rows
                if r["name"] and len(r["name"]) > 2 and not r["name"].startswith("T2D")
            ]

            # 5. Symptoms with no EARLY_SIGNAL_OF link
            rows = s.run("""
                MATCH (s:Symptom) WHERE NOT (s)-[:EARLY_SIGNAL_OF]->(:Disease)
                RETURN s.name AS name ORDER BY name
            """)
            report.symptoms_no_early_signal = [r["name"] for r in rows if r["name"]]

            # 6. Biomarkers with no incoming INCREASES_BIOMARKER/DECREASES_BIOMARKER from Food/Nutrient
            rows = s.run("""
                MATCH (b:Biomarker)
                WHERE NOT (:Food|Nutrient)-[:INCREASES_BIOMARKER|DECREASES_BIOMARKER]->(b)
                RETURN b.name AS name ORDER BY name
            """)
            report.biomarkers_no_food_link = [r["name"] for r in rows if r["name"]]

            # 7. Diseases with no incoming BIOMARKER_FOR
            rows = s.run("""
                MATCH (d:Disease)
                WHERE COUNT { (d)--() } > 0
                AND NOT (:Biomarker)-[:BIOMARKER_FOR]->(d)
                RETURN d.name AS name ORDER BY name
            """)
            report.diseases_no_biomarker = [
                r["name"] for r in rows
                if r["name"] and r["name"].lower() not in _SKIP_CONDITIONS
            ]

            # 8. Mechanisms with no incoming TARGETS_MECHANISM from Food/Nutrient
            rows = s.run("""
                MATCH (m:Mechanism)
                WHERE NOT (:Food|Nutrient)-[:TARGETS_MECHANISM]->(m)
                RETURN m.name AS name ORDER BY name
            """)
            report.mechanisms_no_food = [r["name"] for r in rows if r["name"]]

    except Exception as e:
        print(f"Warning: gap query failed: {e}")
    finally:
        driver.close()

    return report


# ── Query generation ──────────────────────────────────────────────────────────

def _date_range_str(days_back: int = 730) -> str:
    end = datetime.now()
    start = end - timedelta(days=days_back)
    return (
        f'("{start.strftime("%Y/%m/%d")}"[Date - Publication] : '
        f'"{end.strftime("%Y/%m/%d")}"[Date - Publication])'
    )


def _journal_clause(journals: list[str]) -> str:
    return "(" + " OR ".join(f'"{j}"[Journal]' for j in journals) + ")"


def _build_queries(
    report: GapReport,
    days_back: int = 730,
    max_per_type: int = 5,
    demand_boost: set[str] | None = None,
) -> list[GapQuery]:
    queries: list[GapQuery] = []
    _demand = demand_boost or set()
    date = _date_range_str(days_back)
    base_filters = f'{date} AND open access[filter] AND "humans"[MeSH Terms]'

    nutr_j = _journal_clause(_NUTRITION_JOURNALS)
    med_j = _journal_clause(_MEDICAL_JOURNALS)
    food_j = _journal_clause(_FOOD_CHEM_JOURNALS)

    # Priority 1 (0 if demand-boosted) — Conditions with no food recommendations (most impactful)
    for name, count in report.conditions_no_food_recs[:max_per_type]:
        q = (
            f'("{name}"[Title/Abstract] OR "{name}"[MeSH Terms]) '
            f'AND (diet OR food OR nutrition OR nutrient OR dietary) '
            f'AND {nutr_j} AND {base_filters}'
        )
        priority = 0 if name in _demand else 1
        queries.append(GapQuery(
            entity=name, gap_type="no_food_recs", query=q, priority=priority,
            hint=f"{name} has {count} food recs — find more food/nutrient evidence"
                 + (" [HIGH DEMAND]" if name in _demand else ""),
        ))

    # Priority 1 — Key conditions with no avoidance data
    _avoidance_priority = {"Type 2 diabetes", "Hypertension", "Cardiovascular disease",
                           "Osteoporosis", "Sarcopenia", "Prediabetes",
                           # Landmine diseases — P1 priority for avoidance data
                           "Alzheimer's disease", "Stroke", "Chronic kidney disease",
                           "Major depressive disorder", "Pancreatic cancer", "Dementia"}
    priority_avoidance = [n for n in report.conditions_no_avoidance if n in _avoidance_priority]
    rest_avoidance = [n for n in report.conditions_no_avoidance if n not in _avoidance_priority]

    for name in (priority_avoidance + rest_avoidance)[:max_per_type]:
        q = (
            f'("{name}"[Title/Abstract] OR "{name}"[MeSH Terms]) '
            f'AND (avoid OR worsen OR "risk factor" OR aggravate OR harmful OR "foods to limit") '
            f'AND (diet OR food OR nutrition) AND {nutr_j} AND {base_filters}'
        )
        if name in _demand:
            priority = 0
        elif name in _avoidance_priority:
            priority = 1
        else:
            priority = 2
        queries.append(GapQuery(
            entity=name, gap_type="no_avoidance", query=q, priority=priority,
            hint=f"No AGGRAVATES/CAUSES data for {name} — find foods to avoid"
                 + (" [HIGH DEMAND]" if name in _demand else ""),
        ))

    # Priority 2 — Foods with no nutrient links
    _food_priority = {"Mediterranean diet", "Leafy greens", "Berries", "Olive oil",
                      "Oily fish", "Legumes", "Red meat", "Whole grains"}
    priority_foods = [f for f in report.foods_no_nutrients if f in _food_priority]
    rest_foods = [f for f in report.foods_no_nutrients if f not in _food_priority]

    for name in (priority_foods + rest_foods)[:max_per_type]:
        q = (
            f'("{name}"[Title/Abstract]) '
            f'AND (nutrient OR vitamin OR mineral OR composition OR "nutritional content" OR antioxidant) '
            f'AND {food_j} AND {date} AND open access[filter]'
        )
        queries.append(GapQuery(
            entity=name, gap_type="no_nutrients", query=q, priority=2,
            hint=f"{name} has no CONTAINS→Nutrient links — find composition data",
        ))

    # Priority 2 — Nutrients with no food source
    _nutrient_priority = {"Omega-3", "Vitamin D", "Calcium", "Magnesium", "Iron",
                          "Folate", "Vitamin B12", "Potassium", "Dietary fibre",
                          "omega-3 fatty acid", "calcium", "antioxidants"}
    priority_nutrients = [n for n in report.nutrients_no_food if n in _nutrient_priority]
    rest_nutrients = [n for n in report.nutrients_no_food if n not in _nutrient_priority]

    for name in (priority_nutrients + rest_nutrients)[:max_per_type]:
        q = (
            f'("{name}"[Title/Abstract] OR "{name}"[MeSH Terms]) '
            f'AND ("food source" OR "dietary source" OR "found in" OR "rich in" OR "high in") '
            f'AND {food_j} AND {date} AND open access[filter]'
        )
        queries.append(GapQuery(
            entity=name, gap_type="no_food_source", query=q, priority=2,
            hint=f"{name} not linked to any food — find food sources",
        ))

    # Priority 3 — Symptoms with no early signal
    for name in report.symptoms_no_early_signal[:max_per_type]:
        q = (
            f'("{name}"[Title/Abstract]) '
            f'AND ("early sign" OR "early indicator" OR precursor OR "warning sign" OR "early symptom") '
            f'AND disease AND {med_j} AND {base_filters}'
        )
        queries.append(GapQuery(
            entity=name, gap_type="no_early_signal", query=q, priority=3,
            hint=f"{name} has no EARLY_SIGNAL_OF link — find disease associations",
        ))

    # Priority 2 — Biomarkers with no food link
    for name in report.biomarkers_no_food_link[:max_per_type]:
        q = (
            f'("{name}"[Title/Abstract] OR "{name}"[MeSH Terms]) '
            f'AND (diet OR food OR nutrition OR nutrient OR dietary) '
            f'AND (increase OR decrease OR reduce OR improve OR worsen) '
            f'AND {nutr_j} AND {base_filters}'
        )
        queries.append(GapQuery(
            entity=name, gap_type="biomarker_no_food", query=q, priority=2,
            hint=f"Biomarker {name} has no food link — find foods that affect it",
        ))

    # Priority 2 — Diseases with no biomarker
    for name in report.diseases_no_biomarker[:max_per_type]:
        q = (
            f'("{name}"[Title/Abstract] OR "{name}"[MeSH Terms]) '
            f'AND (biomarker OR "clinical marker" OR indicator OR HbA1c OR LDL OR CRP) '
            f'AND {med_j} AND {base_filters}'
        )
        queries.append(GapQuery(
            entity=name, gap_type="disease_no_biomarker", query=q, priority=2,
            hint=f"{name} has no biomarker links — find relevant biomarkers",
        ))

    # Priority 2 — Mechanisms with no food link
    for name in report.mechanisms_no_food[:max_per_type]:
        q = (
            f'("{name}"[Title/Abstract] OR "{name}"[MeSH Terms]) '
            f'AND (diet OR food OR nutrient OR dietary OR phytochemical) '
            f'AND (target OR modulate OR inhibit OR activate) '
            f'AND {nutr_j} AND {base_filters}'
        )
        queries.append(GapQuery(
            entity=name, gap_type="mechanism_no_food", query=q, priority=2,
            hint=f"Mechanism {name} has no food targeting — find dietary modulators",
        ))

    # Sort: priority ascending, then by entity name
    queries.sort(key=lambda q: (q.priority, q.entity))
    return queries


# ── Main entry point ──────────────────────────────────────────────────────────

def _load_demand_boost() -> set[str]:
    """Load top-demand entities from SQLite to boost their gap priority."""
    try:
        import sqlite3
        from pathlib import Path
        db_path = Path(__file__).resolve().parent.parent.parent / "data" / "health_map.db"
        if not db_path.exists():
            return set()
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT entity_name FROM query_demand
               GROUP BY entity_name ORDER BY SUM(count) DESC LIMIT 20"""
        ).fetchall()
        conn.close()
        return {r["entity_name"] for r in rows}
    except Exception:
        return set()


def analyze_kg_gaps(
    uri: str = "bolt://localhost:7687",
    user: str = "foodnot4self",
    pw: str = "foodnot4self",
    min_food_recs: int = 3,
    days_back: int = 730,
    max_per_type: int = 5,
) -> GapReport:
    """
    Full KG gap analysis: query Neo4j → generate targeted PubMed queries.
    Returns GapReport; generated_queries contains ready-to-use PubMed query strings.
    Demand-boosted: entities frequently queried by users get priority 0.
    """
    report = _run_gap_queries(uri, user, pw, min_food_recs)
    if report is None:
        return GapReport(as_of=datetime.now().strftime("%Y-%m-%d %H:%M"))

    demand_boost = _load_demand_boost()
    report.generated_queries = _build_queries(
        report, days_back=days_back, max_per_type=max_per_type,
        demand_boost=demand_boost,
    )
    return report


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="KG gap analyzer — identify missing data and generate targeted queries")
    parser.add_argument("--json", action="store_true", help="Output full report as JSON")
    parser.add_argument("--queries-only", action="store_true", help="Print only generated queries")
    args = parser.parse_args()

    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "foodnot4self")
    pw = os.getenv("NEO4J_PASSWORD", "foodnot4self")

    report = analyze_kg_gaps(uri=uri, user=user, pw=pw)

    if args.json:
        out = {
            "as_of": report.as_of,
            "conditions_no_food_recs": [{"name": n, "count": c} for n, c in report.conditions_no_food_recs],
            "conditions_no_avoidance": report.conditions_no_avoidance,
            "foods_no_nutrients": report.foods_no_nutrients,
            "nutrients_no_food": report.nutrients_no_food,
            "symptoms_no_early_signal": report.symptoms_no_early_signal,
            "biomarkers_no_food_link": report.biomarkers_no_food_link,
            "diseases_no_biomarker": report.diseases_no_biomarker,
            "mechanisms_no_food": report.mechanisms_no_food,
            "generated_queries": [
                {"entity": q.entity, "gap_type": q.gap_type, "priority": q.priority,
                 "hint": q.hint, "query": q.query}
                for q in report.generated_queries
            ],
        }
        print(json.dumps(out, indent=2))
        return

    if args.queries_only:
        for q in report.generated_queries:
            print(f"\n[P{q.priority}] {q.hint}")
            print(f"  {q.query}")
        return

    print(report.summary())
    print()
    print("Generated queries (sorted by priority):")
    for q in report.generated_queries:
        print(f"\n  [P{q.priority} | {q.gap_type}] {q.hint}")
        print(f"  {q.query[:120]}...")


if __name__ == "__main__":
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
    main()
