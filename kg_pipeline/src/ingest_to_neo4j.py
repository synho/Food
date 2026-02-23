from neo4j import GraphDatabase
import json
import os
from dotenv import load_dotenv

from config_loader import get_paths_config
from ontology import normalize_entity_type, normalize_predicate
from artifacts import AGENT_EXTRACT, AGENT_INGEST, get_run_id, read_manifest, write_manifest

load_dotenv()

# Neo4j connection details (project default id/password: foodnot4self)
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "foodnot4self")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "foodnot4self")

class KnowledgeGraphIngestor:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def setup_schema(self):
        """Create indexes for all entity types. Idempotent (IF NOT EXISTS)."""
        labels = [
            "Food", "Disease", "Symptom", "Nutrient", "Drug",
            "LifestyleFactor", "BodySystem", "AgeRelatedChange", "LifeStage",
            "Study",  # Reserved for future evidence graph; no Study nodes ingested yet
        ]
        with self.driver.session() as session:
            for label in labels:
                session.run(f"CREATE INDEX IF NOT EXISTS FOR (n:{label}) ON (n.name)")
        print(f"Schema indexes created/verified for: {', '.join(labels)}")

    def ingest_triples(self, triples):
        skipped = 0
        with self.driver.session() as session:
            for triple in triples:
                if not triple.get("source_id"):
                    subj = triple.get("subject", "?")
                    pred = triple.get("predicate", "?")
                    obj = triple.get("object", "?")
                    print(f"WARNING: skipping triple with missing source_id: {subj} --{pred}--> {obj}")
                    skipped += 1
                    continue
                session.execute_write(self._create_relationship, triple)
        if skipped:
            print(f"WARNING: {skipped} triple(s) skipped due to missing source_id (zero-error rule).")

    @staticmethod
    def _create_relationship(tx, triple):
        subject_name = triple.get("subject", "").strip()
        object_name = triple.get("object", "").strip()
        if not subject_name or not object_name:
            return
        # Ontology-based labels (safe for Cypher)
        subject_label = normalize_entity_type(triple.get("subject_type", ""))
        object_label = normalize_entity_type(triple.get("object_type", ""))
        predicate = normalize_predicate(triple.get("predicate", ""))
        # Sanitize for Cypher: relationship type must be valid identifier
        rel_type = predicate.replace("-", "_").replace(" ", "_")
        source_id = triple.get("source_id", "")

        # Fix: include source_id in MERGE so each (subject, predicate, object, source) gets its own
        # relationship — prior evidence from other papers is never overwritten.
        query = f"""
        MERGE (s:{subject_label} {{name: $subject_name}})
        MERGE (o:{object_label} {{name: $object_name}})
        MERGE (s)-[r:{rel_type} {{source_id: $source_id}}]->(o)
        SET r.context = $context,
            r.source_type = $source_type,
            r.journal = $journal,
            r.pub_date = $pub_date,
            r.evidence_type = $evidence_type,
            r.evidence_strength = $evidence_strength
        """
        tx.run(query,
               subject_name=subject_name,
               object_name=object_name,
               context=triple.get("context", ""),
               source_id=source_id,
               source_type=triple.get("source_type", "PMC"),
               journal=triple.get("journal", ""),
               pub_date=triple.get("pub_date", ""),
               evidence_type=triple.get("evidence_type", ""),
               evidence_strength=int(triple.get("evidence_strength", 1)))

def main():
    paths = get_paths_config()
    run_id = get_run_id()
    # Cascade: optional master_graph from previous (extract) manifest
    master_file = paths.get("master_graph") or os.path.join(paths["extracted_triples"], "master_graph.json")
    prev = read_manifest(AGENT_EXTRACT, run_id)
    if prev and prev.get("master_graph_path") and os.path.exists(prev["master_graph_path"]):
        master_file = prev["master_graph_path"]
    if not os.path.exists(master_file):
        print(f"Master graph file not found: {master_file}")
        return

    with open(master_file, "r") as f:
        triples = json.load(f)

    print(f"Ingesting {len(triples)} triples into Neo4j...")
    try:
        ingestor = KnowledgeGraphIngestor(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
        ingestor.setup_schema()
        ingestor.ingest_triples(triples)
        ingestor.close()
        write_manifest(AGENT_INGEST, run_id, {
            "triples_ingested": len(triples),
            "master_graph_path": master_file,
            "status": "ok",
        })
        print("Ingestion complete.")
    except Exception as e:
        write_manifest(AGENT_INGEST, run_id, {"status": "error", "error": str(e)})
        print(f"Failed to ingest to Neo4j: {e}")
        print("Tip: Neo4j auth defaults: user/password foodnot4self. Set NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD in .env to override.")

if __name__ == "__main__":
    main()
