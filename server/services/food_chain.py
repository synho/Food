"""
Food-chain multi-hop query service.
Returns the Food → Nutrient → Disease/Symptom chain from the KG,
giving clients the "why" trail behind a food recommendation.

Example: GET /api/kg/food-chain?food=Salmon
  → Salmon -CONTAINS-> Omega-3 -PREVENTS-> Cardiovascular disease
"""
from server.neo4j_client import get_driver


def get_food_chain(food: str) -> dict:
    """
    Query the 2-hop chain: (Food)-[:CONTAINS]->(Nutrient)-[r]->(Disease|Symptom)
    Returns all chains as a list of {nutrient, relationship_type, target, target_type, evidence[]}.
    """
    driver = get_driver()
    if driver is None:
        return {"food": food, "chain": [], "error": "Neo4j not available"}

    # Match the 2-hop chain; include any relationship type from Nutrient outward
    cypher = """
    MATCH (f:Food {name: $food})-[c:CONTAINS]->(n:Nutrient)-[r]->(d)
    WHERE d:Disease OR d:Symptom
    RETURN
        n.name AS nutrient,
        type(r) AS relationship_type,
        d.name AS target,
        labels(d)[0] AS target_type,
        r.source_id AS source_id,
        r.context AS context,
        r.journal AS journal,
        r.pub_date AS pub_date,
        r.source_type AS source_type,
        r.evidence_type AS evidence_type,
        c.source_id AS contains_source_id,
        c.context AS contains_context
    ORDER BY n.name, relationship_type, d.name
    LIMIT 50
    """

    try:
        with driver.session() as session:
            result = session.run(cypher, food=food)
            rows = [dict(r) for r in result]
    except Exception as e:
        return {"food": food, "chain": [], "error": str(e)}

    # Group by (nutrient, relationship_type, target) and aggregate evidence
    grouped: dict[tuple, dict] = {}
    for row in rows:
        key = (row["nutrient"], row["relationship_type"], row["target"])
        if key not in grouped:
            grouped[key] = {
                "nutrient": row["nutrient"],
                "relationship_type": row["relationship_type"],
                "target": row["target"],
                "target_type": row["target_type"],
                "contains_evidence": [],
                "evidence": [],
            }
        # Evidence for the Nutrient → target relationship
        if row.get("source_id"):
            ev = {
                "source_id": row["source_id"],
                "context": row.get("context") or "",
                "journal": row.get("journal") or "",
                "pub_date": row.get("pub_date") or "",
                "source_type": row.get("source_type") or "PMC",
                "evidence_type": row.get("evidence_type") or "",
            }
            if ev not in grouped[key]["evidence"]:
                grouped[key]["evidence"].append(ev)
        # Evidence for the Food → Nutrient CONTAINS relationship
        if row.get("contains_source_id"):
            cev = {
                "source_id": row["contains_source_id"],
                "context": row.get("contains_context") or "",
                "journal": "",
                "pub_date": "",
                "source_type": "PMC",
                "evidence_type": "",
            }
            if cev not in grouped[key]["contains_evidence"]:
                grouped[key]["contains_evidence"].append(cev)

    chain = list(grouped.values())
    return {"food": food, "chain": chain}
