"""
Neo4j client for KG queries. Uses same auth as kg_pipeline (foodnot4self).
Standardized: query and return canonical entity names from the graph.
"""
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from neo4j import GraphDatabase

# Load .env from cwd (repo root when uvicorn runs from root) and from server/
load_dotenv()
_load_path = Path(__file__).resolve().parent / ".env"
if _load_path.exists():
    load_dotenv(_load_path)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "foodnot4self")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "foodnot4self")

# Singleton driver — created once, reused across all requests.
_driver = None


def get_driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    return _driver


def close_driver():
    """Close the singleton driver. Call on application shutdown."""
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None


def run_query(query: str, parameters: dict[str, Any] | None = None) -> list[dict]:
    """Run a read query and return list of records as dicts."""
    with get_driver().session() as session:
        result = session.run(query, parameters or {})
        return [dict(record) for record in result]


def get_kg_stats() -> dict[str, Any]:
    """Return KG statistics for dashboard: nodes, relationships, by_label, by_relationship_type."""
    try:
        with get_driver().session() as session:
            r = session.run("MATCH (n) RETURN count(n) AS c")
            nodes = r.single()["c"] or 0
            r = session.run("MATCH ()-[r]->() RETURN count(r) AS c")
            relationships = r.single()["c"] or 0
            r = session.run("""
                MATCH (n)
                WITH labels(n) AS lbls WHERE size(lbls) > 0
                WITH lbls[0] AS lbl
                RETURN lbl, count(*) AS c ORDER BY c DESC
            """)
            by_label = {rec["lbl"]: rec["c"] for rec in r}
            r = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) AS t, count(*) AS c ORDER BY c DESC
            """)
            by_relationship_type = {rec["t"]: rec["c"] for rec in r}
        return {
            "nodes": nodes,
            "relationships": relationships,
            "by_label": by_label,
            "by_relationship_type": by_relationship_type,
        }
    except Exception as e:
        msg = str(e)
        is_connection_refused = "Connection refused" in msg or "Failed to establish" in msg or "Errno 61" in msg
        return {
            "error": msg,
            "error_type": "connection_refused" if is_connection_refused else "auth_error",
            "debug": {"uri": NEO4J_URI, "user": NEO4J_USER},
        }
