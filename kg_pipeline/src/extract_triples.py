import os
import json
import glob
import time
from dotenv import load_dotenv

from config_loader import get_paths_config, get_extract_config, get_continuous_build_config
from ontology import get_ontology_prompt_section, normalize_entity_type, normalize_entity_name, normalize_predicate
from artifacts import AGENT_EXTRACT, get_run_id, read_manifest, write_manifest
from consolidate_graph import consolidate_graph

load_dotenv()

# ── Backend selection ─────────────────────────────────────────────────────────
# If extract.model starts with "bedrock/", use Bedrock; otherwise use Gemini.
# Bedrock models: bedrock/amazon.nova-micro-v1:0  (cheapest)
#                 bedrock/amazon.nova-lite-v1:0   (balanced)
#                 bedrock/anthropic.claude-3-haiku-20240307-v1:0 (highest accuracy)

_extract_cfg = get_extract_config()
_model_setting = _extract_cfg.get("model", "gemini-2.0-flash-lite")
_USE_BEDROCK = _model_setting.startswith("bedrock/")
_BEDROCK_MODEL_ID = _model_setting[len("bedrock/"):] if _USE_BEDROCK else ""
_BEDROCK_REGION = _extract_cfg.get("bedrock_region", "us-east-1")

if _USE_BEDROCK:
    from bedrock_extractor import extract_triples_bedrock, get_recommended_delay
    client = None
    DEMO_MODE = False
    print(f"Using AWS Bedrock backend: {_BEDROCK_MODEL_ID} (region: {_BEDROCK_REGION})")
else:
    try:
        from google import genai
        from google.genai import types
        _api_key = os.getenv("GEMINI_API_KEY", "").strip()
        DEMO_MODE = not bool(_api_key)
        if DEMO_MODE:
            client = None
            print("GEMINI_API_KEY not set: running in DEMO mode (minimal triples from abstracts, no LLM).")
        else:
            client = genai.Client(api_key=_api_key)
    except ImportError:
        client = None
        DEMO_MODE = True
        print("google-genai not installed and no Bedrock model configured: running in DEMO mode.")


def _demo_triples_from_paper(article_data, pmcid):
    """Produce minimal valid triples when API key is missing (zero-error: source_id, pub_date)."""
    journal = article_data.get("journal", "")
    pub_date = article_data.get("date", "")
    title = (article_data.get("title") or "Unknown")[:200]
    abstract = (article_data.get("abstract") or "")[:500]
    # One triple per paper: Paper DOCUMENTS Topic (placeholder for validation)
    return [{
        "subject": title,
        "subject_type": "Publication",
        "predicate": "DOCUMENTS",
        "object": "nutrition and diet" if abstract else "medical research",
        "object_type": "Topic",
        "context": abstract[:200] if abstract else f"PMC{pmcid}",
        "source_id": str(pmcid),
        "journal": journal,
        "pub_date": pub_date,
        "source_type": "PMC",
    }]


def _parse_gemini_retry_delay(exc, default_sec: int = 65, max_sec: int = 120) -> int:
    """
    Parse the retryDelay from a Gemini rate-limit exception.
    Falls back to default_sec if parsing fails.
    """
    try:
        details = exc.details.get("error", {}).get("details", [])
        for item in details:
            if "retryDelay" in item:
                return min(int(str(item["retryDelay"]).rstrip("s")), max_sec)
    except Exception:
        pass
    return default_sec


def _build_extraction_prompt(text: str, pmcid: str) -> str:
    ontology_section = get_ontology_prompt_section()
    return f"""You are an expert medical data extractor building a Knowledge Graph for a personalized health navigation application.
Extract structured relationships between entities from the provided medical text, using the ontology below.

{ontology_section}

Instructions:
1. Read the text carefully.
2. Extract exact, concise entity names; use canonical forms where possible (e.g. "Vitamin D" not "vitamin d", "Type 2 diabetes" for T2DM). Assign subject_type and object_type ONLY from the Target Entity Types list.
3. Use ONLY predicates from the Target Relationship Types list (e.g. PREVENTS, TREATS, CONTAINS, ALLEVIATES, AGGRAVATES, REDUCES_RISK_OF, EARLY_SIGNAL_OF, SUBSTITUTES_FOR, COMPLEMENTS_DRUG where the text supports them).
4. Early signals: When the text describes early signs or symptoms of a disease, extract Symptom -EARLY_SIGNAL_OF-> Disease. When it describes foods/nutrients that reduce a symptom, use ALLEVIATES; when they worsen a symptom, use AGGRAVATES (so we can recommend "foods that reduce" vs "foods to avoid" for user safety).
5. Chain extraction: When possible, emit the explicit chain: Food -CONTAINS-> Nutrient -AFFECTS/ALLEVIATES/AGGRAVATES-> Symptom/Disease, so the evidence trail is explicit and the KG can answer "why is this food good/bad for me?" via the nutrient mechanism.
6. Return a JSON array of objects. Each object must have:
   - "subject", "subject_type", "predicate", "object", "object_type"
   - "context": short quote from the text justifying this relationship
   - "source_id": "{pmcid}"
   - Optional "evidence_type": if the study design is clear, one of: RCT, meta_analysis, observational, cohort, review, other (for evidence strength; leave empty if unclear).

Do not add "journal" or "pub_date"; they will be added from article metadata.
If you find no relevant relationships, return an empty array [].

Text to analyze:
{text}"""


def extract_triples_from_text(text, pmcid):
    """
    Extract KG triples from medical text using the configured backend (Bedrock or Gemini).
    """
    if DEMO_MODE or (not _USE_BEDROCK and client is None):
        return []

    prompt = _build_extraction_prompt(text, pmcid)

    # ── Bedrock backend ───────────────────────────────────────────────────────
    if _USE_BEDROCK:
        return extract_triples_bedrock(
            prompt=prompt,
            model_id=_BEDROCK_MODEL_ID,
            pmcid=pmcid,
            region=_BEDROCK_REGION,
        )

    # ── Gemini backend ────────────────────────────────────────────────────────
    model = get_extract_config().get("model", "gemini-2.0-flash-lite")
    print(f"Sending extraction request to Gemini ({model}) for {pmcid}...")
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )
            return json.loads(response.text)
        except Exception as e:
            if "429" in str(e):
                wait = _parse_gemini_retry_delay(e)
                print(f"Rate limit hit for {pmcid}. Retrying in {wait}s... (Attempt {attempt+1}/{max_retries})")
                time.sleep(wait)
                continue
            print(f"Error during Gemini extraction for {pmcid}: {e}")
            return []
    return []

def main():
    paths = get_paths_config()
    input_dir = paths["raw_papers"]
    output_dir = paths["extracted_triples"]
    os.makedirs(output_dir, exist_ok=True)

    paper_files = glob.glob(os.path.join(input_dir, "*.json"))
    
    if not paper_files:
        print(f"No papers found in {input_dir}. Run fetch_papers.py first.")
        return

    all_triples = []
    cb_cfg = get_continuous_build_config()
    if _USE_BEDROCK:
        # Bedrock has much higher rate limits; use model-specific recommended delay
        inter_paper_delay = get_recommended_delay(_BEDROCK_MODEL_ID)
    else:
        inter_paper_delay = cb_cfg.get("extract_delay_sec", 0)

    for idx, file_path in enumerate(paper_files, 1):
        with open(file_path, "r", encoding="utf-8") as f:
            article_data = json.load(f)

        pmcid = article_data.get("pmcid", "Unknown")
        print(f"[{idx}/{len(paper_files)}] Processing {pmcid}...")

        # Skip already-extracted papers (idempotent across runs)
        output_file = os.path.join(output_dir, f"{pmcid}_triples.json")
        if os.path.exists(output_file):
            with open(output_file, "r", encoding="utf-8") as ef:
                existing = json.load(ef)
            all_triples.extend(existing)
            print(f"  Skipping {pmcid} (already extracted, {len(existing)} triples cached).")
            continue
        
        # We will use the abstract for the primary extraction as it usually contains the core findings
        # If abstract is missing/short, fallback to full_text_preview
        text_to_analyze = article_data.get("abstract", "")
        if len(text_to_analyze) < 100:
             text_to_analyze = article_data.get("full_text_preview", "")
             
        if not text_to_analyze:
             print(f"Skipping {pmcid} - No text to analyze.")
             continue

        if DEMO_MODE:
            triples = _demo_triples_from_paper(article_data, pmcid)
        else:
            triples = extract_triples_from_text(text_to_analyze, pmcid)
        
        if triples:
            journal = article_data.get("journal", "")
            pub_date = article_data.get("date", "")
            for t in triples:
                t["journal"] = journal
                t["pub_date"] = pub_date
                # Normalize to ontology labels for Neo4j
                t["subject_type"] = normalize_entity_type(t.get("subject_type", ""))
                t["object_type"] = normalize_entity_type(t.get("object_type", ""))
                t["predicate"] = normalize_predicate(t.get("predicate", ""))
                # Canonical entity names (e.g. Vitamin D, Type 2 diabetes)
                t["subject"] = normalize_entity_name(t.get("subject", ""), t.get("subject_type", ""))
                t["object"] = normalize_entity_name(t.get("object", ""), t.get("object_type", ""))
                t["source_type"] = t.get("source_type") or "PMC"
                t["evidence_type"] = (t.get("evidence_type") or "").strip() or ""
            print(f"Extracted {len(triples)} triples from {pmcid}")
            all_triples.extend(triples)
            
            # Save individual extraction results
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(triples, f, indent=4)

        # Pause between Gemini calls to respect rate limits
        if inter_paper_delay > 0 and not DEMO_MODE and idx < len(paper_files):
            print(f"  Waiting {inter_paper_delay}s before next paper...")
            time.sleep(inter_paper_delay)

    # Consolidate ALL *_triples.json (including prior batches) into master_graph.json.
    # consolidate_graph is the single master writer — avoids incomplete master on incremental runs.
    master_output = consolidate_graph()

    run_id = get_run_id()
    papers_processed = [os.path.splitext(os.path.basename(p))[0] for p in paper_files]
    write_manifest(AGENT_EXTRACT, run_id, {
        "papers_processed": papers_processed,
        "total_triples": len(all_triples),
        "master_graph_path": master_output,
    })
    print(f"Successfully extracted {len(all_triples)} total relationships across {len(paper_files)} papers.")

if __name__ == "__main__":
    main()
