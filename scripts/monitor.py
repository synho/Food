#!/usr/bin/env python3
"""
모듈별 정상 동작 확인 (모니터링). 레포 루트에서 실행: python3 scripts/monitor.py

다른 앱이 3000/8000 등 포트를 쓰는 경우: 건너뛸 항목 지정.
  SKIP_CHECKS=web          → Web(3000) 검사 생략
  SKIP_CHECKS=server,web   → Server(8000), Web(3000) 생략
  (가능: neo4j, pipeline, server, web)

포트 충돌 회피: 다른 포트로 실행한 경우 아래 env로 모니터가 해당 주소를 확인.
  SERVER_URL=http://127.0.0.1:8001  WEB_URL=http://127.0.0.1:3001
  NEO4J_HTTP_URL=http://localhost:7474
"""
import json
import os
import sys
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

REPO_ROOT = Path(__file__).resolve().parent.parent
KG = REPO_ROOT / "kg_pipeline"
MASTER_GRAPH = KG / "data" / "extracted_triples" / "master_graph.json"

SKIP_ENV = os.environ.get("SKIP_CHECKS", "")
SKIP = set(s.strip().lower() for s in SKIP_ENV.split(",") if s.strip())

# 포트 충돌 회피: env로 URL 지정 가능. 기본 8001은 web/.env.local 및 run.sh start와 맞춤.
NEO4J_HTTP_URL = os.environ.get("NEO4J_HTTP_URL", "http://localhost:7474")
def _detect_server_url() -> str:
    """Try 8001 first (web/.env.local default), fall back to 8000."""
    forced = os.environ.get("SERVER_URL", "")
    if forced:
        return forced
    for port in (8001, 8000):
        try:
            urlopen(f"http://127.0.0.1:{port}/health", timeout=1)
            return f"http://127.0.0.1:{port}"
        except Exception:
            pass
    return "http://127.0.0.1:8001"

SERVER_URL = _detect_server_url()
WEB_URL = os.environ.get("WEB_URL", "http://127.0.0.1:3000")


def ok(msg: str) -> str:
    return f"\033[92mOK\033[0m  {msg}"


def fail(msg: str) -> str:
    return f"\033[91mFAIL\033[0m {msg}"


def skip(name: str) -> str:
    return f"\033[90mskip\033[0m  {name} (SKIP_CHECKS로 제외)"


def check_neo4j() -> str:
    if "neo4j" in SKIP:
        return skip("Neo4j")
    try:
        r = urlopen(f"{NEO4J_HTTP_URL.rstrip('/')}", timeout=2)
        if r.status == 200:
            return ok(f"Neo4j ({NEO4J_HTTP_URL}) 응답")
    except (URLError, HTTPError, OSError):
        pass
    return fail(f"Neo4j ({NEO4J_HTTP_URL}) 미응답 — Docker: docker compose up -d neo4j / Homebrew: brew services start neo4j")


def check_pipeline() -> str:
    if "pipeline" in SKIP:
        return skip("Pipeline")
    if not MASTER_GRAPH.exists():
        return fail("master_graph.json 없음 — run_pipeline.py 실행 필요")
    try:
        with open(MASTER_GRAPH) as f:
            data = json.load(f)
        n = len(data) if isinstance(data, list) else 0
        with_source = sum(1 for t in data if t.get("source_id")) if isinstance(data, list) else 0
        if n == 0:
            return fail("triples 0건")
        return ok(f"triples {n}건 (source_id {with_source}건)")
    except Exception as e:
        return fail(str(e))


def check_server() -> str:
    if "server" in SKIP:
        return skip("Server")
    base = SERVER_URL.rstrip("/")
    try:
        r = urlopen(f"{base}/health", timeout=2)
        if r.status != 200:
            return fail(f"Server ({SERVER_URL}) /health 비정상")
        # 8000에 다른 앱이 떠 있을 수 있음 — 우리 API인지 확인
        spec = urlopen(f"{base}/openapi.json", timeout=2)
        data = json.load(spec)
        title = (data.get("info") or {}).get("title") or ""
        if "Health Navigation" not in title:
            return fail(f"Server ({SERVER_URL})는 다른 앱입니다 (title={title}). uvicorn server.main:app 필요")
    except (URLError, HTTPError, OSError) as e:
        return fail(f"Server ({SERVER_URL}) 미응답 — uvicorn server.main:app 필요")
    return ok(f"Server ({SERVER_URL}) /health 응답")


def check_web() -> str:
    if "web" in SKIP:
        return skip("Web")
    try:
        r = urlopen(WEB_URL.rstrip("/"), timeout=2)
        if r.status == 200:
            return ok(f"Web ({WEB_URL}) 응답")
    except (URLError, HTTPError, OSError):
        pass
    return fail(f"Web ({WEB_URL}) 미응답 — cd web && npm run dev 필요")


def main():
    print("Health Navigation — 모듈 상태")
    if SKIP:
        print("(제외:", ", ".join(sorted(SKIP)) + ")")
    print("-" * 50)
    r_neo4j = check_neo4j()
    r_pipeline = check_pipeline()
    r_server = check_server()
    r_web = check_web()
    print("Neo4j     ", r_neo4j)
    print("Pipeline  ", r_pipeline)
    print("Server    ", r_server)
    print("Web       ", r_web)
    print("-" * 50)
    print("KG 상세:  make kg-status")
    # 제외되지 않은 항목만 실패로 exit 1
    if "neo4j" not in SKIP and "FAIL" in r_neo4j:
        sys.exit(1)
    if "server" not in SKIP and "FAIL" in r_server:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
