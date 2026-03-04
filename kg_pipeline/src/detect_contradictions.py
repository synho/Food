#!/usr/bin/env python3
"""
Contradiction Detector — finds opposing predicates on the same subject-object pairs.

Queries Neo4j for predicate pairs that indicate contradictory evidence, e.g.:
  - A -REDUCES_RISK_OF-> B  AND  A -INCREASES_RISK_OF-> B
  - A -ALLEVIATES-> B       AND  A -AGGRAVATES-> B
  - A -PREVENTS-> B         AND  A -CAUSES-> B

Output:
  - Console summary
  - JSON report to data/contradictions_report.json

Usage:
    python src/detect_contradictions.py
    python src/detect_contradictions.py --output custom_report.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Opposing predicate pairs
OPPOSING_PAIRS = [
    ("REDUCES_RISK_OF", "INCREASES_RISK_OF"),
    ("ALLEVIATES", "AGGRAVATES"),
    ("PREVENTS", "CAUSES"),
    ("TREATS", "CAUSES"),
    ("TREATS", "AGGRAVATES"),
    ("INCREASES_BIOMARKER", "DECREASES_BIOMARKER"),
]


def detect_contradictions(
    uri: str = "bolt://localhost:7687",
    user: str = "foodnot4self",
    pw: str = "foodnot4self",
) -> dict:
    """Find all contradictory evidence pairs in the KG. Returns report dict."""
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(uri, auth=(user, pw))
    report: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pairs_checked": len(OPPOSING_PAIRS),
        "contradictions": [],
        "summary_by_pair": {},
    }

    try:
        for pred_a, pred_b in OPPOSING_PAIRS:
            pair_key = f"{pred_a} vs {pred_b}"
            try:
                with driver.session() as session:
                    result = session.run(f"""
                        MATCH (a)-[r1:{pred_a}]->(b)
                        MATCH (a)-[r2:{pred_b}]->(b)
                        RETURN a.name AS subject, labels(a) AS subject_labels,
                               b.name AS object, labels(b) AS object_labels,
                               r1.source_id AS source_a, r1.context AS context_a,
                               r1.journal AS journal_a, r1.pub_date AS pub_date_a,
                               r1.evidence_type AS evidence_type_a,
                               r1.evidence_strength AS strength_a,
                               r2.source_id AS source_b, r2.context AS context_b,
                               r2.journal AS journal_b, r2.pub_date AS pub_date_b,
                               r2.evidence_type AS evidence_type_b,
                               r2.evidence_strength AS strength_b
                    """)
                    pair_contradictions = []
                    for r in result:
                        pair_contradictions.append({
                            "subject": r["subject"],
                            "subject_labels": r["subject_labels"],
                            "object": r["object"],
                            "object_labels": r["object_labels"],
                            "predicate_a": pred_a,
                            "evidence_a": {
                                "source_id": r["source_a"],
                                "context": r["context_a"],
                                "journal": r["journal_a"],
                                "pub_date": r["pub_date_a"],
                                "evidence_type": r["evidence_type_a"],
                                "evidence_strength": r["strength_a"],
                            },
                            "predicate_b": pred_b,
                            "evidence_b": {
                                "source_id": r["source_b"],
                                "context": r["context_b"],
                                "journal": r["journal_b"],
                                "pub_date": r["pub_date_b"],
                                "evidence_type": r["evidence_type_b"],
                                "evidence_strength": r["strength_b"],
                            },
                        })
                    report["summary_by_pair"][pair_key] = len(pair_contradictions)
                    report["contradictions"].extend(pair_contradictions)
            except Exception as e:
                report["summary_by_pair"][pair_key] = f"error: {e}"

    finally:
        driver.close()

    report["total_contradictions"] = len(report["contradictions"])
    return report


def print_report(report: dict) -> None:
    """Print human-readable summary."""
    print("\n" + "=" * 60)
    print("  CONTRADICTION DETECTION REPORT")
    print("=" * 60)
    print(f"  Timestamp:           {report['timestamp']}")
    print(f"  Predicate pairs:     {report['pairs_checked']}")
    print(f"  Total contradictions: {report['total_contradictions']}")
    print()

    print("  Contradictions by predicate pair:")
    for pair, count in report["summary_by_pair"].items():
        print(f"    {pair}: {count}")
    print()

    if report["contradictions"]:
        print("  Details:")
        for c in report["contradictions"]:
            print(f"    {c['subject']} —[{c['predicate_a']}]→ {c['object']}")
            print(f"      Source: {c['evidence_a']['source_id']} | "
                  f"{c['evidence_a']['journal'] or '?'} | "
                  f"{c['evidence_a']['evidence_type'] or '?'}")
            print(f"    {c['subject']} —[{c['predicate_b']}]→ {c['object']}")
            print(f"      Source: {c['evidence_b']['source_id']} | "
                  f"{c['evidence_b']['journal'] or '?'} | "
                  f"{c['evidence_b']['evidence_type'] or '?'}")
            print()

    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Contradiction Detector — find opposing evidence in KG")
    parser.add_argument("--output", type=str, default="data/contradictions_report.json",
                        help="Output JSON path (default: data/contradictions_report.json)")
    args = parser.parse_args()

    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "foodnot4self")
    pw = os.getenv("NEO4J_PASSWORD", "foodnot4self")

    report_data = detect_contradictions(uri=uri, user=user, pw=pw)
    print_report(report_data)

    with open(args.output, "w") as f:
        json.dump(report_data, f, indent=2)
    print(f"Report saved to {args.output}")


if __name__ == "__main__":
    main()
