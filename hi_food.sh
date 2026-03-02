#!/bin/bash
# ╔══════════════════════════════════════════════════════════╗
# ║  hi_food.sh — Full startup for Health Navigation Platform ║
# ║  Run this when you come back: bash hi_food.sh             ║
# ╚══════════════════════════════════════════════════════════╝
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║          Food — Health Navigation Platform               ║"
echo "║          Starting all services…                          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# ── Step 1: Start Neo4j + Server + Web ────────────────────────────────────
echo "[1/4] Starting Neo4j, API server, and web..."
make start
echo ""

# ── Step 2: Check everything is healthy ───────────────────────────────────
echo "[2/4] Checking service health..."
sleep 5
make check
echo ""

# ── Step 3: Run pipeline to catch up on new papers ────────────────────────
echo "[3/4] Running pipeline to fetch new papers..."
cd "$ROOT/kg_pipeline"
source venv/bin/activate
python run_pipeline.py
deactivate
cd "$ROOT"
echo ""

# ── Step 4: Start continuous watch_kg daemon ──────────────────────────────
echo "[4/4] Starting continuous KG watcher (every 10 min)..."
cd "$ROOT/kg_pipeline"
source venv/bin/activate
mkdir -p logs
PYTHONUNBUFFERED=1 python -u watch_kg.py > logs/watch_kg.log 2>&1 &
WATCH_PID=$!
deactivate
cd "$ROOT"
echo "  watch_kg started (PID=$WATCH_PID) — logs: kg_pipeline/logs/watch_kg.log"
echo ""

# ── Summary ───────────────────────────────────────────────────────────────
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  All systems GO.                                         ║"
echo "║                                                          ║"
echo "║  Web:       http://localhost:3000                        ║"
echo "║  API:       http://localhost:8000/docs                   ║"
echo "║  KG Dash:   http://localhost:3000/kg                     ║"
echo "║  KG Graph:  http://localhost:3000/kg/explore             ║"
echo "║  Neo4j:     http://localhost:7474                        ║"
echo "║                                                          ║"
echo "║  watch_kg running — tail -f kg_pipeline/logs/watch_kg.log ║"
echo "║  Stop all:  make stop && kill $WATCH_PID                ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
make kg-status
