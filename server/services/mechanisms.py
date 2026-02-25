"""
Mechanism service — multi-hop mechanism graph for a disease.
Food/Nutrient -TARGETS_MECHANISM-> Mechanism -CAUSES/INCREASES_RISK_OF-> Disease.
Shows *why* a food helps or harms through the biological mechanism.
"""
from server.neo4j_client import get_driver
from server.canonical import normalize_entity_name


def get_mechanisms(disease: str) -> dict:
    """
    Given a disease, find the mechanism chain:
    Food/Nutrient → TARGETS_MECHANISM → Mechanism → CAUSES/INCREASES_RISK_OF → Disease
    """
    if not disease or not disease.strip():
        return {"disease": "", "mechanism_chains": [], "disclaimer": _DISCLAIMER}

    driver = get_driver()
    if driver is None:
        return {"disease": disease, "mechanism_chains": [], "error": "Neo4j unavailable", "disclaimer": _DISCLAIMER}

    normalized_disease = normalize_entity_name(disease.strip())

    chains = []
    with driver.session() as session:
        # Multi-hop: Food/Nutrient → Mechanism → Disease
        result = session.run("""
            MATCH (f)-[r1:TARGETS_MECHANISM]->(m:Mechanism)-[r2:CAUSES|INCREASES_RISK_OF]->(d:Disease)
            WHERE (f:Food OR f:Nutrient)
              AND (toLower(d.name) = toLower($disease)
                   OR toLower(d.display_name) = toLower($disease))
              AND r1.source_id IS NOT NULL
            RETURN
                COALESCE(f.display_name, f.name) AS food,
                labels(f)[0] AS food_type,
                COALESCE(m.display_name, m.name) AS mechanism,
                type(r2) AS mechanism_relationship,
                COALESCE(d.display_name, d.name) AS disease,
                r1.context AS food_mechanism_context,
                r1.source_id AS food_mechanism_source_id,
                r1.journal AS food_mechanism_journal,
                r1.pub_date AS food_mechanism_pub_date,
                COALESCE(r1.source_type, 'PMC') AS food_mechanism_source_type,
                r2.context AS mechanism_disease_context,
                r2.source_id AS mechanism_disease_source_id,
                r2.journal AS mechanism_disease_journal,
                r2.pub_date AS mechanism_disease_pub_date,
                COALESCE(r2.source_type, 'PMC') AS mechanism_disease_source_type
            ORDER BY food, mechanism
        """, disease=normalized_disease)

        for row in result:
            chains.append({
                "food": row["food"],
                "food_type": row["food_type"],
                "mechanism": row["mechanism"],
                "mechanism_relationship": row["mechanism_relationship"],
                "disease": row["disease"],
                "food_to_mechanism": {
                    "context": row["food_mechanism_context"] or "",
                    "evidence": {
                        "source_id": row["food_mechanism_source_id"] or "",
                        "source_type": row["food_mechanism_source_type"],
                        "journal": row["food_mechanism_journal"] or "",
                        "pub_date": row["food_mechanism_pub_date"] or "",
                    },
                },
                "mechanism_to_disease": {
                    "context": row["mechanism_disease_context"] or "",
                    "evidence": {
                        "source_id": row["mechanism_disease_source_id"] or "",
                        "source_type": row["mechanism_disease_source_type"],
                        "journal": row["mechanism_disease_journal"] or "",
                        "pub_date": row["mechanism_disease_pub_date"] or "",
                    },
                },
            })

    return {
        "disease": normalized_disease,
        "mechanism_chains": chains,
        "disclaimer": _DISCLAIMER,
    }


def get_drug_interactions(medications: list[str]) -> dict:
    """
    Given medications, find food contraindications and complements.
    Nutrient -CONTRAINDICATED_WITH-> Drug
    Food/Nutrient -COMPLEMENTS_DRUG-> Drug
    """
    if not medications:
        return {"interactions": [], "disclaimer": _DRUG_DISCLAIMER}

    driver = get_driver()
    if driver is None:
        return {"interactions": [], "error": "Neo4j unavailable", "disclaimer": _DRUG_DISCLAIMER}

    normalized = [normalize_entity_name(m) for m in medications if m.strip()]

    interactions = []
    with driver.session() as session:
        for drug in normalized:
            # Contraindications
            contra_result = session.run("""
                MATCH (n)-[r:CONTRAINDICATED_WITH]->(d:Drug)
                WHERE (n:Nutrient OR n:Food)
                  AND (toLower(d.name) = toLower($drug)
                       OR toLower(d.display_name) = toLower($drug))
                  AND r.source_id IS NOT NULL
                RETURN
                    COALESCE(n.display_name, n.name) AS nutrient,
                    labels(n)[0] AS nutrient_type,
                    COALESCE(d.display_name, d.name) AS drug,
                    r.context AS context,
                    r.source_id AS source_id,
                    r.journal AS journal,
                    r.pub_date AS pub_date,
                    COALESCE(r.source_type, 'PMC') AS source_type
            """, drug=drug)

            contraindications = []
            for row in contra_result:
                contraindications.append({
                    "nutrient": row["nutrient"],
                    "nutrient_type": row["nutrient_type"],
                    "context": row["context"] or "",
                    "evidence": {
                        "source_id": row["source_id"] or "",
                        "source_type": row["source_type"],
                        "journal": row["journal"] or "",
                        "pub_date": row["pub_date"] or "",
                    },
                })

            # Complements
            comp_result = session.run("""
                MATCH (n)-[r:COMPLEMENTS_DRUG]->(d:Drug)
                WHERE (n:Nutrient OR n:Food)
                  AND (toLower(d.name) = toLower($drug)
                       OR toLower(d.display_name) = toLower($drug))
                  AND r.source_id IS NOT NULL
                RETURN
                    COALESCE(n.display_name, n.name) AS nutrient,
                    labels(n)[0] AS nutrient_type,
                    COALESCE(d.display_name, d.name) AS drug,
                    r.context AS context,
                    r.source_id AS source_id,
                    r.journal AS journal,
                    r.pub_date AS pub_date,
                    COALESCE(r.source_type, 'PMC') AS source_type
            """, drug=drug)

            complements = []
            for row in comp_result:
                complements.append({
                    "nutrient": row["nutrient"],
                    "nutrient_type": row["nutrient_type"],
                    "context": row["context"] or "",
                    "evidence": {
                        "source_id": row["source_id"] or "",
                        "source_type": row["source_type"],
                        "journal": row["journal"] or "",
                        "pub_date": row["pub_date"] or "",
                    },
                })

            if contraindications or complements:
                interactions.append({
                    "drug": drug,
                    "contraindications": contraindications,
                    "complements": complements,
                })

    return {"interactions": interactions, "disclaimer": _DRUG_DISCLAIMER}


_DISCLAIMER = (
    "Mechanism information is for educational purposes. "
    "Consult your healthcare provider for diagnosis and treatment."
)

_DRUG_DISCLAIMER = (
    "Drug interaction information is for educational purposes only. "
    "Do NOT change medication or diet without consulting your doctor or pharmacist."
)
