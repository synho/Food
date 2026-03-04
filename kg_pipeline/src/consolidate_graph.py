import json
import glob
import os
import re

from config_loader import get_paths_config
from ontology import normalize_entity_type, normalize_entity_name, normalize_predicate
from triple_validator import validate_and_score, report as validator_report


# ── Evidence type inference from context keywords ─────────────────────────────
_EVIDENCE_TYPE_PATTERNS = [
    (r"\bmeta[\-\s]?analysis\b", "meta-analysis"),
    (r"\bsystematic[\s_]review\b", "systematic review"),
    (r"\brandomized[\s_]controlled[\s_]trial\b", "RCT"),
    (r"\brandomised[\s_]controlled[\s_]trial\b", "RCT"),
    (r"\b(?:double|single)[\-\s]blind\b", "RCT"),
    (r"\bplacebo[\-\s]controlled\b", "RCT"),
    (r"\bprospective[\s_]cohort\b", "prospective cohort"),
    (r"\bretrospective[\s_]cohort\b", "retrospective cohort"),
    (r"\bcohort[\s_]study\b", "cohort"),
    (r"\bcross[\-\s]sectional\b", "cross-sectional"),
    (r"\bcase[\-\s]control\b", "case-control"),
    (r"\bobservational[\s_]study\b", "observational"),
    (r"\breview\b", "review"),
]


def _infer_evidence_type(context: str) -> str | None:
    """Infer evidence type from context keywords. Returns None if no match."""
    if not context:
        return None
    text = context.lower()
    for pattern, etype in _EVIDENCE_TYPE_PATTERNS:
        if re.search(pattern, text):
            return etype
    return None


def _backfill_metadata(triples: list[dict], raw_papers_dir: str) -> dict:
    """Backfill empty journal and evidence_type fields.

    For journal: look up data/raw_papers/PMC{source_id}.json and copy journal field.
    For evidence_type: infer from context keywords, tag with evidence_type_source: "inferred".

    Returns stats dict.
    """
    stats = {"journal_backfilled": 0, "evidence_type_inferred": 0}

    # Build source_id → journal cache from raw papers
    journal_cache: dict[str, str] = {}
    if os.path.isdir(raw_papers_dir):
        for fname in os.listdir(raw_papers_dir):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(raw_papers_dir, fname)
            try:
                with open(fpath, "r") as f:
                    paper = json.load(f)
                sid = paper.get("pmcid") or paper.get("source_id") or ""
                journal = (paper.get("journal") or "").strip()
                if sid and journal:
                    journal_cache[sid.strip()] = journal
            except (json.JSONDecodeError, OSError):
                continue

    for t in triples:
        # Backfill journal
        journal = (t.get("journal") or "").strip()
        if not journal:
            sid = (t.get("source_id") or "").strip()
            cached_journal = journal_cache.get(sid)
            if cached_journal:
                t["journal"] = cached_journal
                stats["journal_backfilled"] += 1

        # Backfill evidence_type
        evidence_type = (t.get("evidence_type") or "").strip()
        if not evidence_type:
            inferred = _infer_evidence_type(t.get("context", ""))
            if inferred:
                t["evidence_type"] = inferred
                t["evidence_type_source"] = "inferred"
                stats["evidence_type_inferred"] += 1

    return stats


def consolidate_graph() -> str:
    """
    Read all *_triples.json files, re-normalize and validate, then write master_graph.json.
    This is the single authoritative writer of master_graph — extract_triples delegates here
    so incremental runs accumulate all prior batches.
    Only valid triples (ontology-compliant, with evidence) make it to the master graph.
    Rejected triples are saved to rejected_triples.json for debugging.
    Returns the output file path.
    """
    paths = get_paths_config()
    input_dir = paths["extracted_triples"]
    output_file = paths.get("master_graph") or os.path.join(input_dir, "master_graph.json")
    rejected_file = os.path.join(input_dir, "rejected_triples.json")
    raw_papers_dir = paths.get("raw_papers", "data/raw_papers")

    all_triples = []

    # Find all triple files except the master itself and the rejected file
    triple_files = glob.glob(os.path.join(input_dir, "*_triples.json"))
    triple_files = [f for f in triple_files if not f.endswith("master_graph.json")
                    and not f.endswith("rejected_triples.json")]

    for file_path in triple_files:
        with open(file_path, "r") as f:
            data = json.load(f)
            if isinstance(data, list):
                # Re-normalize through current ontology
                for t in data:
                    subject_type = normalize_entity_type(t.get("subject_type", ""))
                    object_type = normalize_entity_type(t.get("object_type", ""))
                    # If normalize_entity_type returns None, the type is rejected
                    if subject_type is None or object_type is None:
                        t["subject_type"] = subject_type or "Thing"
                        t["object_type"] = object_type or "Thing"
                    else:
                        t["subject_type"] = subject_type
                        t["object_type"] = object_type
                    t["predicate"] = normalize_predicate(t.get("predicate", ""))
                    t["subject"] = normalize_entity_name(t.get("subject", ""), t.get("subject_type", ""))
                    t["object"] = normalize_entity_name(t.get("object", ""), t.get("object_type", ""))
                all_triples.extend(data)

    # Backfill metadata before validation
    backfill_stats = _backfill_metadata(all_triples, raw_papers_dir)
    if backfill_stats["journal_backfilled"] or backfill_stats["evidence_type_inferred"]:
        print(f"Metadata backfill: {backfill_stats['journal_backfilled']} journals filled, "
              f"{backfill_stats['evidence_type_inferred']} evidence_types inferred")

    # Validate: only ontology-compliant triples with evidence make it to master graph
    valid, rejected, stats = validate_and_score(all_triples)
    print(validator_report(stats))
    if rejected:
        print(f"  Filtered out {len(rejected)} low-quality triples from master graph.")

    with open(output_file, "w") as f:
        json.dump(valid, f, indent=2)

    # Save rejected triples for debugging
    if rejected:
        with open(rejected_file, "w") as f:
            json.dump(rejected, f, indent=2)
        print(f"  Rejected triples saved to {rejected_file}")

    print(f"Consolidated {len(valid)} valid triples from {len(triple_files)} files into {output_file}")
    return output_file

if __name__ == "__main__":
    consolidate_graph()
