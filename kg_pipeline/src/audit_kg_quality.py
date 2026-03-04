#!/usr/bin/env python3
"""
KG Quality Audit — periodic health check that queries Neo4j and produces a
quantitative quality report. No LLM calls, purely graph introspection.

Metrics:
  - Duplicate node groups (same name, different case)
  - Non-standard entity type labels
  - RELATES_TO / AFFECTS percentage
  - Empty journal / evidence_type percentages
  - Contradiction count (opposing predicates on same subject-object)
  - Orphan nodes (zero relationships)
  - Evidence strength distribution
  - Per-label node counts
  - Unique source count

Output:
  - Console summary
  - JSON report to data/audit_quality_report.json (with timestamped snapshots)

Usage:
    python src/audit_kg_quality.py                    # full audit
    python src/audit_kg_quality.py --output report.json
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

from ontology import ENTITY_TYPES, WEAK_PREDICATES

# Opposing predicate pairs for contradiction detection
_OPPOSING_PREDICATES = [
    ("REDUCES_RISK_OF", "INCREASES_RISK_OF"),
    ("ALLEVIATES", "AGGRAVATES"),
    ("PREVENTS", "CAUSES"),
    ("TREATS", "CAUSES"),
    ("INCREASES_BIOMARKER", "DECREASES_BIOMARKER"),
]


def audit(
    uri: str = "bolt://localhost:7687",
    user: str = "foodnot4self",
    pw: str = "foodnot4self",
) -> dict:
    """Run full KG quality audit. Returns report dict."""
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(uri, auth=(user, pw))
    report: dict = {"timestamp": datetime.now(timezone.utc).isoformat()}

    try:
        with driver.session() as session:
            # ── Basic counts ──────────────────────────────────────────────
            total_nodes = session.run("MATCH (n) RETURN count(n) AS cnt").single()["cnt"]
            total_rels = session.run("MATCH ()-[r]->() RETURN count(r) AS cnt").single()["cnt"]
            report["total_nodes"] = total_nodes
            report["total_relationships"] = total_rels

            # ── Unique sources ────────────────────────────────────────────
            unique_sources = session.run(
                "MATCH ()-[r]->() WHERE r.source_id IS NOT NULL AND r.source_id <> '' "
                "RETURN count(DISTINCT r.source_id) AS cnt"
            ).single()["cnt"]
            report["unique_sources"] = unique_sources

            # ── Per-label node counts ─────────────────────────────────────
            label_counts = {}
            result = session.run("""
                CALL db.labels() YIELD label
                CALL {
                    WITH label
                    MATCH (n) WHERE label IN labels(n)
                    RETURN count(n) AS cnt
                }
                RETURN label, cnt ORDER BY cnt DESC
            """)
            for r in result:
                label_counts[r["label"]] = r["cnt"]
            report["node_counts_by_label"] = label_counts

            # ── Non-standard labels ───────────────────────────────────────
            valid_labels = set(ENTITY_TYPES)
            nonstandard = {lb: ct for lb, ct in label_counts.items() if lb not in valid_labels}
            report["nonstandard_labels"] = nonstandard
            report["nonstandard_node_count"] = sum(nonstandard.values())

            # ── Duplicate node groups (case-insensitive) ──────────────────
            dup_result = session.run("""
                MATCH (n)
                WITH toLower(n.name) AS key, collect(n.name) AS names, count(*) AS cnt
                WHERE cnt > 1
                RETURN count(*) AS groups, sum(cnt) - count(*) AS excess_nodes
            """).single()
            report["duplicate_groups"] = dup_result["groups"]
            report["duplicate_excess_nodes"] = dup_result["excess_nodes"]

            # ── Weak predicate relationships ──────────────────────────────
            weak_pred_list = list(WEAK_PREDICATES)
            weak_count = 0
            for wp in weak_pred_list:
                try:
                    cnt = session.run(
                        f"MATCH ()-[r:{wp}]->() RETURN count(r) AS cnt"
                    ).single()["cnt"]
                    weak_count += cnt
                except Exception:
                    pass
            report["weak_predicate_count"] = weak_count
            report["weak_predicate_pct"] = round(100 * weak_count / max(total_rels, 1), 1)

            # ── Empty journal ─────────────────────────────────────────────
            empty_journal = session.run("""
                MATCH ()-[r]->()
                WHERE r.journal IS NULL OR r.journal = ''
                RETURN count(r) AS cnt
            """).single()["cnt"]
            report["empty_journal_count"] = empty_journal
            report["empty_journal_pct"] = round(100 * empty_journal / max(total_rels, 1), 1)

            # ── Empty evidence_type ───────────────────────────────────────
            empty_evidence = session.run("""
                MATCH ()-[r]->()
                WHERE r.evidence_type IS NULL OR r.evidence_type = ''
                RETURN count(r) AS cnt
            """).single()["cnt"]
            report["empty_evidence_type_count"] = empty_evidence
            report["empty_evidence_type_pct"] = round(100 * empty_evidence / max(total_rels, 1), 1)

            # ── Evidence strength distribution ────────────────────────────
            strength_dist = {}
            result = session.run("""
                MATCH ()-[r]->()
                WHERE r.evidence_strength IS NOT NULL
                RETURN r.evidence_strength AS strength, count(r) AS cnt
                ORDER BY strength
            """)
            for r in result:
                strength_dist[str(r["strength"])] = r["cnt"]
            report["evidence_strength_distribution"] = strength_dist

            # ── Contradictions ────────────────────────────────────────────
            contradictions = []
            for pred_a, pred_b in _OPPOSING_PREDICATES:
                try:
                    result = session.run(f"""
                        MATCH (a)-[r1:{pred_a}]->(b)
                        MATCH (a)-[r2:{pred_b}]->(b)
                        RETURN a.name AS subject, b.name AS object,
                               '{pred_a}' AS pred_a, '{pred_b}' AS pred_b,
                               r1.source_id AS source_a, r2.source_id AS source_b
                    """)
                    for r in result:
                        contradictions.append({
                            "subject": r["subject"],
                            "object": r["object"],
                            "predicate_a": r["pred_a"],
                            "predicate_b": r["pred_b"],
                            "source_a": r["source_a"],
                            "source_b": r["source_b"],
                        })
                except Exception:
                    pass
            report["contradiction_count"] = len(contradictions)
            report["contradictions"] = contradictions[:50]  # cap for report size

            # ── Orphan nodes ──────────────────────────────────────────────
            orphan_count = session.run("""
                MATCH (n) WHERE NOT (n)--()
                RETURN count(n) AS cnt
            """).single()["cnt"]
            report["orphan_nodes"] = orphan_count

            # ── Missing source_id ─────────────────────────────────────────
            missing_source = session.run("""
                MATCH ()-[r]->()
                WHERE r.source_id IS NULL OR r.source_id = ''
                RETURN count(r) AS cnt
            """).single()["cnt"]
            report["missing_source_id_count"] = missing_source
            report["source_id_coverage_pct"] = round(
                100 * (total_rels - missing_source) / max(total_rels, 1), 1
            )

    finally:
        driver.close()

    return report


def print_report(report: dict) -> None:
    """Print human-readable summary."""
    print("\n" + "=" * 60)
    print("  KG QUALITY AUDIT REPORT")
    print("=" * 60)
    print(f"  Timestamp:      {report['timestamp']}")
    print(f"  Total nodes:    {report['total_nodes']:,}")
    print(f"  Total rels:     {report['total_relationships']:,}")
    print(f"  Unique sources: {report['unique_sources']:,}")
    print()

    print("  Node counts by label:")
    for label, count in sorted(report["node_counts_by_label"].items(), key=lambda x: -x[1]):
        marker = " ⚠" if label in report.get("nonstandard_labels", {}) else ""
        print(f"    {label:30s} {count:6,}{marker}")
    print()

    print("  Quality Metrics:")
    print(f"    Duplicate groups:     {report['duplicate_groups']:,} ({report['duplicate_excess_nodes']:,} excess nodes)")
    print(f"    Non-standard types:   {report['nonstandard_node_count']:,} nodes in {len(report['nonstandard_labels'])} labels")
    print(f"    Weak predicates:      {report['weak_predicate_count']:,} ({report['weak_predicate_pct']}%)")
    print(f"    Empty journal:        {report['empty_journal_count']:,} ({report['empty_journal_pct']}%)")
    print(f"    Empty evidence_type:  {report['empty_evidence_type_count']:,} ({report['empty_evidence_type_pct']}%)")
    print(f"    Source ID coverage:   {report['source_id_coverage_pct']}%")
    print(f"    Contradictions:       {report['contradiction_count']}")
    print(f"    Orphan nodes:         {report['orphan_nodes']}")
    print()

    if report.get("evidence_strength_distribution"):
        print("  Evidence strength distribution:")
        for strength, count in sorted(report["evidence_strength_distribution"].items()):
            print(f"    Strength {strength}: {count:,}")
    print()

    if report.get("contradictions"):
        print("  Sample contradictions:")
        for c in report["contradictions"][:10]:
            print(f"    {c['subject']} —[{c['predicate_a']}]→ {c['object']}")
            print(f"    {c['subject']} —[{c['predicate_b']}]→ {c['object']}")
            print(f"      Sources: {c['source_a']} vs {c['source_b']}")
            print()

    print("=" * 60)


def save_report(report: dict, output_path: str) -> None:
    """Save report to JSON with timestamped snapshots for trend tracking."""
    history = []
    if os.path.exists(output_path):
        try:
            with open(output_path, "r") as f:
                existing = json.load(f)
            if isinstance(existing, list):
                history = existing
            elif isinstance(existing, dict):
                history = [existing]
        except (json.JSONDecodeError, OSError):
            pass

    history.append(report)
    # Keep last 100 snapshots
    history = history[-100:]

    with open(output_path, "w") as f:
        json.dump(history, f, indent=2)
    print(f"Report saved to {output_path} ({len(history)} snapshot(s))")


def main():
    parser = argparse.ArgumentParser(description="KG Quality Audit — quantitative health check")
    parser.add_argument("--output", type=str, default="data/audit_quality_report.json",
                        help="Output JSON path (default: data/audit_quality_report.json)")
    args = parser.parse_args()

    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "foodnot4self")
    pw = os.getenv("NEO4J_PASSWORD", "foodnot4self")

    report_data = audit(uri=uri, user=user, pw=pw)
    print_report(report_data)
    save_report(report_data, args.output)


if __name__ == "__main__":
    main()
