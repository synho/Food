#!/usr/bin/env python3
"""
사용 중인 포트 확인. 레포 루트에서: python3 scripts/ports_check.py
Health Navigation 관련 포트: 7474(Neo4j HTTP), 7687(Neo4j Bolt), 8000(Server), 3000/3001(Web)
"""
import socket
import sys

PORTS = [
    (7474, "Neo4j HTTP"),
    (7687, "Neo4j Bolt"),
    (8000, "Server (기본/다른앱)"),
    (8001, "Server (Health Nav 대체)"),
    (3000, "Web (기본)"),
    (3001, "Web (Docker/대체)"),
]


def port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            s.connect((host, port))
        return True
    except (OSError, socket.error):
        return False


def main():
    print("Health Navigation — 포트 사용 여부 (127.0.0.1)")
    print("-" * 50)
    in_use = []
    for port, label in PORTS:
        if port_in_use(port):
            status = "\033[93m사용중\033[0m"
            in_use.append((port, label))
        else:
            status = "\033[92m비어있음\033[0m"
        print(f"  {port:5}  {label:20}  {status}")
    print("-" * 50)
    if in_use:
        print("충돌 회피: 해당 서비스를 쓰는 경우 아래처럼 포트를 바꿀 수 있음.")
        print("  Server 다른 포트: PORT=8001 uvicorn server.main:app --reload --port 8001")
        print("  Web 다른 포트:   cd web && npm run dev -- -p 3001")
        print("  모니터링 시:     SERVER_URL=http://127.0.0.1:8001 WEB_URL=http://127.0.0.1:3001 make check")
    sys.exit(0)


if __name__ == "__main__":
    main()
