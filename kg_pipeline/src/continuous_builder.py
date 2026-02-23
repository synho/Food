"""
Continuous KG builder — slow, Gemini-quota-safe pipeline.
Per-cycle flow:
  1. run_smart_fetch() to download new papers
  2. Find unextracted paper files, take papers_per_run newest
  3. extract_one_paper() for each, sleep extract_delay_sec between calls
  4. consolidate_graph() → rebuild master_graph.json
  5. Ingest via KnowledgeGraphIngestor

Usage:
    python src/continuous_builder.py                           # full cycle
    python src/continuous_builder.py --skip-fetch              # extract + ingest only
    python src/continuous_builder.py --skip-ingest             # fetch + extract only
    python src/continuous_builder.py --clusters sarcopenia,cognitive

Cron (every 2 hours):
    0 */2 * * * cd /path/to/kg_pipeline && source venv/bin/activate && python src/continuous_builder.py >> logs/cb.log 2>&1
"""
import argparse
import glob
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# Ensure src/ is on path when running directly
sys.path.insert(0, str(Path(__file__).resolve().parent))

load_dotenv()

from config_loader import get_paths_config, get_continuous_build_config, get_extract_config
from ontology import normalize_entity_type, normalize_entity_name, normalize_predicate
from artifacts import AGENT_INGEST, AGENT_EXTRACT, get_run_id, write_manifest
from consolidate_graph import consolidate_graph
from smart_fetch import run_smart_fetch
from extract_triples import (
    extract_triples_from_text,
    _parse_gemini_retry_delay,
    _demo_triples_from_paper,
    DEMO_MODE,
)


# ── Single-paper extraction ───────────────────────────────────────────────────

def extract_one_paper(
    file_path: str,
    output_dir: str,
    cb_cfg: dict,
) -> tuple[str, list[dict], str]:
    """
    Extract triples from one paper file.
    Returns (pmcid, triples, status).
    status: 'ok' | 'skipped_existing' | 'skipped_no_text' | 'skipped_quota_exceeded' | 'error'
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            article_data = json.load(f)
    except Exception as e:
        print(f"  Error reading {file_path}: {e}")
        return ("unknown", [], "error")

    pmcid = article_data.get("pmcid", "Unknown")
    output_file = os.path.join(output_dir, f"{pmcid}_triples.json")

    # Skip already extracted
    if os.path.exists(output_file):
        with open(output_file, "r", encoding="utf-8") as ef:
            existing = json.load(ef)
        return (pmcid, existing, "skipped_existing")

    # Text selection
    text = article_data.get("abstract", "")
    if len(text) < 100:
        text = article_data.get("full_text_preview", "")
    if not text:
        print(f"  Skipping {pmcid} — no text.")
        return (pmcid, [], "skipped_no_text")

    journal = article_data.get("journal", "")
    pub_date = article_data.get("date", "")

    if DEMO_MODE:
        triples = _demo_triples_from_paper(article_data, pmcid)
    else:
        max_retries = cb_cfg.get("max_retries", 3)
        use_retry_after = cb_cfg.get("use_api_retry_after", True)
        max_wait = cb_cfg.get("max_wait_sec", 120)

        triples = []
        for attempt in range(max_retries):
            try:
                raw = extract_triples_from_text(text, pmcid)
                if raw is not None:
                    triples = raw
                break
            except Exception as e:
                err_str = str(e)
                if "429" in err_str:
                    wait = _parse_gemini_retry_delay(e) if use_retry_after else 65
                    if wait > max_wait:
                        print(f"  Quota exceeded for {pmcid} (wait={wait}s > max={max_wait}s). Skipping.")
                        return (pmcid, [], "skipped_quota_exceeded")
                    print(f"  Rate limit ({pmcid}). Waiting {wait}s (attempt {attempt+1}/{max_retries})...")
                    time.sleep(wait)
                else:
                    print(f"  Extraction error for {pmcid}: {e}")
                    return (pmcid, [], "error")

    # Normalise and annotate
    for t in triples:
        t["journal"] = journal
        t["pub_date"] = pub_date
        t["subject_type"] = normalize_entity_type(t.get("subject_type", ""))
        t["object_type"] = normalize_entity_type(t.get("object_type", ""))
        t["predicate"] = normalize_predicate(t.get("predicate", ""))
        t["subject"] = normalize_entity_name(t.get("subject", ""), t.get("subject_type", ""))
        t["object"] = normalize_entity_name(t.get("object", ""), t.get("object_type", ""))
        t["source_type"] = t.get("source_type") or "PMC"
        t["evidence_type"] = (t.get("evidence_type") or "").strip()

    # Write per-paper file (idempotent on next run)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(triples, f, indent=4)

    print(f"  Extracted {len(triples)} triples from {pmcid}.")
    return (pmcid, triples, "ok")


# ── Main cycle ────────────────────────────────────────────────────────────────

def run_continuous_build(
    skip_fetch: bool = False,
    skip_ingest: bool = False,
    requested_clusters: list[str] | None = None,
) -> None:
    paths = get_paths_config()
    cb_cfg = get_continuous_build_config()
    raw_dir = paths["raw_papers"]
    extracted_dir = paths["extracted_triples"]
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(extracted_dir, exist_ok=True)

    papers_per_run = cb_cfg.get("papers_per_run", 3)
    delay_sec = cb_cfg.get("extract_delay_sec", 45)

    # ── Step 1: Smart fetch ───────────────────────────────────────────────────
    if not skip_fetch:
        print("=== Step 1: Smart fetch ===")
        run_smart_fetch(requested_clusters=requested_clusters)
    else:
        print("=== Step 1: Smart fetch skipped ===")

    # ── Step 2: Find unextracted papers ───────────────────────────────────────
    print("\n=== Step 2: Finding unextracted papers ===")
    all_paper_files = glob.glob(os.path.join(raw_dir, "*.json"))

    def is_unextracted(fp: str) -> bool:
        base = os.path.basename(fp)  # e.g. PMC12345.json
        pmcid = base.replace(".json", "")  # e.g. PMC12345
        return not os.path.exists(os.path.join(extracted_dir, f"{pmcid}_triples.json"))

    unextracted = [f for f in all_paper_files if is_unextracted(f)]
    # Newest first
    unextracted.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    to_process = unextracted[:papers_per_run]

    print(f"Found {len(unextracted)} unextracted papers; processing {len(to_process)} this run.")

    # ── Step 3: Extract papers one by one ────────────────────────────────────
    print("\n=== Step 3: Extracting triples ===")
    all_new_triples: list[dict] = []
    processed_pmcids: list[str] = []

    for i, fp in enumerate(to_process, 1):
        print(f"\n[{i}/{len(to_process)}] {os.path.basename(fp)}")
        pmcid, triples, status = extract_one_paper(fp, extracted_dir, cb_cfg)
        processed_pmcids.append(pmcid)
        all_new_triples.extend(triples)

        if status == "ok" and delay_sec > 0 and i < len(to_process):
            print(f"  Sleeping {delay_sec}s before next paper...")
            time.sleep(delay_sec)

    print(f"\nExtracted {len(all_new_triples)} new triples from {len(to_process)} papers.")

    if not to_process:
        print("Nothing new to extract. Skipping consolidate + ingest.")
        return

    # ── Step 4: Consolidate master graph ──────────────────────────────────────
    print("\n=== Step 4: Consolidating graph ===")
    master_path = consolidate_graph()

    # ── Step 5: Ingest to Neo4j ───────────────────────────────────────────────
    if skip_ingest:
        print("\n=== Step 5: Ingest skipped ===")
        return

    print("\n=== Step 5: Ingesting to Neo4j ===")
    from ingest_to_neo4j import KnowledgeGraphIngestor

    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "foodnot4self")
    neo4j_pw = os.getenv("NEO4J_PASSWORD", "foodnot4self")

    with open(master_path, "r", encoding="utf-8") as f:
        all_triples = json.load(f)

    run_id = get_run_id()
    try:
        ingestor = KnowledgeGraphIngestor(neo4j_uri, neo4j_user, neo4j_pw)
        ingestor.setup_schema()
        ingestor.ingest_triples(all_triples)
        ingestor.close()
        write_manifest(AGENT_INGEST, run_id, {
            "triples_ingested": len(all_triples),
            "papers_processed": processed_pmcids,
            "master_graph_path": master_path,
            "status": "ok",
        })
        print(f"Ingestion complete: {len(all_triples)} total triples in Neo4j.")
    except Exception as e:
        write_manifest(AGENT_INGEST, run_id, {"status": "error", "error": str(e)})
        print(f"Ingest failed: {e}")
        print("Tip: Set NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD in .env")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Continuous KG builder")
    parser.add_argument("--skip-fetch", action="store_true", help="Skip smart fetch step")
    parser.add_argument("--skip-ingest", action="store_true", help="Skip Neo4j ingest step")
    parser.add_argument(
        "--clusters",
        type=str,
        default="",
        help="Comma-separated clusters for smart fetch (e.g. sarcopenia,cognitive)",
    )
    args = parser.parse_args()

    requested = [c.strip() for c in args.clusters.split(",") if c.strip()] or None
    run_continuous_build(
        skip_fetch=args.skip_fetch,
        skip_ingest=args.skip_ingest,
        requested_clusters=requested,
    )


if __name__ == "__main__":
    main()
