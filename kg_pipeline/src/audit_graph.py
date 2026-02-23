#!/usr/bin/env python3
"""
Gemini audit — classify a small sample of extracted triples for claim quality.
Detects overclaims in master_graph.json without touching Neo4j.

Usage (from kg_pipeline/, venv active):
    python src/audit_graph.py               # uses audit.sample_size from config (default 5)
    python src/audit_graph.py --n 10        # override sample size

Output:
    data/audit_report_sample.json  — JSON report with claim classification per triple

No Neo4j writes. Run manually after extraction to inspect claim quality before ingest.
"""
import argparse
import json
import os
import sys
from pathlib import Path

# Run from kg_pipeline root
KG_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config_loader import get_paths_config


def get_audit_config() -> dict:
    try:
        import yaml
        with open(KG_ROOT / "config.yaml", "r") as f:
            cfg = yaml.safe_load(f)
        return cfg.get("audit", {})
    except Exception:
        return {}


def classify_triples_with_gemini(triples: list, model: str) -> list:
    """Send triples to Gemini and ask it to classify each as strong/supportive/overclaim."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("GEMINI_API_KEY not set — cannot run audit. Set it in kg_pipeline/.env")
        return []

    try:
        from google import genai
        from google.genai import types
        from dotenv import load_dotenv
        load_dotenv(KG_ROOT / ".env")
        client = genai.Client(api_key=api_key)
    except ImportError:
        print("google-genai not installed. Run: pip install google-genai")
        return []

    triple_text = "\n".join(
        f"{i+1}. {t.get('subject')} --{t.get('predicate')}--> {t.get('object')} | context: {t.get('context', '')[:120]}"
        for i, t in enumerate(triples)
    )

    prompt = f"""You are a medical evidence quality reviewer.
Classify each claim below as one of:
- "strong": directly supported by the context; well-established in medicine.
- "supportive": plausible and consistent with the context but requires additional evidence.
- "overclaim": the context does not adequately support the claimed relationship; too speculative.

Return a JSON array where each object has:
  "index" (1-based), "classification" (strong|supportive|overclaim), "reason" (one sentence).

Claims to classify:
{triple_text}

Return ONLY the JSON array, no commentary.
"""

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Gemini audit error: {e}")
        return []


def main():
    ap = argparse.ArgumentParser(description="Gemini audit: classify sample triples for claim quality")
    ap.add_argument("--n", type=int, default=0, help="Override sample size (default: from config audit.sample_size)")
    args = ap.parse_args()

    cfg = get_audit_config()
    sample_size = args.n if args.n > 0 else cfg.get("sample_size", 5)
    model = cfg.get("model", "gemini-2.0-flash-lite")

    paths = get_paths_config()
    master_path_str = paths.get("master_graph") or os.path.join(paths["extracted_triples"], "master_graph.json")
    master_path = Path(master_path_str) if Path(master_path_str).is_absolute() else KG_ROOT / master_path_str

    if not master_path.exists():
        print(f"master_graph.json not found at {master_path}. Run the pipeline first.")
        sys.exit(1)

    with open(master_path, "r", encoding="utf-8") as f:
        all_triples = json.load(f)

    if not all_triples:
        print("No triples in master_graph.json.")
        sys.exit(0)

    # Take first N triples with non-empty context (better audit targets)
    candidates = [t for t in all_triples if t.get("context")]
    sample = candidates[:sample_size] if candidates else all_triples[:sample_size]
    print(f"Auditing {len(sample)} triples (model: {model})...")

    classifications = classify_triples_with_gemini(sample, model)

    # Build report: merge original triple with classification
    report = []
    for i, triple in enumerate(sample):
        entry = {
            "index": i + 1,
            "triple": {
                "subject": triple.get("subject"),
                "predicate": triple.get("predicate"),
                "object": triple.get("object"),
                "source_id": triple.get("source_id"),
                "context": triple.get("context", "")[:200],
            },
            "classification": None,
            "reason": None,
        }
        # Match by index from Gemini response
        for c in classifications:
            if c.get("index") == i + 1:
                entry["classification"] = c.get("classification")
                entry["reason"] = c.get("reason")
                break
        report.append(entry)

    # Summary counts
    counts = {"strong": 0, "supportive": 0, "overclaim": 0, "unclassified": 0}
    for entry in report:
        key = entry.get("classification") or "unclassified"
        counts[key] = counts.get(key, 0) + 1

    output = {
        "model": model,
        "sample_size": len(sample),
        "summary": counts,
        "triples": report,
    }

    output_path = KG_ROOT / "data" / "audit_report_sample.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\nAudit complete. Summary: {counts}")
    print(f"Report written to: {output_path}")
    overclaims = [e for e in report if e.get("classification") == "overclaim"]
    if overclaims:
        print(f"\n{len(overclaims)} overclaim(s) detected:")
        for e in overclaims:
            t = e["triple"]
            print(f"  [{e['index']}] {t['subject']} --{t['predicate']}--> {t['object']}: {e['reason']}")


if __name__ == "__main__":
    main()
