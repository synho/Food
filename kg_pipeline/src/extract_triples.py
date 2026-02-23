import os
import json
import glob
import time
from google import genai
from google.genai import types
from dotenv import load_dotenv

from config_loader import get_paths_config, get_extract_config
from ontology import get_ontology_prompt_section, normalize_entity_type, normalize_entity_name, normalize_predicate
from artifacts import AGENT_EXTRACT, get_run_id, read_manifest, write_manifest
from consolidate_graph import consolidate_graph

load_dotenv()

# Initialize GenAI Client (optional: demo mode when GEMINI_API_KEY is missing)
_api_key = os.getenv("GEMINI_API_KEY", "").strip()
DEMO_MODE = not bool(_api_key)
if DEMO_MODE:
    client = None
    print("GEMINI_API_KEY not set: running in DEMO mode (minimal triples from abstracts, no LLM).")
else:
    client = genai.Client(api_key=_api_key)


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


def extract_triples_from_text(text, pmcid):
    """
    Uses Gemini to extract knowledge graph triples from medical text.
    """
    ontology_section = get_ontology_prompt_section()
    prompt = f"""
You are an expert medical data extractor building a Knowledge Graph for a personalized health navigation application.
Extract structured relationships between entities from the provided medical text, using the ontology below.

{ontology_section}

Instructions:
1. Read the text carefully.
2. Extract exact, concise entity names; use canonical forms where possible (e.g. "Vitamin D" not "vitamin d", "Type 2 diabetes" for T2DM). Assign subject_type and object_type ONLY from the Target Entity Types list.
3. Use ONLY predicates from the Target Relationship Types list (e.g. PREVENTS, TREATS, CONTAINS, ALLEVIATES, AGGRAVATES, REDUCES_RISK_OF, EARLY_SIGNAL_OF, SUBSTITUTES_FOR, COMPLEMENTS_DRUG where the text supports them).
4. Early signals: When the text describes early signs or symptoms of a disease, extract Symptom -EARLY_SIGNAL_OF-> Disease. When it describes foods/nutrients that reduce a symptom, use ALLEVIATES; when they worsen a symptom, use AGGRAVATES (so we can recommend "foods that reduce" vs "foods to avoid" for user safety).
5. Return a JSON array of objects. Each object must have:
   - "subject", "subject_type", "predicate", "object", "object_type"
   - "context": short quote from the text justifying this relationship
   - "source_id": "{pmcid}"
   - Optional "evidence_type": if the study design is clear, one of: RCT, meta_analysis, observational, cohort, review, other (for evidence strength; leave empty if unclear).

Do not add "journal" or "pub_date"; they will be added from article metadata.
If you find no relevant relationships, return an empty array [].

Text to analyze:
{text}
    """

    if DEMO_MODE or client is None:
        return []
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
                print(f"Rate limit hit for {pmcid}. Retrying in 65 seconds... (Attempt {attempt+1}/{max_retries})")
                time.sleep(65)
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
    
    for file_path in paper_files:
        with open(file_path, "r", encoding="utf-8") as f:
            article_data = json.load(f)
            
        pmcid = article_data.get("pmcid", "Unknown")
        print(f"Processing {pmcid}...")
        
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
            output_file = os.path.join(output_dir, f"{pmcid}_triples.json")
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(triples, f, indent=4)
                
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
