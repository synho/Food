"""
Safest path (evacuation to safety): actionable steps with evidence. Zero-error.
"""
from server.canonical import normalize_entity_name
from server.models.responses import Evidence, PathStep, SafestPathResponse
from server.neo4j_client import run_query


def _rel_to_evidence(rel: dict) -> Evidence:
    return Evidence(
        source_id=rel.get("source_id") or "",
        source_type=rel.get("source_type") or "PMC",
        context=rel.get("context") or "",
        journal=rel.get("journal") or "",
        pub_date=rel.get("pub_date") or "",
    )


def get_safest_path(conditions: list[str], symptoms: list[str], limit: int = 10) -> SafestPathResponse:
    """
    Actionable steps: increase foods that PREVENTS/TREATS/ALLEVIATES; reduce foods that AGGRAVATES/CAUSES.
    Only steps with at least one evidence record (zero-error).
    """
    cond_canonical = [normalize_entity_name(c) for c in (conditions or []) if c]
    sym_canonical = [normalize_entity_name(s) for s in (symptoms or []) if s]
    targets = cond_canonical + sym_canonical
    steps: list[PathStep] = []

    # Step: Increase foods/nutrients that help (PREVENTS/TREATS/ALLEVIATES)
    q_increase = """
    MATCH (f)-[r]->(t)
    WHERE (f:Food OR f:Nutrient)
      AND type(r) IN ['PREVENTS', 'TREATS', 'ALLEVIATES', 'REDUCES_RISK_OF']
      AND (t:Disease OR t:Symptom)
      AND r.source_id IS NOT NULL AND r.source_id <> ''
      AND (size($targets) = 0 OR t.name IN $targets)
    RETURN f.name AS food, type(r) AS predicate, t.name AS target,
           r.context AS context, r.source_id AS source_id, r.source_type AS source_type,
           r.journal AS journal, r.pub_date AS pub_date
    LIMIT $limit
    """
    rows = run_query(q_increase, {"targets": targets, "limit": limit})
    if rows:
        ev_list = [_rel_to_evidence(r) for r in rows]
        foods = list(dict.fromkeys([(r.get("food") or "").strip() for r in rows if (r.get("food") or "").strip()]))[:5]
        steps.append(
            PathStep(
                action=f"Increase: {', '.join(foods)}",
                reason="Associated with reduced risk or alleviation of condition",
                evidence=ev_list[:3],
            )
        )

    # Step: Reduce foods/nutrients that worsen (AGGRAVATES/CAUSES)
    q_reduce = """
    MATCH (f)-[r]->(t)
    WHERE (f:Food OR f:Nutrient)
      AND type(r) IN ['AGGRAVATES', 'CAUSES']
      AND (t:Disease OR t:Symptom)
      AND r.source_id IS NOT NULL AND r.source_id <> ''
      AND (size($targets) = 0 OR t.name IN $targets)
    RETURN f.name AS food, type(r) AS predicate, t.name AS target,
           r.context AS context, r.source_id AS source_id, r.source_type AS source_type,
           r.journal AS journal, r.pub_date AS pub_date
    LIMIT $limit
    """
    rows = run_query(q_reduce, {"targets": targets, "limit": limit})
    if rows:
        ev_list = [_rel_to_evidence(r) for r in rows]
        foods = list(dict.fromkeys([(r.get("food") or "").strip() for r in rows if (r.get("food") or "").strip()]))[:5]
        steps.append(
            PathStep(
                action=f"Reduce: {', '.join(foods)}",
                reason="Associated with aggravation or increased risk",
                evidence=ev_list[:3],
            )
        )

    return SafestPathResponse(steps=steps)
