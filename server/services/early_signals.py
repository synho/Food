"""
Early-signal guidance: symptom → disease (EARLY_SIGNAL_OF); foods that reduce (ALLEVIATES) vs avoid (AGGRAVATES).
Zero-error: all items with evidence.
"""
from server.canonical import normalize_entity_name
from server.models.responses import (
    Evidence,
    EarlySignalItem,
    EarlySignalGuidanceResponse,
    FoodRecommendation,
    FoodRestriction,
)
from server.neo4j_client import run_query


def _rel_to_evidence(rel: dict) -> Evidence:
    return Evidence(
        source_id=rel.get("source_id") or "",
        source_type=rel.get("source_type") or "PMC",
        context=rel.get("context") or "",
        journal=rel.get("journal") or "",
        pub_date=rel.get("pub_date") or "",
    )


def get_early_signal_guidance(symptoms: list[str], limit: int = 15) -> EarlySignalGuidanceResponse:
    """
    For user's symptoms: (1) early signals (symptom → disease), (2) foods that reduce, (3) foods to avoid.
    Only items with at least one evidence record.
    """
    sym_canonical = [normalize_entity_name(s) for s in (symptoms or []) if s]
    early_signals: list[EarlySignalItem] = []
    foods_that_reduce: list[FoodRecommendation] = []
    foods_to_avoid: list[FoodRestriction] = []

    if not sym_canonical:
        return EarlySignalGuidanceResponse(
            early_signals=early_signals,
            foods_that_reduce=foods_that_reduce,
            foods_to_avoid=foods_to_avoid,
        )

    # Early signals: Symptom -EARLY_SIGNAL_OF-> Disease
    q_signal = """
    MATCH (s:Symptom)-[r:EARLY_SIGNAL_OF]->(d:Disease)
    WHERE s.name IN $symptoms AND r.source_id IS NOT NULL AND r.source_id <> ''
    RETURN s.name AS symptom, d.name AS disease,
           r.context AS context, r.source_id AS source_id, r.source_type AS source_type,
           r.journal AS journal, r.pub_date AS pub_date
    LIMIT $limit
    """
    rows = run_query(q_signal, {"symptoms": sym_canonical, "limit": limit})
    for row in rows:
        symptom = (row.get("symptom") or "").strip()
        disease = (row.get("disease") or "").strip()
        if symptom and disease:
            early_signals.append(
                EarlySignalItem(
                    symptom=symptom,
                    disease=disease,
                    evidence=[_rel_to_evidence(row)],
                )
            )

    # Foods/nutrients that reduce these symptoms (ALLEVIATES)
    q_allev = """
    MATCH (f)-[r:ALLEVIATES]->(s:Symptom)
    WHERE (f:Food OR f:Nutrient)
      AND s.name IN $symptoms AND r.source_id IS NOT NULL AND r.source_id <> ''
    RETURN f.name AS food, s.name AS target,
           r.context AS context, r.source_id AS source_id, r.source_type AS source_type,
           r.journal AS journal, r.pub_date AS pub_date
    LIMIT $limit
    """
    rows = run_query(q_allev, {"symptoms": sym_canonical, "limit": limit})
    by_food: dict[str, list[Evidence]] = {}
    for row in rows:
        food = (row.get("food") or "").strip()
        target = (row.get("target") or "").strip()
        if food:
            if food not in by_food:
                by_food[food] = []
            by_food[food].append(_rel_to_evidence(row))
    for food, ev_list in by_food.items():
        if ev_list:
            foods_that_reduce.append(
                FoodRecommendation(food=food, reason="May alleviate symptom", evidence=ev_list)
            )

    # Foods/nutrients to avoid (AGGRAVATES)
    q_aggr = """
    MATCH (f)-[r:AGGRAVATES]->(s:Symptom)
    WHERE (f:Food OR f:Nutrient)
      AND s.name IN $symptoms AND r.source_id IS NOT NULL AND r.source_id <> ''
    RETURN f.name AS food, s.name AS target,
           r.context AS context, r.source_id AS source_id, r.source_type AS source_type,
           r.journal AS journal, r.pub_date AS pub_date
    LIMIT $limit
    """
    rows = run_query(q_aggr, {"symptoms": sym_canonical, "limit": limit})
    by_food_aggr: dict[str, list[Evidence]] = {}
    for row in rows:
        food = (row.get("food") or "").strip()
        if food:
            if food not in by_food_aggr:
                by_food_aggr[food] = []
            by_food_aggr[food].append(_rel_to_evidence(row))
    for food, ev_list in by_food_aggr.items():
        if ev_list:
            foods_to_avoid.append(
                FoodRestriction(food=food, reason="May aggravate symptom", evidence=ev_list)
            )

    return EarlySignalGuidanceResponse(
        early_signals=early_signals,
        foods_that_reduce=foods_that_reduce,
        foods_to_avoid=foods_to_avoid,
    )
