"""
Quality-Aware Re-extraction — re-extracts high-priority papers with a stronger model.

Targets papers that:
  1. Match landmine disease keywords but yielded ≤2 triples
  2. Are associated with high-demand conditions from query_demand
  3. Had low evidence_strength scores

Re-extracts with Claude 3 Haiku via Bedrock for higher accuracy.
If the new extraction produces more valid triples or higher avg strength,
replaces the old triples in master_graph.json and re-ingests.

Usage:
    python src/reextract.py --dry-run        # show which papers would be re-extracted
    python src/reextract.py --limit 5        # re-extract up to 5 papers
    python src/reextract.py                  # re-extract all eligible papers (up to 20)
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Allow running from kg_pipeline/ or kg_pipeline/src/
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config_loader import get_paths_config, get_extract_config
from ontology import get_ontology_prompt_section, normalize_entity_type, normalize_entity_name, normalize_predicate
from triple_validator import validate_and_score
from consolidate_graph import consolidate_graph

# ── Landmine disease keywords ────────────────────────────────────────────────

_LANDMINE_KEYWORDS = {
    "alzheimer", "dementia", "cognitive decline", "stroke", "cerebrovascular",
    "pancreatic cancer", "pancreas", "chronic kidney disease", "ckd", "renal",
    "cardiovascular", "heart disease", "depression", "depressive",
    # Medical KG — biomarker and mechanism terms
    "hba1c", "ldl cholesterol", "hdl cholesterol", "c-reactive protein", "crp",
    "triglycerides", "fasting glucose", "egfr", "biomarker",
    "insulin resistance", "oxidative stress", "inflammation",
    "endothelial dysfunction", "neuroinflammation", "gut-brain axis",
    "drug interaction", "contraindication", "warfarin", "vitamin k interaction",
}


def _load_demand_entities() -> set[str]:
    """Load top-demand entities from SQLite."""
    try:
        import sqlite3
        db_path = Path(__file__).resolve().parent.parent.parent / "data" / "health_map.db"
        if not db_path.exists():
            return set()
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT entity_name FROM query_demand GROUP BY entity_name ORDER BY SUM(count) DESC LIMIT 20"
        ).fetchall()
        conn.close()
        return {r["entity_name"].lower() for r in rows}
    except Exception:
        return set()


def _is_high_priority(paper_data: dict, demand_entities: set[str]) -> bool:
    """Check if a paper is high-priority for re-extraction."""
    title = (paper_data.get("title") or "").lower()
    abstract = (paper_data.get("abstract") or "").lower()
    text = title + " " + abstract

    # Landmine disease match
    if any(kw in text for kw in _LANDMINE_KEYWORDS):
        return True

    # Demand entity match
    if any(ent in text for ent in demand_entities):
        return True

    return False


def _count_triples_for_paper(master_triples: list[dict], pmcid: str) -> tuple[int, float]:
    """Count triples and avg strength for a specific paper in master_graph."""
    paper_triples = [t for t in master_triples if str(t.get("source_id")) == str(pmcid)]
    if not paper_triples:
        return 0, 0.0
    strengths = [int(t.get("evidence_strength", 1)) for t in paper_triples]
    return len(paper_triples), sum(strengths) / len(strengths) if strengths else 0.0


def _extract_with_haiku(text: str, pmcid: str, region: str = "us-east-1") -> list[dict]:
    """Extract triples using Claude 3 Haiku via Bedrock."""
    try:
        from bedrock_extractor import extract_triples_bedrock
        prompt = _build_extraction_prompt(text, pmcid)
        return extract_triples_bedrock(
            prompt=prompt,
            model_id="anthropic.claude-3-haiku-20240307-v1:0",
            pmcid=pmcid,
            region=region,
        )
    except Exception as e:
        print(f"  Haiku extraction failed for PMC{pmcid}: {e}")
        return []


def _build_extraction_prompt(text: str, pmcid: str) -> str:
    ontology_section = get_ontology_prompt_section()
    return f"""You are an expert medical data extractor building a Knowledge Graph for a personalized health navigation application.
Extract structured relationships between entities from the provided medical text, using the ontology below.

{ontology_section}

Instructions:
1. Read the text carefully and extract ALL meaningful relationships.
2. Extract exact, concise entity names; use canonical forms (e.g. "Vitamin D" not "vitamin d", "Type 2 diabetes" for T2DM).
3. Use ONLY predicates from the Target Relationship Types list.
4. For early signals: Symptom -EARLY_SIGNAL_OF-> Disease for early signs. ALLEVIATES for foods that reduce, AGGRAVATES for foods that worsen.
5. Chain extraction: Food -CONTAINS-> Nutrient -AFFECTS/ALLEVIATES/AGGRAVATES-> Symptom/Disease.
6. Be thorough — extract every valid relationship the text supports.
7. Return a JSON array. Each object must have:
   - "subject", "subject_type", "predicate", "object", "object_type"
   - "context": short quote from the text
   - "source_id": "{pmcid}"
   - Optional "evidence_type": RCT, meta_analysis, observational, cohort, review, other

Text to analyze:
{text}"""


def find_reextraction_candidates(
    limit: int = 20,
    max_existing_triples: int = 2,
) -> list[dict]:
    """Find papers that are high-priority but have few triples."""
    paths = get_paths_config()
    raw_dir = paths["raw_papers"]
    master_path = paths.get("master_graph") or os.path.join(paths["extracted_triples"], "master_graph.json")

    # Load master graph
    master_triples = []
    if os.path.exists(master_path):
        with open(master_path, "r") as f:
            master_triples = json.load(f)

    demand_entities = _load_demand_entities()
    candidates = []

    paper_files = glob.glob(os.path.join(raw_dir, "*.json"))
    for fpath in paper_files:
        fname = os.path.basename(fpath)
        pmcid = fname.replace("PMC", "").replace(".json", "")

        try:
            with open(fpath, "r") as f:
                paper_data = json.load(f)
        except Exception:
            continue

        if not _is_high_priority(paper_data, demand_entities):
            continue

        triple_count, avg_strength = _count_triples_for_paper(master_triples, pmcid)

        if triple_count <= max_existing_triples:
            candidates.append({
                "pmcid": pmcid,
                "file_path": fpath,
                "title": (paper_data.get("title") or "")[:100],
                "current_triples": triple_count,
                "avg_strength": avg_strength,
            })

    # Sort by fewest triples first
    candidates.sort(key=lambda c: (c["current_triples"], -c.get("avg_strength", 0)))
    return candidates[:limit]


def reextract(limit: int = 20, dry_run: bool = False) -> dict:
    """Re-extract high-priority papers with Claude Haiku."""
    candidates = find_reextraction_candidates(limit=limit)

    if not candidates:
        print("No re-extraction candidates found.")
        return {"candidates": 0, "improved": 0}

    print(f"Found {len(candidates)} re-extraction candidates:")
    for c in candidates:
        print(f"  PMC{c['pmcid']}: {c['current_triples']} triples, "
              f"avg strength {c['avg_strength']:.1f} — {c['title']}")

    if dry_run:
        return {"candidates": len(candidates), "dry_run": True}

    paths = get_paths_config()
    master_path = paths.get("master_graph") or os.path.join(paths["extracted_triples"], "master_graph.json")

    # Load master graph
    master_triples = []
    if os.path.exists(master_path):
        with open(master_path, "r") as f:
            master_triples = json.load(f)

    region = get_extract_config().get("bedrock_region", "us-east-1")
    improved = 0

    for c in candidates:
        pmcid = c["pmcid"]
        fpath = c["file_path"]

        try:
            with open(fpath, "r") as f:
                paper_data = json.load(f)
        except Exception:
            continue

        # Build full text
        title = paper_data.get("title", "")
        abstract = paper_data.get("abstract", "")
        body = paper_data.get("body", "")
        text = f"Title: {title}\n\nAbstract:\n{abstract}"
        if body:
            text += f"\n\nBody:\n{body[:5000]}"

        print(f"\nRe-extracting PMC{pmcid}...")
        new_triples = _extract_with_haiku(text, pmcid, region=region)

        if not new_triples:
            print(f"  No triples from Haiku for PMC{pmcid}")
            continue

        # Normalize and validate
        valid_new = []
        for t in new_triples:
            t["subject_type"] = normalize_entity_type(t.get("subject_type", ""))
            t["object_type"] = normalize_entity_type(t.get("object_type", ""))
            t["predicate"] = normalize_predicate(t.get("predicate", ""))
            t["subject"] = normalize_entity_name(t.get("subject", ""))
            t["object"] = normalize_entity_name(t.get("object", ""))
            t["source_id"] = str(pmcid)
            t["journal"] = paper_data.get("journal", "")
            t["pub_date"] = paper_data.get("date", "")
            t["source_type"] = "PMC"
            if t.get("source_id") and t.get("subject") and t.get("object"):
                valid_new.append(t)

        new_count = len(valid_new)
        new_strengths = [int(t.get("evidence_strength", 1)) for t in valid_new]
        new_avg = sum(new_strengths) / len(new_strengths) if new_strengths else 0

        print(f"  Old: {c['current_triples']} triples (avg {c['avg_strength']:.1f})")
        print(f"  New: {new_count} triples (avg {new_avg:.1f})")

        # Replace if improvement
        if new_count > c["current_triples"] or (new_count == c["current_triples"] and new_avg > c["avg_strength"]):
            # Remove old triples for this paper
            master_triples = [t for t in master_triples if str(t.get("source_id")) != str(pmcid)]
            master_triples.extend(valid_new)
            improved += 1
            print(f"  Replaced with improved extraction.")
            # Also write the individual _triples.json so consolidate_graph preserves this improvement
            extracted_dir = paths["extracted_triples"]
            indiv_path = os.path.join(extracted_dir, f"PMC{pmcid}_triples.json")
            try:
                with open(indiv_path, "w") as f:
                    json.dump(valid_new, f, indent=2)
            except Exception as e:
                print(f"  Warning: could not write individual triples file: {e}")
        else:
            print(f"  No improvement — keeping original.")

    # Write back master graph
    if improved > 0:
        with open(master_path, "w") as f:
            json.dump(master_triples, f, indent=2)
        print(f"\nUpdated master_graph.json: {improved} papers improved.")

    return {"candidates": len(candidates), "improved": improved}


def main():
    parser = argparse.ArgumentParser(description="Quality-aware re-extraction with stronger model")
    parser.add_argument("--dry-run", action="store_true", help="Show candidates without re-extracting")
    parser.add_argument("--limit", type=int, default=20, help="Max papers to re-extract")
    args = parser.parse_args()

    reextract(limit=args.limit, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
