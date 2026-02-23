#!/usr/bin/env python3
"""
USDA FoodData Central fetch — optional data stream.
Fetches quantitative nutrient data (CONTAINS relationships with amounts) from USDA FDC.

Usage (from kg_pipeline/):
    python src/fetch_usda.py

Config (config.yaml):
    usda:
      enabled: false      # Set to true to enable
      max_foods: 5        # Max food searches per run
      api_key: ""         # Get free key at https://fdc.nal.usda.gov/api-guide.html

Output:
    data/usda_sample.json  — raw FDC search result for inspection

Note: This step is NOT wired into run_pipeline.py yet. Run manually to inspect output.
      Integrate into the pipeline once the schema for quantity-bearing CONTAINS triples is finalized.
"""
import json
import os
import sys
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.parse import urlencode
from urllib.error import HTTPError

# Run from kg_pipeline root
KG_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config_loader import get_paths_config

USDA_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"


def get_usda_config() -> dict:
    """Load usda config block from config.yaml."""
    try:
        import yaml
        cfg_path = KG_ROOT / "config.yaml"
        with open(cfg_path, "r") as f:
            cfg = yaml.safe_load(f)
        return cfg.get("usda", {})
    except Exception:
        return {}


def fetch_usda_food(query: str, api_key: str, page_size: int = 5) -> dict:
    """Call USDA FoodData Central search endpoint for one food query."""
    params = urlencode({
        "query": query,
        "pageSize": page_size,
        "api_key": api_key,
    })
    url = f"{USDA_SEARCH_URL}?{params}"
    req = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        print(f"USDA API HTTP error {e.code}: {e.reason}")
        return {}
    except Exception as e:
        print(f"USDA API error: {e}")
        return {}


def main():
    cfg = get_usda_config()

    if not cfg.get("enabled", False):
        print("USDA fetch is disabled (usda.enabled: false in config.yaml). Exiting.")
        print("To enable: set usda.enabled: true and usda.api_key in config.yaml.")
        sys.exit(0)

    api_key = cfg.get("api_key", "").strip()
    if not api_key:
        print("ERROR: usda.api_key is not set in config.yaml.")
        print("Get a free key at https://fdc.nal.usda.gov/api-guide.html")
        sys.exit(1)

    max_foods = cfg.get("max_foods", 5)
    # Sample queries — expand this list or read from a config field in the future
    sample_queries = ["salmon", "spinach", "olive oil", "broccoli", "almonds"][:max_foods]

    paths = get_paths_config()
    output_dir = KG_ROOT / paths.get("extracted_triples", "data/extracted_triples")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = KG_ROOT / "data" / "usda_sample.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    results = {}
    for query in sample_queries:
        print(f"Fetching USDA data for: {query}...")
        data = fetch_usda_food(query, api_key, page_size=3)
        foods = data.get("foods", [])
        # Keep only the fields useful for CONTAINS triples
        simplified = []
        for food in foods[:3]:
            simplified.append({
                "fdc_id": food.get("fdcId"),
                "description": food.get("description"),
                "food_nutrients": [
                    {
                        "nutrient_name": n.get("nutrientName"),
                        "unit": n.get("unitName"),
                        "amount": n.get("value"),
                    }
                    for n in food.get("foodNutrients", [])[:10]  # top 10 nutrients
                ],
            })
        results[query] = simplified
        print(f"  Got {len(simplified)} food(s) for '{query}'")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nUSDA sample written to: {output_path}")
    print("Next step: inspect the output, then design quantity-bearing CONTAINS triples for ingest.")


if __name__ == "__main__":
    main()
