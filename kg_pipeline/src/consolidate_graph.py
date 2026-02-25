import json
import glob
import os

from config_loader import get_paths_config
from ontology import normalize_entity_type, normalize_entity_name, normalize_predicate
from triple_validator import validate_and_score, report as validator_report


def consolidate_graph() -> str:
    """
    Read all *_triples.json files, re-normalize and validate, then write master_graph.json.
    This is the single authoritative writer of master_graph — extract_triples delegates here
    so incremental runs accumulate all prior batches.
    Only valid triples (ontology-compliant, with evidence) make it to the master graph.
    Returns the output file path.
    """
    paths = get_paths_config()
    input_dir = paths["extracted_triples"]
    output_file = paths.get("master_graph") or os.path.join(input_dir, "master_graph.json")

    all_triples = []

    # Find all triple files except the master itself
    triple_files = glob.glob(os.path.join(input_dir, "*_triples.json"))

    for file_path in triple_files:
        with open(file_path, "r") as f:
            data = json.load(f)
            if isinstance(data, list):
                # Re-normalize through current ontology
                for t in data:
                    t["subject_type"] = normalize_entity_type(t.get("subject_type", ""))
                    t["object_type"] = normalize_entity_type(t.get("object_type", ""))
                    t["predicate"] = normalize_predicate(t.get("predicate", ""))
                    t["subject"] = normalize_entity_name(t.get("subject", ""), t.get("subject_type", ""))
                    t["object"] = normalize_entity_name(t.get("object", ""), t.get("object_type", ""))
                all_triples.extend(data)

    # Validate: only ontology-compliant triples with evidence make it to master graph
    valid, rejected, stats = validate_and_score(all_triples)
    print(validator_report(stats))
    if rejected:
        print(f"  Filtered out {len(rejected)} low-quality triples from master graph.")

    with open(output_file, "w") as f:
        json.dump(valid, f, indent=2)

    print(f"Consolidated {len(valid)} valid triples from {len(triple_files)} files into {output_file}")
    return output_file

if __name__ == "__main__":
    consolidate_graph()
