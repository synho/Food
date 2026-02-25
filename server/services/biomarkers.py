"""
Biomarker service — given conditions, find relevant biomarkers and foods that improve them.
Queries the medical KG layer: Biomarker -BIOMARKER_FOR-> Disease,
Food/Nutrient -INCREASES_BIOMARKER/DECREASES_BIOMARKER-> Biomarker.
"""
from server.neo4j_client import get_driver
from server.canonical import normalize_entity_name


def get_biomarkers(conditions: list[str]) -> dict:
    """
    Given conditions, find:
    1. Biomarkers linked to those conditions (BIOMARKER_FOR)
    2. Foods/Nutrients that improve those biomarkers (DECREASES/INCREASES_BIOMARKER)
    """
    if not conditions:
        return {"biomarkers": [], "disclaimer": _DISCLAIMER}

    driver = get_driver()
    if driver is None:
        return {"biomarkers": [], "error": "Neo4j unavailable", "disclaimer": _DISCLAIMER}

    normalized = [normalize_entity_name(c) for c in conditions if c.strip()]

    biomarkers = []
    with driver.session() as session:
        for condition in normalized:
            # Find biomarkers for this condition
            result = session.run("""
                MATCH (b:Biomarker)-[r:BIOMARKER_FOR]->(d:Disease)
                WHERE toLower(d.name) = toLower($condition)
                   OR toLower(d.display_name) = toLower($condition)
                WITH b, r, d
                OPTIONAL MATCH (f)-[fr:DECREASES_BIOMARKER|INCREASES_BIOMARKER]->(b)
                WHERE (f:Food OR f:Nutrient) AND fr.source_id IS NOT NULL
                RETURN
                    COALESCE(b.display_name, b.name) AS biomarker,
                    COALESCE(d.display_name, d.name) AS disease,
                    r.context AS biomarker_context,
                    r.source_id AS biomarker_source_id,
                    r.journal AS biomarker_journal,
                    r.pub_date AS biomarker_pub_date,
                    COLLECT(DISTINCT {
                        food: COALESCE(f.display_name, f.name),
                        direction: type(fr),
                        context: fr.context,
                        source_id: fr.source_id,
                        journal: fr.journal,
                        pub_date: fr.pub_date,
                        source_type: COALESCE(fr.source_type, 'PMC')
                    }) AS food_links
            """, condition=condition)

            for row in result:
                # Filter out null food_links (from OPTIONAL MATCH)
                food_links = [
                    fl for fl in row["food_links"]
                    if fl.get("food") and fl.get("source_id")
                ]
                biomarkers.append({
                    "biomarker": row["biomarker"],
                    "disease": row["disease"],
                    "evidence": {
                        "source_id": row["biomarker_source_id"] or "",
                        "context": row["biomarker_context"] or "",
                        "journal": row["biomarker_journal"] or "",
                        "pub_date": row["biomarker_pub_date"] or "",
                    },
                    "food_recommendations": [
                        {
                            "food": fl["food"],
                            "direction": "decreases" if fl["direction"] == "DECREASES_BIOMARKER" else "increases",
                            "context": fl.get("context") or "",
                            "evidence": {
                                "source_id": fl["source_id"],
                                "source_type": fl.get("source_type", "PMC"),
                                "journal": fl.get("journal") or "",
                                "pub_date": fl.get("pub_date") or "",
                            },
                        }
                        for fl in food_links
                    ],
                })

    return {"biomarkers": biomarkers, "disclaimer": _DISCLAIMER}


_DISCLAIMER = (
    "Biomarker information is for educational purposes. "
    "Consult your healthcare provider for diagnosis and treatment."
)
