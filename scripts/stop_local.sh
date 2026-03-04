#!/usr/bin/env bash
# Stop the full stack in reverse order (Web → Server → Neo4j). Run from repo root.
# Usage: ./scripts/stop_local.sh [--only=N]   or   make stop   or   make stop-step1
# --only=1: web only, --only=2: server only, --only=3: neo4j only
set -e
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"
RUN_DIR="${REPO_ROOT}/.run"
SERVER_PID="$RUN_DIR/server.pid"
WEB_PID="$RUN_DIR/web.pid"

ONLY_STEP=""
for arg in "$@"; do
  if [[ "$arg" =~ ^--only=([1-3])$ ]]; then
    ONLY_STEP="${BASH_REMATCH[1]}"
    break
  fi
done

run_stop() { [ -z "$ONLY_STEP" ] || [ "$ONLY_STEP" = "$1" ]; }

# Kill a process and its children (uvicorn workers, node child processes)
stop_pid() {
  local PID="$1" NAME="$2"
  if kill -0 "$PID" 2>/dev/null; then
    pkill -P "$PID" 2>/dev/null || true
    kill -TERM "$PID" 2>/dev/null || true
    for i in $(seq 1 10); do
      kill -0 "$PID" 2>/dev/null || break
      sleep 0.5
    done
    kill -0 "$PID" 2>/dev/null && kill -KILL "$PID" 2>/dev/null || true
    echo "  $NAME stopped (PID $PID)."
  else
    echo "  $NAME not running (stale PID $PID)."
  fi
}

echo "=== Health Navigation — Stop (local) ==="
echo ""

# --- Step 0: Stop pipeline jobs ---
if [ -z "$ONLY_STEP" ]; then
echo "[Step 0] Stopping pipeline jobs..."
for name in expansion overnight watch_kg; do
  pid_file="$REPO_ROOT/kg_pipeline/.run/${name}.pid"
  if [ -f "$pid_file" ]; then
    PID=$(cat "$pid_file")
    if kill -0 "$PID" 2>/dev/null; then
      kill -TERM "$PID" 2>/dev/null && echo "  Stopped $name (PID $PID)."
      sleep 2
      kill -0 "$PID" 2>/dev/null && kill -KILL "$PID" 2>/dev/null || true
    fi
    rm -f "$pid_file"
  fi
done
pkill -f "watch_kg.py" 2>/dev/null || true
echo ""
fi

# --- Step 1: Stop Web ---
if run_stop 1; then
echo "[Step 1/3] Stopping web..."
if [ -f "$WEB_PID" ]; then
  PID=$(cat "$WEB_PID")
  stop_pid "$PID" "Web"
  rm -f "$WEB_PID"
else
  echo "  No web PID file (.run/web.pid)."
fi
echo ""
fi

# --- Step 2: Stop Server ---
if run_stop 2; then
echo "[Step 2/3] Stopping API server..."
if [ -f "$SERVER_PID" ]; then
  PID=$(cat "$SERVER_PID")
  stop_pid "$PID" "Server"
  rm -f "$SERVER_PID"
else
  echo "  No server PID file (.run/server.pid)."
fi
echo ""
fi

# --- Step 3: Stop Neo4j ---
if run_stop 3; then
echo "[Step 3/3] Stopping Neo4j..."
# Stop Docker Neo4j if running
if command -v docker &>/dev/null; then
  if docker ps --format '{{.Names}}' 2>/dev/null | grep -qE "neo4j|kg_pipeline"; then
    echo "  Stopping Docker Neo4j..."
    (cd "$REPO_ROOT/kg_pipeline" && docker compose down 2>/dev/null) || true
  fi
fi
# Stop Homebrew Neo4j
if brew services list 2>/dev/null | grep -q "neo4j.*started"; then
  brew services stop neo4j 2>/dev/null && echo "  Neo4j stopped." || echo "  Neo4j stop returned an error (may need sudo)."
else
  echo "  Neo4j not running as brew service (or brew not available)."
fi
echo ""
fi

echo "=== Done. ==="
echo "  To start again: make start"
