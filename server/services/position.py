"""
Health map position and nearby risks. Uses canonical names; returns only risks with evidence when available.
"""
from server.canonical import normalize_entity_name
from server.models.responses import Evidence, NearbyRisk, PositionResponse
from server.neo4j_client import run_query


def _rel_to_evidence(rel: dict) -> Evidence:
    return Evidence(
        source_id=rel.get("source_id") or "",
        source_type=rel.get("source_type") or "PMC",
        context=rel.get("context") or "",
        journal=rel.get("journal") or "",
        pub_date=rel.get("pub_date") or "",
    )


def get_position(conditions: list[str], symptoms: list[str], plan: str = "free") -> PositionResponse:
    """
    User position = active conditions/symptoms (canonical). Nearby risks = diseases linked by EARLY_SIGNAL_OF
    from user symptoms, plus user's conditions as risks; each with evidence when available.
    Free plan caps nearby_risks to 5.
    """
    max_risks = 5 if plan == "free" else 30
    active_conditions = [normalize_entity_name(c) for c in (conditions or []) if c]
    active_symptoms = [normalize_entity_name(s) for s in (symptoms or []) if s]

    nearby_risks: list[NearbyRisk] = []

    # Nearby risks: Symptom -EARLY_SIGNAL_OF-> Disease for user's symptoms (diseases to watch)
    if active_symptoms:
        q = """
        MATCH (s:Symptom)-[r:EARLY_SIGNAL_OF]->(d:Disease)
        WHERE s.name IN $symptoms AND r.source_id IS NOT NULL AND r.source_id <> ''
        RETURN s.name AS symptom, d.name AS disease,
               r.context AS context, r.source_id AS source_id, r.source_type AS source_type,
               r.journal AS journal, r.pub_date AS pub_date
        LIMIT 30
        """
        rows = run_query(q, {"symptoms": active_symptoms})
        seen: set[tuple[str, str]] = set()
        for row in rows:
            disease = (row.get("disease") or "").strip()
            symptom = (row.get("symptom") or "").strip()
            if not disease or (symptom, disease) in seen:
                continue
            seen.add((symptom, disease))
            ev = _rel_to_evidence(row)
            nearby_risks.append(
                NearbyRisk(
                    name=disease,
                    kind="early_signal",
                    reason=f"Early signal: {symptom}",
                    evidence=[ev],
                )
            )

    # User's conditions as nearby risks (they are "here")
    for c in active_conditions:
        nearby_risks.append(
            NearbyRisk(name=c, kind="disease", reason="Current condition", evidence=[])
        )

    return PositionResponse(
        active_conditions=active_conditions,
        active_symptoms=active_symptoms,
        nearby_risks=nearby_risks[:max_risks],
    )
