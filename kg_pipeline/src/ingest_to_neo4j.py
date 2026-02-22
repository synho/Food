from neo4j import GraphDatabase
import json
import os
from dotenv import load_dotenv

load_dotenv()

# Neo4j connection details
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

class KnowledgeGraphIngestor:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def ingest_triples(self, triples):
        with self.driver.session() as session:
            for triple in triples:
                session.execute_write(self._create_relationship, triple)

    @staticmethod
    def _create_relationship(tx, triple):
        # Clean labels to remove spaces
        subject_label = triple["subject_type"].replace(" ", "_").capitalize()
        object_label = triple["object_type"].replace(" ", "_").capitalize()
        predicate = triple["predicate"].upper()

        # Cypher query to create nodes and a relationship
        query = f"""
        MERGE (s:{subject_label} {{name: $subject_name}})
        MERGE (o:{object_label} {{name: $object_name}})
        MERGE (s)-[r:{predicate}]->(o)
        SET r.context = $context,
            r.source_id = $source_id
        """
        tx.run(query, 
               subject_name=triple["subject"], 
               object_name=triple["object"], 
               context=triple.get("context", ""), 
               source_id=triple.get("source_id", ""))

def main():
    master_file = "data/extracted_triples/master_graph.json"
    if not os.path.exists(master_file):
        print(f"Master graph file not found: {master_file}")
        return

    with open(master_file, "r") as f:
        triples = json.load(f)

    print(f"Ingesting {len(triples)} triples into Neo4j...")
    
    # NOTE: Ensure Neo4j is running and environment variables are set
    try:
        ingestor = KnowledgeGraphIngestor(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
        ingestor.ingest_triples(triples)
        ingestor.close()
        print("Ingestion complete.")
    except Exception as e:
        print(f"Failed to ingest to Neo4j: {e}")
        print("Tip: Make sure Neo4j is running locally at bolt://localhost:7687 or update the .env file.")

if __name__ == "__main__":
    main()
