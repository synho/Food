"""
Evidence Contradiction Detector — finds entities that both help and harm the same disease.

Detects cases where the KG has conflicting evidence, e.g. Omega-3 both PREVENTS and
AGGRAVATES the same disease from different papers. Flags weaker side as 'contested'
or both as 'debated' when evidence is roughly equal.

Runs post-ingest or on-demand via API.
"""
from __future__ import annotations

from server.neo4j_client import run_query, get_driver
from server.db import save_contradiction, get_contradictions


# Positive predicates: entity helps with disease
_POSITIVE = ["PREVENTS", "TREATS", "ALLEVIATES", "REDUCES_RISK_OF"]
# Negative predicates: entity harms / worsens disease
_NEGATIVE = ["AGGRAVATES", "CAUSES", "INCREASES_RISK_OF"]


def detect_contradictions() -> list[dict]:
    """
    Query Neo4j for entities that have both positive and negative relationships
    to the same disease. Classify each contradiction and persist to SQLite.

    Returns list of contradiction records.
    """
    query = """
    MATCH (f)-[r1]->(d:Disease)
    WHERE type(r1) IN $positive_rels
      AND r1.source_id IS NOT NULL
      AND (f:Food OR f:Nutrient OR f:LifestyleFactor)
    WITH f, d, type(r1) AS pos_type,
         count(DISTINCT r1) AS pos_count,
         avg(COALESCE(r1.evidence_strength, 1)) AS pos_strength
    MATCH (f)-[r2]->(d)
    WHERE type(r2) IN $negative_rels
      AND r2.source_id IS NOT NULL
    WITH f.name AS entity, d.name AS disease,
         pos_type, pos_count, pos_strength,
         type(r2) AS neg_type,
         count(DISTINCT r2) AS neg_count,
         avg(COALESCE(r2.evidence_strength, 1)) AS neg_strength
    RETURN entity, disease,
           pos_type, pos_count, pos_strength,
           neg_type, neg_count, neg_strength
    ORDER BY (pos_count + neg_count) DESC
    """
    rows = run_query(query, {
        "positive_rels": _POSITIVE,
        "negative_rels": _NEGATIVE,
    })

    results = []
    for row in rows:
        entity = row.get("entity") or ""
        disease = row.get("disease") or ""
        pos_count = row.get("pos_count", 0)
        neg_count = row.get("neg_count", 0)
        pos_strength = row.get("pos_strength")
        neg_strength = row.get("neg_strength")

        # Classify the contradiction
        if pos_count >= 2 * neg_count and (pos_strength or 1) >= (neg_strength or 1):
            verdict = "negative_contested"
        elif neg_count >= 2 * pos_count and (neg_strength or 1) >= (pos_strength or 1):
            verdict = "positive_contested"
        else:
            verdict = "debated"

        record = {
            "entity": entity,
            "disease": disease,
            "positive_rel": row.get("pos_type", ""),
            "pos_count": pos_count,
            "pos_strength": pos_strength,
            "negative_rel": row.get("neg_type", ""),
            "neg_count": neg_count,
            "neg_strength": neg_strength,
            "verdict": verdict,
        }
        results.append(record)

        # Persist to SQLite
        save_contradiction(
            entity=entity, disease=disease,
            positive_rel=record["positive_rel"],
            pos_count=pos_count, pos_strength=pos_strength,
            negative_rel=record["negative_rel"],
            neg_count=neg_count, neg_strength=neg_strength,
            verdict=verdict,
        )

        # Mark relationships in Neo4j
        _mark_contested_in_neo4j(entity, disease, verdict)

    return results


def _mark_contested_in_neo4j(entity: str, disease: str, verdict: str) -> None:
    """Set contested/debated flags on Neo4j relationships."""
    try:
        driver = get_driver()
        with driver.session() as session:
            if verdict == "negative_contested":
                # Mark negative relationships as contested
                session.run("""
                    MATCH (f {name: $entity})-[r]->(d:Disease {name: $disease})
                    WHERE type(r) IN $neg_rels
                    SET r.contested = true
                """, entity=entity, disease=disease, neg_rels=_NEGATIVE)
            elif verdict == "positive_contested":
                # Mark positive relationships as contested
                session.run("""
                    MATCH (f {name: $entity})-[r]->(d:Disease {name: $disease})
                    WHERE type(r) IN $pos_rels
                    SET r.contested = true
                """, entity=entity, disease=disease, pos_rels=_POSITIVE)
            else:
                # Mark both sides as debated
                session.run("""
                    MATCH (f {name: $entity})-[r]->(d:Disease {name: $disease})
                    WHERE type(r) IN $all_rels
                    SET r.debated = true
                """, entity=entity, disease=disease,
                    all_rels=_POSITIVE + _NEGATIVE)
    except Exception:
        pass  # Non-critical: don't fail the pipeline for flag-setting
