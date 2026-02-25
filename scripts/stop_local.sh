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
    # Kill children first to prevent reparenting to PID 1
    pkill -P "$PID" 2>/dev/null || true
    kill "$PID" 2>/dev/null || true
    echo "  $NAME stopped (PID $PID)."
  else
    echo "  $NAME not running (stale PID $PID)."
  fi
}

echo "=== Health Navigation — Stop (local) ==="
echo ""

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

# --- Step 3: Stop Neo4j (Homebrew only; Docker left running) ---
if run_stop 3; then
echo "[Step 3/3] Stopping Neo4j (Homebrew service)..."
if brew services list 2>/dev/null | grep -q "neo4j.*started"; then
  brew services stop neo4j 2>/dev/null && echo "  Neo4j stopped." || echo "  Neo4j stop returned an error (may need sudo)."
else
  echo "  Neo4j not running as brew service (or brew not available)."
  echo "  If you started Neo4j with 'make neo4j-console', stop it with Ctrl+C in that terminal."
fi
echo ""
fi

echo "=== Done. ==="
echo "  To start again: make start"
