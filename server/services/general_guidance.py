"""
General guidance by age: age-related changes, why pay attention to diet/exercise. Evidence from KG.
Queries AgeRelatedChange, LifeStage, BodySystem, MODIFIABLE_BY, EXPLAINS_WHY, OCCURS_AT.
"""
from server.models.responses import Evidence, AgeRelatedChangeItem, GeneralGuidanceResponse
from server.neo4j_client import run_query


def _rel_to_evidence(rel: dict) -> Evidence:
    return Evidence(
        source_id=rel.get("source_id") or "",
        source_type=rel.get("source_type") or "PMC",
        context=rel.get("context") or "",
        journal=rel.get("journal") or "",
        pub_date=rel.get("pub_date") or "",
    )


def _life_stage_from_age(age: int | None) -> str:
    """Map age to life stage label (canonical)."""
    if age is None:
        return ""
    if age < 30:
        return "20s"
    if age < 40:
        return "30s"
    if age < 50:
        return "40s"
    if age < 65:
        return "50s-60s"
    return "65+"


def get_general_guidance(age: int | None) -> GeneralGuidanceResponse:
    """
    Age-related changes and why pay attention (diet, exercise) with evidence.
    If KG has no aging layer data yet, returns empty age_related_changes and a generic food summary.
    """
    life_stage = _life_stage_from_age(age)
    age_related_changes: list[AgeRelatedChangeItem] = []

    # AgeRelatedChange -[OCCURS_AT]-> LifeStage; -[MODIFIABLE_BY]-> Nutrient/Food/LifestyleFactor; -[EXPLAINS_WHY]->
    q_aging = """
    MATCH (a:AgeRelatedChange)-[r]->(t)
    WHERE type(r) IN ['OCCURS_AT', 'MODIFIABLE_BY', 'EXPLAINS_WHY']
      AND r.source_id IS NOT NULL AND r.source_id <> ''
    RETURN a.name AS change, type(r) AS predicate, t.name AS target,
           r.context AS context, r.source_id AS source_id, r.source_type AS source_type,
           r.journal AS journal, r.pub_date AS pub_date
    LIMIT 50
    """
    rows = run_query(q_aging, {})
    # Group by change name
    by_change: dict[str, list[dict]] = {}
    for row in rows:
        ch = (row.get("change") or "").strip()
        if not ch:
            continue
        if ch not in by_change:
            by_change[ch] = []
        by_change[ch].append(row)

    for change_name, rels in by_change.items():
        why_parts = []
        life_stage_val = ""
        ev_list: list[Evidence] = []
        for r in rels:
            ev_list.append(_rel_to_evidence(r))
            pred = r.get("predicate") or ""
            target = (r.get("target") or "").strip()
            if pred == "OCCURS_AT":
                life_stage_val = target or life_stage
            elif pred == "MODIFIABLE_BY":
                why_parts.append(f"Modifiable by {target}")
            elif pred == "EXPLAINS_WHY":
                why_parts.append(r.get("context") or target)
        why = "; ".join(why_parts) if why_parts else "Diet and exercise matter for this change."
        age_related_changes.append(
            AgeRelatedChangeItem(
                change=change_name,
                life_stage=life_stage_val,
                why_pay_attention=why,
                evidence=ev_list[:3],
            )
        )

    # High-level food guidance (static summary when we have no dedicated food-summary graph)
    food_guidance_summary = (
        "Prefer Mediterranean-style choices; limit sodium and processed meats. "
        "Evidence-based recommendations depend on your conditions and age—use the recommendations and safest-path endpoints for personalized guidance."
    )

    return GeneralGuidanceResponse(
        food_guidance_summary=food_guidance_summary,
        age_related_changes=age_related_changes,
    )
