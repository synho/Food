#!/usr/bin/env bash
# Start the full stack step by step (Neo4j → Server → Web). Run from repo root.
# Usage: ./scripts/start_local.sh [--only=N]   or   make start   or   make start-step2
set -e
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"
RUN_DIR="${REPO_ROOT}/.run"
mkdir -p "$RUN_DIR"
SERVER_PID="$RUN_DIR/server.pid"
WEB_PID="$RUN_DIR/web.pid"

# Optional: run only one step (e.g. --only=2)
ONLY_STEP=""
for arg in "$@"; do
  if [[ "$arg" =~ ^--only=([1-4])$ ]]; then
    ONLY_STEP="${BASH_REMATCH[1]}"
    break
  fi
done

# Default ports: 8001 matches web/.env.local (NEXT_PUBLIC_API_URL). Override with env if needed.
SERVER_PORT="${SERVER_PORT:-8001}"
WEB_PORT="${WEB_PORT:-3000}"
NEO4J_HTTP="${NEO4J_HTTP_URL:-http://localhost:7474}"

echo "=== Health Navigation — Start (local) ==="
echo ""

run_step() {
  local n="$1"
  if [ -n "$ONLY_STEP" ] && [ "$ONLY_STEP" != "$n" ]; then return 1; fi
  return 0
}

# Return 0 if port is in use
port_in_use() {
  python3 -c "import socket; s=socket.socket(); s.settimeout(1); exit(0 if s.connect_ex(('127.0.0.1', $1))==0 else 1)" 2>/dev/null
}

# --- Step 1: Ports check (always run first when doing a single step) ---
if run_step 1 || [ -n "$ONLY_STEP" ]; then
  echo "[Step 1/4] Checking ports..."
  python3 scripts/ports_check.py || true
  echo ""
  [ "$ONLY_STEP" = "1" ] && exit 0
fi

# --- Step 2: Neo4j ---
if run_step 2; then
echo "[Step 2/4] Starting Neo4j..."
if command -v docker &>/dev/null; then
  (cd kg_pipeline && docker-compose up -d 2>/dev/null) || (docker compose up -d neo4j 2>/dev/null) || true
fi
if ! curl -sf "${NEO4J_HTTP}" >/dev/null 2>&1; then
  if brew services list 2>/dev/null | grep -q neo4j; then
    brew services start neo4j 2>/dev/null || true
  else
    echo "  Neo4j not detected. Start it manually: brew services start neo4j   or   make neo4j-console (in another terminal)"
  fi
  echo "  Waiting for Neo4j (up to 45s)..."
  for i in $(seq 1 45); do
    if curl -sf "${NEO4J_HTTP}" >/dev/null 2>&1; then break; fi
    sleep 1
  done
  if ! curl -sf "${NEO4J_HTTP}" >/dev/null 2>&1; then
    echo "  WARNING: Neo4j not responding at ${NEO4J_HTTP}. Start with: brew services start neo4j   or   make neo4j-console"
  else
    echo "  Neo4j OK."
  fi
else
  echo "  Neo4j already running."
fi
echo ""
fi

# --- Step 3: Server ---
if run_step 3; then
echo "[Step 3/4] Starting API server (port $SERVER_PORT)..."
if [ -f "$SERVER_PID" ]; then
  OLD_PID=$(cat "$SERVER_PID")
  if kill -0 "$OLD_PID" 2>/dev/null; then
    echo "  Server already running (PID $OLD_PID)."
  else
    rm -f "$SERVER_PID"
  fi
fi
if [ ! -f "$SERVER_PID" ] || ! kill -0 "$(cat "$SERVER_PID")" 2>/dev/null; then
  if port_in_use "$SERVER_PORT"; then
    echo "  Port $SERVER_PORT already in use. Skip start (or stop other process and retry)."
  else
    UVC=""
    if [ -x "$REPO_ROOT/.venv/bin/uvicorn" ]; then UVC="$REPO_ROOT/.venv/bin/uvicorn server.main:app"; elif command -v uvicorn &>/dev/null; then UVC="uvicorn server.main:app"; else UVC="python3 -m uvicorn server.main:app"; fi
    (cd "$REPO_ROOT" && $UVC --host 0.0.0.0 --port "$SERVER_PORT" </dev/null >> "$RUN_DIR/server.log" 2>&1 & echo $! > "$SERVER_PID")
    echo "  Server started (PID $(cat "$SERVER_PID")). Log: .run/server.log"
    sleep 2
    if ! curl -sf "http://127.0.0.1:${SERVER_PORT}/health" >/dev/null 2>&1; then
      echo "  WARNING: Server may still be starting. Check: .run/server.log"
    fi
  fi
fi
echo ""
fi

# --- Step 4: Web ---
if run_step 4; then
echo "[Step 4/4] Starting web (port $WEB_PORT)..."
if [ -f "$WEB_PID" ]; then
  OLD_PID=$(cat "$WEB_PID")
  if kill -0 "$OLD_PID" 2>/dev/null; then
    echo "  Web already running (PID $OLD_PID)."
  else
    rm -f "$WEB_PID"
  fi
fi
if [ ! -f "$WEB_PID" ] || ! kill -0 "$(cat "$WEB_PID")" 2>/dev/null; then
  if port_in_use "$WEB_PORT"; then
    echo "  Port $WEB_PORT already in use. Skip start (or stop other process and retry)."
  else
    (cd web && PORT="$WEB_PORT" npm run dev </dev/null >> "$RUN_DIR/web.log" 2>&1 & echo $! > "$WEB_PID")
    echo "  Web started (PID $(cat "$WEB_PID")). Log: .run/web.log"
    sleep 2
  fi
fi
echo ""
fi

echo "=== Done. ==="
echo "  Neo4j:  ${NEO4J_HTTP}"
echo "  API:    http://127.0.0.1:${SERVER_PORT}"
echo "  Web:    http://localhost:${WEB_PORT}"
echo "  Check:  make check   (or SERVER_URL=http://127.0.0.1:${SERVER_PORT} WEB_URL=http://localhost:${WEB_PORT} make check)"
echo "  Stop:   make stop"
