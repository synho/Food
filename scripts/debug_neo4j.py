#!/usr/bin/env python3
"""
Neo4j 연결 디버그. 레포 루트에서: make debug-neo4j (또는 .venv/bin/python3 scripts/debug_neo4j.py)

- 포트 7687 개방 여부 확인 후, NEO4J_URI/USER/PASSWORD로 연결 테스트.
- Connection refused 시 최대 5회, 3초 간격 재시도.
- foodnot4self / neo4j 두 계정 시도: scripts/debug_neo4j.py --try-both
"""
import os
import socket
import sys
from pathlib import Path
from typing import Tuple

# Load env from repo root and server/
REPO_ROOT = Path(__file__).resolve().parent.parent
for env_file in [REPO_ROOT / ".env", REPO_ROOT / "server" / ".env"]:
    if env_file.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_file)
        except ImportError:
            pass
        break

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "foodnot4self")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "foodnot4self")


def port_open(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def try_connect(uri: str, user: str, password: str) -> Tuple[bool, str]:
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            r = session.run("RETURN 1 AS n")
            r.single()
        driver.close()
        return True, "OK"
    except Exception as e:
        return False, str(e)


def connect_with_retry(uri: str, user: str, password: str, max_attempts: int = 5, delay_sec: float = 3.0) -> Tuple[bool, str]:
    """Try to connect with backoff; helps when Neo4j is still starting (e.g. after brew services start)."""
    import time
    last_msg = ""
    for attempt in range(1, max_attempts + 1):
        ok, msg = try_connect(uri, user, password)
        if ok:
            return True, "OK"
        last_msg = msg
        if attempt < max_attempts and ("Connection refused" in msg or "Failed to establish" in msg):
            time.sleep(delay_sec)
    return False, last_msg


def main():
    try_both = "--try-both" in sys.argv
    # Parse host/port from URI for port check
    host = "localhost"
    port = 7687
    if "://" in NEO4J_URI:
        rest = NEO4J_URI.split("://", 1)[1].split("/")[0]
        if ":" in rest:
            host, p = rest.rsplit(":", 1)
            try:
                port = int(p)
            except ValueError:
                pass
        else:
            host = rest

    print("Neo4j connection debug")
    print("-" * 50)
    print(f"  NEO4J_URI      = {NEO4J_URI}")
    print(f"  NEO4J_USER     = {NEO4J_USER}")
    print(f"  NEO4J_PASSWORD = {'(set)' if NEO4J_PASSWORD else '(empty)'}")
    print()

    if not port_open(host, port):
        print("  Port check: FAIL — nothing listening on {}:{}".format(host, port))
        print()
        print("  Neo4j is not running. Start it first:")
        print("    ./run.sh start          # full stack (Neo4j + API + Web)")
        print("    ./run.sh start-neo4j    # Neo4j only")
        print("    brew services start neo4j   # Homebrew")
        print("    make neo4j-console      # foreground (Homebrew)")
        print("-" * 50)
        return 1

    print("  Port check: OK — {}:{} is open".format(host, port))
    print()

    ok, msg = connect_with_retry(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    if ok:
        print("  Result: OK — connection successful.")
        print("-" * 50)
        return 0

    is_auth = "auth" in msg.lower() or "unauthorized" in msg.lower() or "credentials" in msg.lower()
    print("  Result: FAIL — {}".format(msg))
    if is_auth:
        print()
        print("  Likely cause: authentication. This project uses foodnot4self / foodnot4self.")
    if try_both:
        print()
        print("  Trying neo4j/neo4j (default Neo4j image)...")
        ok2, msg2 = connect_with_retry(NEO4J_URI, "neo4j", "neo4j")
        if ok2:
            print("  Result: OK — neo4j/neo4j works. DB was initialized with default credentials.")
            print("  Fix: Create user foodnot4self in Neo4j Browser (http://localhost:7474), or")
            print("       Docker: docker compose down -v && docker compose up -d neo4j")
        else:
            print("  Result: FAIL — {}".format(msg2))
    elif is_auth:
        print("  Run with --try-both to test neo4j/neo4j:  python3 scripts/debug_neo4j.py --try-both")
    print("-" * 50)
    return 1

if __name__ == "__main__":
    sys.exit(main())
