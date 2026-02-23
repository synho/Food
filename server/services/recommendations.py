"""
Food recommendations from KG. Zero-error: only return items with at least one evidence record.
Uses canonical entity names for conditions/symptoms when querying.
"""
from server.canonical import normalize_entity_name
from server.models.responses import Evidence, FoodRecommendation, FoodRestriction, RecommendationsResponse
from server.neo4j_client import run_query


def _rel_to_evidence(rel: dict) -> Evidence:
    return Evidence(
        source_id=rel.get("source_id") or "",
        source_type=rel.get("source_type") or "PMC",
        context=rel.get("context") or "",
        journal=rel.get("journal") or "",
        pub_date=rel.get("pub_date") or "",
    )


def get_recommendations(conditions: list[str], symptoms: list[str], limit: int = 20) -> RecommendationsResponse:
    """
    Query KG for recommended and restricted foods. Only includes items with evidence (zero-error).
    Conditions and symptoms are normalized to canonical names before query.
    """
    # Normalize user input to canonical names for KG lookup
    cond_canonical = [normalize_entity_name(c) for c in (conditions or []) if c]
    sym_canonical = [normalize_entity_name(s) for s in (symptoms or []) if s]

    targets = cond_canonical + sym_canonical

    recommended: list[FoodRecommendation] = []
    restricted: list[FoodRestriction] = []

    # Recommended: Food/Nutrient -[PREVENTS|TREATS|ALLEVIATES|REDUCES_RISK_OF]-> Disease/Symptom
    # When targets provided, filter to foods linked to user's conditions/symptoms only.
    # Query with higher limit to compensate for evidence-level rows; Python-slice unique items to limit.
    q_rec = """
    MATCH (f)-[r]->(t)
    WHERE (f:Food OR f:Nutrient)
      AND type(r) IN ['PREVENTS', 'TREATS', 'ALLEVIATES', 'REDUCES_RISK_OF']
      AND (t:Disease OR t:Symptom)
      AND r.source_id IS NOT NULL AND r.source_id <> ''
      AND (size($targets) = 0 OR t.name IN $targets)
    RETURN f.name AS food, type(r) AS predicate, t.name AS target,
           r.context AS context, r.source_id AS source_id, r.source_type AS source_type,
           r.journal AS journal, r.pub_date AS pub_date
    LIMIT $query_limit
    """
    rec_rows = run_query(q_rec, {"targets": targets, "query_limit": limit * 10})
    # Group by (food, reason) and collect evidence; slice unique food entries to limit
    rec_by_key: dict[tuple[str, str], list[Evidence]] = {}
    for row in rec_rows:
        food = (row.get("food") or "").strip()
        if not food:
            continue
        pred = row.get("predicate") or "PREVENTS"
        target = (row.get("target") or "").strip()
        reason = f"Associated with {pred.replace('_', ' ').lower()} of {target}"
        key = (food, reason)
        ev = _rel_to_evidence(row)
        if key not in rec_by_key:
            rec_by_key[key] = []
        rec_by_key[key].append(ev)
    for (food, reason), ev_list in list(rec_by_key.items())[:limit]:
        if ev_list:
            recommended.append(FoodRecommendation(food=food, reason=reason, evidence=ev_list))

    # Restricted: Food/Nutrient -[AGGRAVATES|CAUSES]-> Disease/Symptom
    q_res = """
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
    res_rows = run_query(q_res, {"targets": targets, "query_limit": limit * 10})
    res_by_key: dict[tuple[str, str], list[Evidence]] = {}
    for row in res_rows:
        food = (row.get("food") or "").strip()
        if not food:
            continue
        pred = row.get("predicate") or "AGGRAVATES"
        target = (row.get("target") or "").strip()
        reason = f"Associated with {pred.replace('_', ' ').lower()} of {target}"
        key = (food, reason)
        ev = _rel_to_evidence(row)
        if key not in res_by_key:
            res_by_key[key] = []
        res_by_key[key].append(ev)
    for (food, reason), ev_list in list(res_by_key.items())[:limit]:
        if ev_list:
            restricted.append(FoodRestriction(food=food, reason=reason, evidence=ev_list))

    return RecommendationsResponse(recommended=recommended, restricted=restricted)
