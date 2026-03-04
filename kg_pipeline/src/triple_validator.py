"""
Triple quality validator — scores and filters extracted triples before ingest.

Zero-error enforcement:
  - Rejects triples missing source_id, context, or pub_date
  - Rejects triples with vague/generic entity names (< 3 chars, or generic terms)
  - Rejects triples with RELATES_TO predicate (catch-all fallback — no information value)

Evidence strength scoring (stored on Neo4j relationships):
  5 = RCT (randomized controlled trial)
  4 = meta-analysis / systematic review
  3 = cohort / observational study
  2 = review article
  1 = other / unknown

Usage:
    from triple_validator import validate_and_score
    valid_triples, rejected, stats = validate_and_score(raw_triples)
"""
from __future__ import annotations

from ontology import ENTITY_TYPES, REJECT_ENTITY_TYPES, WEAK_PREDICATES

# Set of valid entity types for fast lookup
_VALID_ENTITY_TYPES = set(ENTITY_TYPES)

# ── Known medical abbreviations that have canonical name mappings ─────────────
# These pass the vague/length check even though they're short
_ABBREVIATION_WHITELIST = {
    "ra", "ms", "uc", "oa", "mi", "uv", "sle", "t1d", "gad",
    "hba1c", "crp", "ldl", "hdl", "bmi", "tg", "crc", "amd",
    "copd", "ptsd", "ckd", "mdd", "ibs", "cvd", "egfr",
    "nafld", "gerd", "nsclc", "fbg", "sbp", "dbp", "a1c",
}

# ── Vague entity names to reject ─────────────────────────────────────────────
_VAGUE = {
    "patients", "patient", "humans", "human", "adults", "adult", "children",
    "child", "people", "person", "individuals", "individual", "subjects",
    "subject", "participants", "participant", "population", "group", "groups",
    "women", "men", "woman", "man", "elderly", "seniors", "control group",
    "treatment group", "study group", "healthy subjects", "healthy adults",
    "healthy individuals", "older adults", "young adults", "volunteers",
    "intervention group", "placebo group", "control", "intervention",
    "experimental group", "samples", "cases", "cohort", "body",
}

# ── Evidence type → strength score ───────────────────────────────────────────
_EVIDENCE_STRENGTH: dict[str, int] = {
    "rct": 5,
    "randomized_controlled_trial": 5,
    "randomized controlled trial": 5,
    "meta_analysis": 4,
    "meta-analysis": 4,
    "systematic_review": 4,
    "systematic review": 4,
    "cohort": 3,
    "prospective cohort": 3,
    "retrospective cohort": 3,
    "observational": 3,
    "case_control": 3,
    "case-control": 3,
    "cross_sectional": 2,
    "cross-sectional": 2,
    "review": 2,
    "narrative review": 2,
    "other": 1,
    "": 1,
}

# ── Low-value predicates — imported from ontology.WEAK_PREDICATES ─────────────
_WEAK_PREDICATES = WEAK_PREDICATES


def _evidence_strength(evidence_type: str) -> int:
    key = (evidence_type or "").strip().lower()
    # Normalize underscores/hyphens
    return _EVIDENCE_STRENGTH.get(key) or _EVIDENCE_STRENGTH.get(key.replace("_", " ")) or 1


def _is_vague(name: str) -> bool:
    if not name or not name.strip():
        return True
    cleaned = name.strip().lower()
    # Allow known medical abbreviations even if short
    if cleaned in _ABBREVIATION_WHITELIST:
        return False
    if len(cleaned) < 3:
        return True
    return cleaned in _VAGUE


def validate_and_score(
    triples: list[dict],
    strict_pub_date: bool = False,
) -> tuple[list[dict], list[dict], dict]:
    """
    Validate and score a list of raw extracted triples.

    Args:
        triples: raw triple dicts from extract_triples.py
        strict_pub_date: if True, reject triples with pub_date == "Unknown"

    Returns:
        (valid_triples, rejected_triples, stats_dict)
        Each valid triple gets an `evidence_strength` field (int 1-5).
    """
    valid: list[dict] = []
    rejected: list[dict] = []
    reject_reasons: dict[str, int] = {}

    def _reject(t: dict, reason: str):
        t["_reject_reason"] = reason
        rejected.append(t)
        reject_reasons[reason] = reject_reasons.get(reason, 0) + 1

    for t in triples:
        # 1. source_id required (zero-error rule)
        if not (t.get("source_id") or "").strip():
            _reject(t, "missing source_id")
            continue

        # 2. context required (prevents evidence-free triples)
        if not (t.get("context") or "").strip():
            _reject(t, "missing context")
            continue

        # 3. pub_date check
        pub_date = (t.get("pub_date") or "").strip()
        if strict_pub_date and (not pub_date or pub_date == "Unknown"):
            _reject(t, "missing pub_date")
            continue

        # 4. Entity quality checks
        subject = (t.get("subject") or "").strip()
        obj = (t.get("object") or "").strip()
        if _is_vague(subject):
            _reject(t, f"vague subject: {subject!r}")
            continue
        if _is_vague(obj):
            _reject(t, f"vague object: {obj!r}")
            continue

        # 5. Low-value predicate filter
        predicate = (t.get("predicate") or "").strip().upper()
        if predicate in _WEAK_PREDICATES:
            _reject(t, f"low-value predicate: {predicate}")
            continue

        # 6. Entity type validation — reject types not in ontology or in reject list
        subject_type = (t.get("subject_type") or "").strip()
        object_type = (t.get("object_type") or "").strip()
        if subject_type:
            st_key = subject_type.replace(" ", "_").replace("-", "_").lower()
            if st_key in REJECT_ENTITY_TYPES:
                _reject(t, f"rejected subject_type: {subject_type}")
                continue
            if subject_type not in _VALID_ENTITY_TYPES:
                _reject(t, f"unknown subject_type: {subject_type}")
                continue
        if object_type:
            ot_key = object_type.replace(" ", "_").replace("-", "_").lower()
            if ot_key in REJECT_ENTITY_TYPES:
                _reject(t, f"rejected object_type: {object_type}")
                continue
            if object_type not in _VALID_ENTITY_TYPES:
                _reject(t, f"unknown object_type: {object_type}")
                continue

        # 7. Assign evidence strength
        t["evidence_strength"] = _evidence_strength(t.get("evidence_type", ""))
        valid.append(t)

    total = len(triples)
    n_valid = len(valid)
    n_rejected = len(rejected)
    pass_rate = round(100 * n_valid / total, 1) if total else 0.0

    stats = {
        "total": total,
        "valid": n_valid,
        "rejected": n_rejected,
        "pass_rate_pct": pass_rate,
        "reject_reasons": reject_reasons,
        "avg_evidence_strength": round(
            sum(t.get("evidence_strength", 1) for t in valid) / max(n_valid, 1), 2
        ),
        "rct_count": sum(1 for t in valid if t.get("evidence_strength", 1) >= 5),
        "meta_count": sum(1 for t in valid if t.get("evidence_strength", 1) >= 4),
    }
    return valid, rejected, stats


def report(stats: dict) -> str:
    lines = [
        f"Triple validation: {stats['valid']}/{stats['total']} passed ({stats['pass_rate_pct']}%)",
        f"  Avg evidence strength: {stats['avg_evidence_strength']}/5  "
        f"(RCT: {stats['rct_count']}, meta-analysis: {stats['meta_count']})",
    ]
    if stats["reject_reasons"]:
        lines.append("  Rejections by reason:")
        for reason, count in sorted(stats["reject_reasons"].items(), key=lambda x: -x[1]):
            lines.append(f"    {count:3d}  {reason}")
    return "\n".join(lines)
