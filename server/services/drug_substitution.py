"""
Drug-substituting/complementing foods from KG. SUBSTITUTES_FOR, COMPLEMENTS_DRUG with evidence.
Zero-error: only items with evidence. Canonical drug names for lookup.
"""
from server.canonical import normalize_entity_name
from server.models.responses import Evidence, DrugSubstituteItem, DrugSubstitutionItem, DrugSubstitutionResponse
from server.neo4j_client import run_query


def _rel_to_evidence(rel: dict) -> Evidence:
    return Evidence(
        source_id=rel.get("source_id") or "",
        source_type=rel.get("source_type") or "PMC",
        context=rel.get("context") or "",
        journal=rel.get("journal") or "",
        pub_date=rel.get("pub_date") or "",
    )


def get_drug_substitution(drugs: list[str], limit_per_drug: int = 15) -> DrugSubstitutionResponse:
    """
    For each drug, return foods/ingredients that SUBSTITUTES_FOR or COMPLEMENTS_DRUG it, with evidence.
    Drugs are normalized to canonical names. Only items with at least one evidence record.
    """
    drug_canonical = [normalize_entity_name(d) for d in (drugs or []) if d]
    by_drug: list[DrugSubstitutionItem] = []

    for drug in drug_canonical:
        substitutes: list[DrugSubstituteItem] = []
        complements: list[DrugSubstituteItem] = []

        q_sub = """
        MATCH (x)-[r:SUBSTITUTES_FOR]->(d:Drug)
        WHERE d.name = $drug AND r.source_id IS NOT NULL AND r.source_id <> ''
        RETURN x.name AS name, r.context AS context, r.source_id AS source_id,
               r.source_type AS source_type, r.journal AS journal, r.pub_date AS pub_date
        LIMIT $limit
        """
        for row in run_query(q_sub, {"drug": drug, "limit": limit_per_drug}):
            name = (row.get("name") or "").strip()
            if name:
                substitutes.append(
                    DrugSubstituteItem(
                        food_or_ingredient=name,
                        relation="SUBSTITUTES_FOR",
                        reason=row.get("context") or "May substitute",
                        evidence=[_rel_to_evidence(row)],
                    )
                )

        q_comp = """
        MATCH (x)-[r:COMPLEMENTS_DRUG]->(d:Drug)
        WHERE d.name = $drug AND r.source_id IS NOT NULL AND r.source_id <> ''
        RETURN x.name AS name, r.context AS context, r.source_id AS source_id,
               r.source_type AS source_type, r.journal AS journal, r.pub_date AS pub_date
        LIMIT $limit
        """
        for row in run_query(q_comp, {"drug": drug, "limit": limit_per_drug}):
            name = (row.get("name") or "").strip()
            if name:
                complements.append(
                    DrugSubstituteItem(
                        food_or_ingredient=name,
                        relation="COMPLEMENTS_DRUG",
                        reason=row.get("context") or "May complement",
                        evidence=[_rel_to_evidence(row)],
                    )
                )

        by_drug.append(
            DrugSubstitutionItem(drug=drug, substitutes=substitutes, complements=complements)
        )

    return DrugSubstitutionResponse(by_drug=by_drug)
