"""
Food recommendations from KG. Zero-error: only return items with at least one evidence record.
Uses canonical entity names for conditions/symptoms when querying.
Multi-hop: 1-hop direct + CONTAINS chain + disease-expansion via shared symptoms.
Age/gender bracket profiles provide defaults when no conditions/symptoms given.
"""
from server.canonical import normalize_entity_name
from server.models.responses import Evidence, FoodRecommendation, FoodRestriction, RecommendationsResponse
from server.neo4j_client import run_query


# ── Age/gender bracket profiles ───────────────────────────────────────────────

AGE_GENDER_PROFILES: dict[tuple[str, str], dict] = {
    ("30s", "female"): {
        "priority_conditions": ["Iron-deficiency anaemia", "Polycystic ovary syndrome"],
        "focus_nutrients": ["Iron", "Folate", "Vitamin D"],
    },
    ("30s", "male"): {
        "priority_conditions": ["Cardiovascular disease", "Hypertension"],
        "focus_nutrients": ["Omega-3", "Potassium", "Magnesium"],
    },
    ("40s", "female"): {
        "priority_conditions": ["Cardiovascular disease", "Type 2 diabetes", "Osteoporosis"],
        "focus_nutrients": ["Vitamin D", "Calcium", "Omega-3", "Magnesium"],
    },
    ("40s", "male"): {
        "priority_conditions": ["Cardiovascular disease", "Hypertension", "Type 2 diabetes"],
        "focus_nutrients": ["Omega-3", "Dietary fibre", "Potassium"],
    },
    ("50s", "female"): {
        "priority_conditions": ["Osteoporosis", "Cardiovascular disease", "Sarcopenia"],
        "focus_nutrients": ["Calcium", "Vitamin D", "Omega-3", "Iron"],
    },
    ("50s", "male"): {
        "priority_conditions": ["Cardiovascular disease", "Type 2 diabetes", "Sarcopenia"],
        "focus_nutrients": ["Omega-3", "Magnesium", "Dietary fibre"],
    },
    ("60s+", "female"): {
        "priority_conditions": ["Osteoporosis", "Sarcopenia", "Cardiovascular disease", "Cognitive decline"],
        "focus_nutrients": ["Calcium", "Vitamin D", "Vitamin B12", "Omega-3"],
    },
    ("60s+", "male"): {
        "priority_conditions": ["Cardiovascular disease", "Sarcopenia", "Cognitive decline", "Type 2 diabetes"],
        "focus_nutrients": ["Omega-3", "Vitamin B12", "Magnesium"],
    },
    ("default", "any"): {
        "priority_conditions": ["Cardiovascular disease", "Type 2 diabetes", "Hypertension"],
        "focus_nutrients": ["Omega-3", "Dietary fibre", "Vitamin D"],
    },
}


def get_age_gender_profile(age: int | None, gender: str | None) -> dict:
    """Return the best-matching age/gender profile."""
    if age is not None:
        decade = "30s" if age < 40 else "40s" if age < 50 else "50s" if age < 60 else "60s+"
    else:
        decade = "default"

    g = (gender or "").lower()
    if g in ("female", "f", "woman"):
        normalized = "female"
    elif g in ("male", "m", "man"):
        normalized = "male"
    else:
        normalized = "any"

    return (
        AGE_GENDER_PROFILES.get((decade, normalized))
        or AGE_GENDER_PROFILES.get((decade, "any"))
        or AGE_GENDER_PROFILES[("default", "any")]
    )


# ── Evidence helper ───────────────────────────────────────────────────────────

def _rel_to_evidence(rel: dict) -> Evidence:
    return Evidence(
        source_id=rel.get("source_id") or "",
        source_type=rel.get("source_type") or "PMC",
        context=rel.get("context") or "",
        journal=rel.get("journal") or "",
        pub_date=rel.get("pub_date") or "",
    )


# ── Query helpers ─────────────────────────────────────────────────────────────

def _run_layer1(targets: list[str], limit: int) -> list[dict]:
    """Layer 1 — 1-hop: Food/Nutrient -[PREVENTS|TREATS|ALLEVIATES|REDUCES_RISK_OF]-> Disease/Symptom."""
    q = """
    MATCH (f)-[r]->(t)
    WHERE (f:Food OR f:Nutrient)
      AND type(r) IN ['PREVENTS', 'TREATS', 'ALLEVIATES', 'REDUCES_RISK_OF']
      AND (t:Disease OR t:Symptom)
      AND r.source_id IS NOT NULL AND r.source_id <> ''
      AND (size($targets) = 0 OR t.name IN $targets)
    RETURN f.name AS food, type(r) AS predicate, t.name AS target,
           null AS via_nutrient,
           r.context AS context, r.source_id AS source_id, r.source_type AS source_type,
           r.journal AS journal, r.pub_date AS pub_date
    LIMIT $query_limit
    """
    return run_query(q, {"targets": targets, "query_limit": limit * 10})


def _run_layer2(targets: list[str], limit: int) -> list[dict]:
    """Layer 2 — CONTAINS chain: Food -[:CONTAINS]-> Nutrient -[...]-> Disease/Symptom."""
    if not targets:
        return []
    q = """
    MATCH (food:Food)-[:CONTAINS]->(n:Nutrient)-[r:PREVENTS|TREATS|ALLEVIATES|REDUCES_RISK_OF]->(t)
    WHERE (t:Disease OR t:Symptom)
      AND t.name IN $targets AND r.source_id IS NOT NULL AND r.source_id <> ''
    RETURN food.name AS food, type(r) AS predicate, t.name AS target,
           n.name AS via_nutrient,
           r.context AS context, r.source_id AS source_id, r.source_type AS source_type,
           r.journal AS journal, r.pub_date AS pub_date
    LIMIT $query_limit
    """
    return run_query(q, {"targets": targets, "query_limit": limit * 10})


def _run_layer3(targets: list[str], limit: int) -> list[dict]:
    """Layer 3 — disease expansion via shared symptoms."""
    if not targets:
        return []
    q = """
    MATCH (s:Symptom)-[:EARLY_SIGNAL_OF]->(d:Disease)
    WHERE d.name IN $targets
    WITH collect(DISTINCT s.name) AS related_symptoms
    MATCH (f)-[r:ALLEVIATES|PREVENTS]->(s2:Symptom)
    WHERE (f:Food OR f:Nutrient) AND s2.name IN related_symptoms
      AND r.source_id IS NOT NULL AND r.source_id <> ''
    RETURN f.name AS food, type(r) AS predicate, s2.name AS target,
           null AS via_nutrient,
           r.context AS context, r.source_id AS source_id, r.source_type AS source_type,
           r.journal AS journal, r.pub_date AS pub_date
    LIMIT $query_limit
    """
    return run_query(q, {"targets": targets, "query_limit": limit * 10})


def _run_restricted(targets: list[str], limit: int) -> list[dict]:
    """Restricted foods: Food/Nutrient -[AGGRAVATES|CAUSES]-> Disease/Symptom."""
    q = """
    MATCH (f)-[r]->(t)
    WHERE (f:Food OR f:Nutrient)
      AND type(r) IN ['AGGRAVATES', 'CAUSES']
      AND (t:Disease OR t:Symptom)
      AND r.source_id IS NOT NULL AND r.source_id <> ''
      AND (size($targets) = 0 OR t.name IN $targets)
    RETURN f.name AS food, type(r) AS predicate, t.name AS target,
           r.context AS context, r.source_id AS source_id, r.source_type AS source_type,
           r.journal AS journal, r.pub_date AS pub_date
    LIMIT $query_limit
    """
    return run_query(q, {"targets": targets, "query_limit": limit * 10})


# ── Build reason string ───────────────────────────────────────────────────────

def _make_reason(row: dict, profile_note: str = "") -> str:
    pred = (row.get("predicate") or "PREVENTS").replace("_", " ").lower()
    target = (row.get("target") or "").strip()
    via = row.get("via_nutrient")

    if via:
        reason = f"Contains {via} which {pred} {target}"
    else:
        reason = f"Associated with {pred} of {target}"

    if profile_note:
        reason = f"{profile_note} — {reason}"
    return reason


# ── Main entry point ──────────────────────────────────────────────────────────

def get_recommendations(
    conditions: list[str],
    symptoms: list[str],
    age: int | None = None,
    gender: str | None = None,
    limit: int = 20,
    plan: str = "free",
) -> RecommendationsResponse:
    """
    Query KG for recommended and restricted foods. Only includes items with evidence (zero-error).
    Conditions and symptoms are normalized to canonical names for KG lookup.
    Three query layers: 1-hop direct, CONTAINS chain, disease-expansion via symptoms.
    Falls back to age/gender profile defaults when no conditions/symptoms given.
    Free plan is capped at 5 recommended and 5 restricted items.
    """
    effective_limit = 5 if plan == "free" else limit
    cond_canonical = [normalize_entity_name(c) for c in (conditions or []) if c]
    sym_canonical = [normalize_entity_name(s) for s in (symptoms or []) if s]
    targets = cond_canonical + sym_canonical

    profile_note = ""

    # Fallback: age/gender defaults when user gives no conditions or symptoms
    if len(targets) == 0 and (age or gender):
        profile = get_age_gender_profile(age, gender)
        targets = profile["priority_conditions"]

        # Build a short profile label for the reason string
        if age:
            decade = "30s" if age < 40 else "40s" if age < 50 else "50s" if age < 60 else "60s+"
        else:
            decade = ""
        g_label = (gender or "").lower()
        profile_note = f"Recommended for your profile ({' '.join(filter(None, [decade, g_label]))})"

    recommended: list[FoodRecommendation] = []

    # Run all three recommendation layers and merge by (food, reason)
    layer1_rows = _run_layer1(targets, limit)
    layer2_rows = _run_layer2(targets, limit)
    layer3_rows = _run_layer3(targets, limit)

    rec_by_key: dict[tuple[str, str], list[Evidence]] = {}
    for row in layer1_rows + layer2_rows + layer3_rows:
        food = (row.get("food") or "").strip()
        if not food:
            continue
        reason = _make_reason(row, profile_note)
        key = (food, reason)
        ev = _rel_to_evidence(row)
        if key not in rec_by_key:
            rec_by_key[key] = []
        rec_by_key[key].append(ev)

    for (food, reason), ev_list in list(rec_by_key.items())[:effective_limit]:
        if ev_list:
            recommended.append(FoodRecommendation(food=food, reason=reason, evidence=ev_list))

    # Restricted foods
    restricted: list[FoodRestriction] = []
    res_rows = _run_restricted(targets, limit)
    res_by_key: dict[tuple[str, str], list[Evidence]] = {}
    for row in res_rows:
        food = (row.get("food") or "").strip()
        if not food:
            continue
        pred = (row.get("predicate") or "AGGRAVATES").replace("_", " ").lower()
        target = (row.get("target") or "").strip()
        reason = f"Associated with {pred} of {target}"
        key = (food, reason)
        ev = _rel_to_evidence(row)
        if key not in res_by_key:
            res_by_key[key] = []
        res_by_key[key].append(ev)

    for (food, reason), ev_list in list(res_by_key.items())[:effective_limit]:
        if ev_list:
            restricted.append(FoodRestriction(food=food, reason=reason, evidence=ev_list))

    return RecommendationsResponse(recommended=recommended, restricted=restricted)
