"""
fetch_fda_labels.py — FDA Drug Label data source via openFDA API.

Fetches drug labels containing food-drug interactions, contraindications, and
dietary warnings. Formats each label as a synthetic "paper" in raw_papers/ so
the existing extract_triples pipeline can mine drug-nutrient relationships.

Key sections extracted:
  - food_and_drug_interaction  → direct food-drug interaction evidence
  - drug_interactions          → broader interaction context
  - warnings_and_cautions      → dietary warnings, contraindications
  - contraindications          → absolute contraindications (e.g. grapefruit)

Source IDs use prefix FDA_ to distinguish from PMC papers in the KG.

Usage:
    python src/fetch_fda_labels.py
    python src/fetch_fda_labels.py --max-labels 500 --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config_loader import get_paths_config

FDA_API = "https://api.fda.gov/drug/label.json"

# Drug classes most relevant to nutrition / food interactions
_DRUG_CLASSES = [
    "warfarin",
    "metformin",
    "statin",
    "SSRI",
    "MAOI",
    "antihypertensive",
    "diuretic",
    "anticoagulant",
    "thyroid",
    "corticosteroid",
    "proton pump inhibitor",
    "ACE inhibitor",
    "beta blocker",
    "calcium channel blocker",
    "bisphosphonate",
    "tetracycline",
    "fluoroquinolone",
    "iron supplement",
    "potassium supplement",
    "vitamin K",
    "folic acid",
    "vitamin D",
    "vitamin B12",
    "zinc",
    "magnesium",
    "calcium",
]

# Sections to extract from each label
_SECTIONS = [
    "food_and_drug_interaction",
    "drug_interactions",
    "warnings_and_cautions",
    "contraindications",
    "dosage_and_administration",
]


# ── API helpers ───────────────────────────────────────────────────────────────

def _search_labels(search_term: str, limit: int = 100, skip: int = 0) -> list[dict]:
    """Query openFDA drug/label endpoint. Returns list of label records."""
    params = {
        "search": search_term,
        "limit":  min(limit, 100),
        "skip":   skip,
    }
    for attempt in range(3):
        try:
            r = requests.get(FDA_API, params=params, timeout=30)
            if r.status_code == 404:
                return []   # no results for this query
            if r.status_code == 429:
                wait = 15 * (2 ** attempt)
                print(f"  FDA rate limit. Waiting {wait}s...")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json().get("results", [])
        except Exception as e:
            if attempt == 2:
                print(f"  FDA API error for '{search_term}': {e}")
            time.sleep(5)
    return []


# ── Label → paper conversion ──────────────────────────────────────────────────

def _extract_text(label: dict, field: str) -> str:
    """Extract first string value from a label field (may be list or str)."""
    val = label.get(field)
    if not val:
        return ""
    if isinstance(val, list):
        return " ".join(str(v) for v in val if v).strip()
    return str(val).strip()


def _label_to_paper(label: dict, drug_class: str) -> dict | None:
    """Convert an FDA label record to raw_papers JSON format."""
    # Extract key identifiers
    openfda = label.get("openfda", {})
    brand   = (_extract_text(openfda, "brand_name")   or "").split(";")[0].strip()
    generic = (_extract_text(openfda, "generic_name") or "").split(";")[0].strip()
    appl    = (_extract_text(openfda, "application_number") or "").split(";")[0].strip()

    drug_name = brand or generic or drug_class
    if not drug_name:
        return None

    # Build a stable source_id from application number or name hash
    if appl:
        source_id = f"FDA_{appl.replace(' ', '_')}"
    else:
        h = hashlib.md5(drug_name.encode()).hexdigest()[:8]
        source_id = f"FDA_{drug_name[:20].replace(' ', '_')}_{h}"

    # Collect relevant text sections
    sections: list[str] = []
    for sec in _SECTIONS:
        text = _extract_text(label, sec)
        if text:
            label_name = sec.replace("_", " ").title()
            sections.append(f"{label_name}:\n{text}")

    if not sections:
        return None

    title    = f"{drug_name} — Drug-Nutrient Interactions and Dietary Warnings"
    abstract = "\n\n".join(sections)[:8000]  # cap at 8000 chars for extraction

    # Approval / effective date
    effective_date = _extract_text(label, "effective_time") or ""
    pub_date = ""
    if effective_date and len(effective_date) >= 8:
        try:
            pub_date = f"{effective_date[:4]}-{effective_date[4:6]}-{effective_date[6:8]}"
        except Exception:
            pub_date = effective_date[:10]

    return {
        "pmcid":             source_id,       # reuse pmcid field; source_id keeps FDA_ prefix
        "title":             title,
        "abstract":          abstract,
        "full_text_preview": "",
        "body":              "",
        "journal":           "FDA Drug Label",
        "date":              pub_date,
        "source_type":       "FDA",
        "source":            "fda_openlabels",
        "drug_class":        drug_class,
        "brand_name":        brand,
        "generic_name":      generic,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def run_fetch(max_labels: int = 100, dry_run: bool = False) -> int:
    """Fetch FDA drug labels. Returns count of new labels saved."""
    paths   = get_paths_config()
    raw_dir = paths["raw_papers"]
    os.makedirs(raw_dir, exist_ok=True)

    print(f"[fda_labels] Fetching drug labels for {len(_DRUG_CLASSES)} drug classes…")

    labels_per_class = max(1, min(max_labels // len(_DRUG_CLASSES), 50))
    saved = skipped = bad = 0

    for drug_class in _DRUG_CLASSES:
        # Search for labels containing food interactions for this drug class
        search = (
            f"(food_and_drug_interaction:{drug_class} "
            f"OR drug_interactions:{drug_class} "
            f"OR warnings_and_cautions:{drug_class})"
        )
        results = _search_labels(search, limit=labels_per_class)
        if not results:
            # Fallback: search by brand/generic name
            results = _search_labels(
                f"openfda.generic_name:{drug_class}",
                limit=labels_per_class,
            )

        for label in results:
            paper = _label_to_paper(label, drug_class)
            if not paper:
                bad += 1
                continue

            source_id = paper["pmcid"]
            out = os.path.join(raw_dir, f"{source_id}.json")

            if os.path.exists(out):
                skipped += 1
                continue

            if not dry_run:
                with open(out, "w", encoding="utf-8") as f:
                    json.dump(paper, f, indent=2, ensure_ascii=False)
            saved += 1

        time.sleep(0.3)   # be polite to FDA API

    print(f"[fda_labels] +{saved} new  ·  {skipped} existing  ·  {bad} skipped (no interaction data)")
    return saved


def main():
    parser = argparse.ArgumentParser(description="Fetch FDA drug label interactions")
    parser.add_argument("--max-labels", type=int, default=200,
                        help="Approx total labels to fetch (default: 200)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print counts without saving files")
    args = parser.parse_args()
    run_fetch(max_labels=args.max_labels, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
