#!/usr/bin/env bash
# =============================================================================
# run_expansion.sh — Phase 3 expansion + post-cleanup
#
# Runs watch_kg.py --interval 10 for up to 4.5 hours, then cleans up.
#
# Usage:
#   cd kg_pipeline
#   nohup bash run_expansion.sh > logs/expansion_main.log 2>&1 & disown
# =============================================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_PYTHON="$SCRIPT_DIR/venv/bin/python"
LOGS_DIR="$SCRIPT_DIR/logs"
DATA_DIR="$(dirname "$SCRIPT_DIR")/data"
RUN_DIR="$SCRIPT_DIR/.run"

mkdir -p "$LOGS_DIR" "$RUN_DIR" "$DATA_DIR"

TS=$(date +%Y%m%d_%H%M%S)
LOG="$LOGS_DIR/expansion_${TS}.log"
EXPANSION_LOG="$LOGS_DIR/expansion_cycles_${TS}.log"
EXPANSION_TIMEOUT=16200   # 4h 30m

echo $$ > "$RUN_DIR/expansion.pid"

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    echo "$msg"
    echo "$msg" >> "$LOG"
}

kg_counts() {
    "$VENV_PYTHON" -c "
from neo4j import GraphDatabase
d = GraphDatabase.driver('bolt://localhost:7687', auth=('foodnot4self','foodnot4self'))
with d.session() as s:
    nodes = s.run('MATCH (n) RETURN count(n) AS c').single()['c']
    rels  = s.run('MATCH ()-[r]->() RETURN count(r) AS c').single()['c']
    print(f'Nodes: {nodes}  |  Relationships: {rels}')
d.close()
" 2>/dev/null || echo "(could not query Neo4j)"
}

# ═══════════════════════════════════════════════════════════════════════════════
log "═══ PHASE 3: KG Expansion ═══"
log "PID: $$"
log "Pre-expansion KG counts:"
kg_counts | tee -a "$LOG"

log "Starting watch_kg.py --interval 10 (timeout: ${EXPANSION_TIMEOUT}s / ~4.5h)"

"$VENV_PYTHON" watch_kg.py \
    --interval 10 \
    --log-file "$EXPANSION_LOG" \
    >> "$LOG" 2>&1 &
WATCH_PID=$!
log "watch_kg.py PID: $WATCH_PID"

EXPANSION_START=$(date +%s)

# Poll every 30s; kill after timeout
while kill -0 "$WATCH_PID" 2>/dev/null; do
    ELAPSED=$(( $(date +%s) - EXPANSION_START ))
    if [ "$ELAPSED" -ge "$EXPANSION_TIMEOUT" ]; then
        log "Timeout reached (${EXPANSION_TIMEOUT}s) — sending SIGTERM to watch_kg"
        kill -TERM "$WATCH_PID" 2>/dev/null
        sleep 10
        kill -0 "$WATCH_PID" 2>/dev/null && kill -KILL "$WATCH_PID" 2>/dev/null
        break
    fi
    sleep 30
done
wait "$WATCH_PID" 2>/dev/null || true

ELAPSED=$(( $(date +%s) - EXPANSION_START ))
log "═══ Expansion finished (${ELAPSED}s) ═══"
log "Post-expansion KG counts:"
kg_counts | tee -a "$LOG"

# ═══════════════════════════════════════════════════════════════════════════════
log "═══ Post-expansion cleanup ═══"

log "Consolidating master_graph.json..."
"$VENV_PYTHON" src/consolidate_graph.py >> "$LOG" 2>&1 && log "  done" || log "  FAILED"

log "Entity resolution (round 2)..."
"$VENV_PYTHON" src/entity_resolver.py >> "$LOG" 2>&1 && log "  done" || log "  FAILED"

log "Label cleanup..."
"$VENV_PYTHON" src/entity_resolver.py --cleanup-labels >> "$LOG" 2>&1 && log "  done" || log "  FAILED"

log "Orphan cleanup..."
"$VENV_PYTHON" src/entity_resolver.py --cleanup-orphans >> "$LOG" 2>&1 && log "  done" || log "  FAILED"

log "Contradiction detection..."
"$VENV_PYTHON" src/detect_contradictions.py --output "$DATA_DIR/contradictions_post_expansion_${TS}.json" >> "$LOG" 2>&1 && log "  done" || log "  FAILED"

log "Final ingest..."
"$VENV_PYTHON" src/ingest_to_neo4j.py >> "$LOG" 2>&1 && log "  done" || log "  FAILED"

log "Final audit..."
"$VENV_PYTHON" src/audit_kg_quality.py --output "$DATA_DIR/audit_POST_EXPANSION_${TS}.json" >> "$LOG" 2>&1 && log "  done" || log "  FAILED"

log "Validation..."
"$VENV_PYTHON" src/validate_run.py --neo4j >> "$LOG" 2>&1 && log "  done" || log "  FAILED"

log "Final KG counts:"
kg_counts | tee -a "$LOG"

TOTAL_ELAPSED=$(( $(date +%s) - EXPANSION_START ))
HOURS=$((TOTAL_ELAPSED / 3600))
MINS=$(( (TOTAL_ELAPSED % 3600) / 60 ))
log "═══ ALL DONE — ${HOURS}h ${MINS}m total ═══"

rm -f "$RUN_DIR/expansion.pid"
