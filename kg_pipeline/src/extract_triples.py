import os
import json
import glob
import time
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load environment variables (e.g., GEMINI_API_KEY)
load_dotenv()

# Initialize GenAI Client
# Ensure GEMINI_API_KEY is set in your environment
client = genai.Client()

def extract_triples_from_text(text, pmcid):
    """
    Uses Gemini to extract knowledge graph triples from medical text.
    """
    prompt = f"""
You are an expert medical data extractor building a Knowledge Graph for a personalized health navigation application.
Your goal is to extract structured relationships between entities from the provided medical text.

Target Entity Types:
- Disease
- Symptom
- Food
- Nutrient
- Drug/Treatment
- Lifestyle Factor

Target Relationship Types:
- PREVENTS (e.g., Nutrient -> PREVENTS -> Disease)
- CAUSES (e.g., Food -> CAUSES -> Disease)
- TREATS (e.g., Drug -> TREATS -> Disease)
- CONTAINS (e.g., Food -> CONTAINS -> Nutrient)
- AGGRAVATES (e.g., Food -> AGGRAVATES -> Symptom)
- REDUCES_RISK_OF (e.g., Lifestyle Factor -> REDUCES_RISK_OF -> Disease)

Instructions:
1. Read the text carefully.
2. Extract exact, concise entity names.
3. Determine the relationship between them based ONLY on the text.
4. Return a JSON array of objects, where each object has:
   - "subject": The source entity name
   - "subject_type": The type of the source entity
   - "predicate": The relationship (MUST be one of the Target Relationship Types)
   - "object": The target entity name
   - "object_type": The type of the target entity
   - "context": A short quote from the text that justifies this relationship.
   - "source_id": "{pmcid}"

If you find no relevant relationships, return an empty array [].

Text to analyze:
{text}
    """

    print(f"Sending extraction request to Gemini for {pmcid}...")
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-2.0-flash-lite',
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
    input_dir = "data/raw_papers"
    output_dir = "data/extracted_triples"
    os.makedirs(output_dir, exist_ok=True)
    
    # Process all JSON files in the raw_papers directory
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
             
        triples = extract_triples_from_text(text_to_analyze, pmcid)
        
        if triples:
            print(f"Extracted {len(triples)} triples from {pmcid}")
            all_triples.extend(triples)
            
            # Save individual extraction results
            output_file = os.path.join(output_dir, f"{pmcid}_triples.json")
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(triples, f, indent=4)
                
    # Save the consolidated graph data
    master_output = os.path.join(output_dir, "master_graph.json")
    with open(master_output, "w", encoding="utf-8") as f:
         json.dump(all_triples, f, indent=4)
         
    print(f"Successfully extracted {len(all_triples)} total relationships across {len(paper_files)} papers.")

if __name__ == "__main__":
    main()
