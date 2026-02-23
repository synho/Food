#!/usr/bin/env python3
"""
KG 상태 모니터링. 레포 루트에서 실행: python3 scripts/kg_status.py

- 파이프라인: master_graph.json triples 수, source_id 보유 건수, 고유 논문 수
- Neo4j: 노드/관계 수, 라벨별·관계타입별 집계 (선택)

환경변수: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD (기본값: bolt://localhost:7687, foodnot4self)
  --no-neo4j   Neo4j 조회 생략 (파이프라인만)
  --json       머신 출력 (JSON)
"""
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
KG_ROOT = REPO_ROOT / "kg_pipeline"
MASTER_GRAPH = KG_ROOT / "data" / "extracted_triples" / "master_graph.json"
MANIFESTS_DIR = KG_ROOT / "data" / "manifests"


def pipeline_stats():
    """파이프라인 산출물 기준 통계."""
    out = {"triples": 0, "with_source_id": 0, "unique_sources": 0, "master_exists": False}
    if not MASTER_GRAPH.exists():
        return out
    out["master_exists"] = True
    try:
        with open(MASTER_GRAPH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return out
    if not isinstance(data, list):
        return out
    triples = data
    out["triples"] = len(triples)
    with_sid = [t for t in triples if t.get("source_id")]
    out["with_source_id"] = len(with_sid)
    out["unique_sources"] = len(set(t.get("source_id") for t in with_sid if t.get("source_id")))
    return out


def neo4j_stats():
    """Neo4j 그래프 통계 (노드/관계 수, 라벨·타입별)."""
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "foodnot4self")
    password = os.getenv("NEO4J_PASSWORD", "foodnot4self")
    try:
        from neo4j import GraphDatabase
    except ImportError:
        return {"error": "neo4j package not installed (pip install neo4j)"}
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
    except Exception as e:
        return {"error": str(e)}
    out = {"nodes": 0, "relationships": 0, "by_label": {}, "by_relationship_type": {}}
    try:
        with driver.session() as session:
            r = session.run("MATCH (n) RETURN count(n) AS c")
            out["nodes"] = r.single()["c"] or 0
            r = session.run("MATCH ()-[r]->() RETURN count(r) AS c")
            out["relationships"] = r.single()["c"] or 0
            r = session.run("""
                MATCH (n)
                WITH labels(n) AS lbls
                WHERE size(lbls) > 0
                WITH lbls[0] AS lbl
                RETURN lbl, count(*) AS c
                ORDER BY c DESC
            """)
            out["by_label"] = {rec["lbl"]: rec["c"] for rec in r}
            r = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) AS t, count(*) AS c
                ORDER BY c DESC
            """)
            out["by_relationship_type"] = {rec["t"]: rec["c"] for rec in r}
    except Exception as e:
        out["error"] = str(e)
    finally:
        driver.close()
    return out


def main():
    no_neo4j = "--no-neo4j" in sys.argv
    as_json = "--json" in sys.argv
    args = [a for a in sys.argv[1:] if a in ("--no-neo4j", "--json")]

    pl = pipeline_stats()
    neo = {} if no_neo4j else neo4j_stats()

    if as_json:
        print(json.dumps({"pipeline": pl, "neo4j": neo}, ensure_ascii=False, indent=2))
        sys.exit(0 if pl["triples"] or neo.get("nodes", 0) else 1)

    # 사람이 읽기 쉬운 출력
    print("Knowledge Graph — 상태")
    print("-" * 50)
    print("파이프라인 (master_graph.json)")
    if not pl["master_exists"]:
        print("  master_graph.json 없음 — run_pipeline.py 실행 필요")
    else:
        print(f"  triples:        {pl['triples']:,}건")
        print(f"  source_id 있음: {pl['with_source_id']:,}건")
        print(f"  고유 논문 수:   {pl['unique_sources']:,}개")
        if pl["triples"] > 0 and pl["with_source_id"] < pl["triples"]:
            print("  \033[93m경고: source_id 없는 triple 있음 (zero-error 규칙)\033[0m")
    print()
    print("Neo4j (그래프 DB)")
    if no_neo4j:
        print("  (--no-neo4j 로 생략)")
    elif neo.get("error"):
        print(f"  \033[91m연결 실패: {neo['error']}\033[0m")
    else:
        print(f"  노드:           {neo.get('nodes', 0):,}개")
        print(f"  관계:           {neo.get('relationships', 0):,}개")
        if neo.get("by_label"):
            print("  라벨별:")
            for lbl, c in list(neo["by_label"].items())[:12]:
                print(f"    {lbl}: {c:,}")
            if len(neo["by_label"]) > 12:
                print(f"    ... 외 {len(neo['by_label']) - 12}개")
        if neo.get("by_relationship_type"):
            print("  관계 타입별:")
            for t, c in list(neo["by_relationship_type"].items())[:10]:
                print(f"    {t}: {c:,}")
            if len(neo["by_relationship_type"]) > 10:
                print(f"    ... 외 {len(neo['by_relationship_type']) - 10}개")
    print("-" * 50)

    has_data = pl["triples"] > 0 or (neo.get("nodes", 0) or 0) > 0
    sys.exit(0 if has_data else 1)


if __name__ == "__main__":
    main()
