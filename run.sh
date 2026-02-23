#!/usr/bin/env bash
# Health Navigation — one script for start, stop, check, pipeline, etc.
# Usage: ./run.sh <command>   (run from repo root, or any dir — script cd's to repo root)
#
# Commands:
#   start         Start full stack (Neo4j → Server → Web). Background.
#   stop          Stop full stack (Web → Server → Neo4j).
#   check         Show status of Neo4j, Pipeline, Server, Web.
#   status        Same as check.
#   ports         Show which ports are in use (7474, 7687, 8000, 3000, ...).
#   pipeline      Run pipeline once (Fetch → Extract → Ingest).
#   validate      Validate pipeline output and Neo4j.
#   kg-status     KG detail (triples, nodes, relationships).
#   debug         Neo4j connection debug (port + auth; pass --try-both to try neo4j/neo4j).
#   test          Run test: stop → start(8010/3010) → check → stop.
#   help          Show this help.
#
# Step-by-step (optional):
#   start-neo4j   Start only Neo4j.
#   start-server  Start only API server.
#   start-web     Start only web app.
#   stop-web      Stop only web.
#   stop-server   Stop only server.
#   stop-neo4j    Stop only Neo4j.
#
# Examples:
#   ./run.sh start && ./run.sh check
#   ./run.sh stop
#   ./run.sh pipeline
#   ./run.sh help
set -e
REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_ROOT"

CMD="${1:-help}"

case "$CMD" in
  start)
    chmod +x scripts/start_local.sh scripts/stop_local.sh 2>/dev/null || true
    ./scripts/start_local.sh
    ;;
  stop)
    chmod +x scripts/stop_local.sh 2>/dev/null || true
    ./scripts/stop_local.sh
    ;;
  check|status)
    python3 scripts/monitor.py
    ;;
  ports)
    python3 scripts/ports_check.py
    ;;
  pipeline)
    (cd kg_pipeline && (venv/bin/python run_pipeline.py 2>/dev/null || ( . venv/bin/activate && python run_pipeline.py )))
    echo "Pipeline done. Check: ./run.sh check"
    ;;
  validate)
    (cd kg_pipeline && (venv/bin/python src/validate_run.py --neo4j 2>/dev/null || ( . venv/bin/activate && python src/validate_run.py --neo4j )))
    ;;
  kg-status)
    if [ -f .venv/bin/python3 ]; then .venv/bin/python3 scripts/kg_status.py; else python3 scripts/kg_status.py --no-neo4j; fi
    ;;
  debug)
    if [ -f .venv/bin/python3 ]; then .venv/bin/python3 scripts/debug_neo4j.py "${@:2}"; else python3 scripts/debug_neo4j.py "${@:2}"; fi
    ;;
  test)
    make test-start-stop
    ;;
  start-neo4j)
    chmod +x scripts/start_local.sh 2>/dev/null || true
    ./scripts/start_local.sh --only=2
    ;;
  start-server)
    chmod +x scripts/start_local.sh 2>/dev/null || true
    ./scripts/start_local.sh --only=3
    ;;
  start-web)
    chmod +x scripts/start_local.sh 2>/dev/null || true
    ./scripts/start_local.sh --only=4
    ;;
  stop-web)
    chmod +x scripts/stop_local.sh 2>/dev/null || true
    ./scripts/stop_local.sh --only=1
    ;;
  stop-server)
    chmod +x scripts/stop_local.sh 2>/dev/null || true
    ./scripts/stop_local.sh --only=2
    ;;
  stop-neo4j)
    chmod +x scripts/stop_local.sh 2>/dev/null || true
    ./scripts/stop_local.sh --only=3
    ;;
  help|--help|-h)
    echo "Health Navigation — run.sh"
    echo ""
    echo "  ./run.sh <command>"
    echo ""
    echo "  start         Start full stack (Neo4j → Server → Web)"
    echo "  stop          Stop full stack"
    echo "  check         Status (Neo4j, Pipeline, Server, Web)"
    echo "  status        Same as check"
    echo "  ports         Show port usage"
    echo "  pipeline      Run pipeline once"
    echo "  validate      Validate pipeline + Neo4j"
    echo "  kg-status     KG detail"
    echo "  debug         Neo4j connection debug (./run.sh debug --try-both for both credentials)"
    echo "  test          Test: stop → start → check → stop"
    echo "  help          This help"
    echo ""
    echo "  start-neo4j   start-server   start-web   (only one component)"
    echo "  stop-web      stop-server   stop-neo4j"
    echo ""
    ;;
  *)
    echo "Unknown command: $CMD" >&2
    echo "Run: ./run.sh help" >&2
    exit 1
    ;;
esac
