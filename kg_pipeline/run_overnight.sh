#!/usr/bin/env bash
# =============================================================================
# run_overnight.sh — 8-hour automated KG quality + expansion run
#
# Phases:
#   0. Startup         (~15 min)  — Neo4j up, baseline audit
#   1. Quality cleanup  (~1h 15m) — Renormalize → reingest → entity dedup → label/orphan cleanup
#   2. Extract backlog  (~45 min) — Extract ~357 unextracted papers → consolidate → ingest
#   3. Expansion        (~4h 30m) — Gap-targeted fetch/extract/ingest cycles (10-min intervals)
#   4. Post-expansion   (~45 min) — Entity dedup round 2, contradictions, final ingest
#   5. Final audit      (~30 min) — Quality audit, validation, summary report
#
# Usage:
#   cd kg_pipeline
#   nohup bash run_overnight.sh > logs/overnight_main.log 2>&1 & disown
#
# To stop gracefully:
#   kill -TERM $(cat .run/overnight.pid)    # watch_kg.py handles SIGTERM
# =============================================================================
set -uo pipefail

# ── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_PYTHON="$SCRIPT_DIR/venv/bin/python"
LOGS_DIR="$SCRIPT_DIR/logs"
DATA_DIR="$(dirname "$SCRIPT_DIR")/data"
RUN_DIR="$SCRIPT_DIR/.run"

mkdir -p "$LOGS_DIR" "$RUN_DIR" "$DATA_DIR"

TS=$(date +%Y%m%d_%H%M%S)
LOG="$LOGS_DIR/overnight_${TS}.log"
SUMMARY="$LOGS_DIR/overnight_summary_${TS}.txt"
PID_FILE="$RUN_DIR/overnight.pid"

AUDIT_BEFORE="$DATA_DIR/audit_BEFORE_${TS}.json"
AUDIT_AFTER_P1="$DATA_DIR/audit_AFTER_PHASE1_${TS}.json"
AUDIT_FINAL="$DATA_DIR/audit_FINAL_${TS}.json"
CONTRADICTIONS="$DATA_DIR/contradictions_${TS}.json"

EXPANSION_LOG="$LOGS_DIR/overnight_expansion_${TS}.log"
EXPANSION_TIMEOUT=16200   # 4h 30m in seconds

# Write PID for external stop
echo $$ > "$PID_FILE"

# ── Counters ─────────────────────────────────────────────────────────────────
STEP_PASS=0
STEP_FAIL=0
STEP_SKIP=0
START_EPOCH=$(date +%s)

# ── Helper functions ─────────────────────────────────────────────────────────

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    echo "$msg"
    echo "$msg" >> "$LOG"
}

separator() {
    local line="════════════════════════════════════════════════════════════════"
    echo "$line"
    echo "$line" >> "$LOG"
}

run_step() {
    # Usage: run_step "description" command [args...]
    local desc="$1"; shift
    log "▶ START: $desc"
    local step_start
    step_start=$(date +%s)

    if "$@" >> "$LOG" 2>&1; then
        local elapsed=$(( $(date +%s) - step_start ))
        log "✓ DONE:  $desc  (${elapsed}s)"
        STEP_PASS=$((STEP_PASS + 1))
        return 0
    else
        local rc=$?
        local elapsed=$(( $(date +%s) - step_start ))
        log "✗ FAIL:  $desc  (exit $rc, ${elapsed}s)"
        STEP_FAIL=$((STEP_FAIL + 1))
        return $rc
    fi
}

wait_for_neo4j() {
    log "Waiting for Neo4j to accept connections..."
    local max_wait=120
    local elapsed=0
    while ! "$VENV_PYTHON" -c "
from neo4j import GraphDatabase
d = GraphDatabase.driver('bolt://localhost:7687', auth=('foodnot4self','foodnot4self'))
d.verify_connectivity()
d.close()
" 2>/dev/null; do
        sleep 5
        elapsed=$((elapsed + 5))
        if [ "$elapsed" -ge "$max_wait" ]; then
            log "✗ Neo4j did not start within ${max_wait}s"
            return 1
        fi
    done
    log "✓ Neo4j is ready (waited ${elapsed}s)"
}

kg_counts() {
    # Print node and relationship counts
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

# ── Pre-flight checks ────────────────────────────────────────────────────────

if [ ! -x "$VENV_PYTHON" ]; then
    echo "ERROR: venv not found at $VENV_PYTHON"
    echo "Run: python -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

separator
log "OVERNIGHT KG RUN — started $TS"
log "Log file:    $LOG"
log "Summary:     $SUMMARY"
log "PID:         $$"
separator

# =============================================================================
# PHASE 0: Startup — Neo4j + baseline audit
# =============================================================================
separator
log "PHASE 0: Startup"
separator

run_step "Start Neo4j (docker compose)" \
    docker compose up -d

wait_for_neo4j || { log "ABORT: Neo4j not available"; exit 1; }

log "Baseline KG counts:"
kg_counts | tee -a "$LOG"

run_step "Baseline audit" \
    "$VENV_PYTHON" src/audit_kg_quality.py --output "$AUDIT_BEFORE"

run_step "Baseline validation" \
    "$VENV_PYTHON" src/validate_run.py --neo4j

# =============================================================================
# PHASE 1: Quality cleanup — renormalize, reingest, entity dedup, label/orphan fix
# =============================================================================
separator
log "PHASE 1: Quality Cleanup"
separator

# Safety check — dry run first
run_step "Renormalize (dry-run safety check)" \
    "$VENV_PYTHON" src/renormalize_graph.py --dry-run

# Full renormalize + reingest (DETACH DELETE + re-ingest from rewritten files)
run_step "Renormalize + reingest (full rebuild)" \
    "$VENV_PYTHON" src/renormalize_graph.py --reingest

log "Post-reingest KG counts:"
kg_counts | tee -a "$LOG"

# Entity resolution — merge duplicate nodes
run_step "Entity resolution (merge duplicates)" \
    "$VENV_PYTHON" src/entity_resolver.py

# Cleanup non-standard labels
run_step "Cleanup non-standard labels" \
    "$VENV_PYTHON" src/entity_resolver.py --cleanup-labels

# Remove orphan nodes
run_step "Cleanup orphan nodes" \
    "$VENV_PYTHON" src/entity_resolver.py --cleanup-orphans

log "Post-cleanup KG counts:"
kg_counts | tee -a "$LOG"

run_step "Post-cleanup audit" \
    "$VENV_PYTHON" src/audit_kg_quality.py --output "$AUDIT_AFTER_P1"

# =============================================================================
# PHASE 2: Extract backlog — process ~357 unextracted papers
# =============================================================================
separator
log "PHASE 2: Extract Backlog"
separator

run_step "Extract unextracted papers" \
    "$VENV_PYTHON" src/extract_triples.py

run_step "Consolidate graph (rebuild master_graph.json)" \
    "$VENV_PYTHON" src/consolidate_graph.py

run_step "Ingest to Neo4j" \
    "$VENV_PYTHON" src/ingest_to_neo4j.py

log "Post-backlog KG counts:"
kg_counts | tee -a "$LOG"

# =============================================================================
# PHASE 3: Expansion — gap-targeted fetch/extract/ingest for ~4.5 hours
# =============================================================================
separator
log "PHASE 3: Expansion (${EXPANSION_TIMEOUT}s / ~4.5h)"
separator

log "Starting watch_kg.py with --interval 10 (hard timeout: ${EXPANSION_TIMEOUT}s)"

# macOS lacks `timeout`; use background process + sleep + kill instead
log "▶ START: KG expansion (watch_kg.py --interval 10)"
EXPANSION_START=$(date +%s)

"$VENV_PYTHON" watch_kg.py \
    --interval 10 \
    --log-file "$EXPANSION_LOG" \
    >> "$LOG" 2>&1 &
WATCH_PID=$!

# Wait up to EXPANSION_TIMEOUT seconds, checking every 30s
while kill -0 "$WATCH_PID" 2>/dev/null; do
    ELAPSED_EXP=$(( $(date +%s) - EXPANSION_START ))
    if [ "$ELAPSED_EXP" -ge "$EXPANSION_TIMEOUT" ]; then
        log "Expansion timeout reached (${EXPANSION_TIMEOUT}s) — sending SIGTERM"
        kill -TERM "$WATCH_PID" 2>/dev/null
        sleep 5
        kill -0 "$WATCH_PID" 2>/dev/null && kill -KILL "$WATCH_PID" 2>/dev/null
        break
    fi
    sleep 30
done
wait "$WATCH_PID" 2>/dev/null || true

EXPANSION_ELAPSED=$(( $(date +%s) - EXPANSION_START ))
log "✓ DONE:  KG expansion  (${EXPANSION_ELAPSED}s)"
STEP_PASS=$((STEP_PASS + 1))

log "Expansion complete."
log "Post-expansion KG counts:"
kg_counts | tee -a "$LOG"

# =============================================================================
# PHASE 4: Post-expansion cleanup
# =============================================================================
separator
log "PHASE 4: Post-Expansion Cleanup"
separator

run_step "Consolidate graph (post-expansion)" \
    "$VENV_PYTHON" src/consolidate_graph.py

run_step "Entity resolution (round 2)" \
    "$VENV_PYTHON" src/entity_resolver.py

run_step "Cleanup non-standard labels (round 2)" \
    "$VENV_PYTHON" src/entity_resolver.py --cleanup-labels

run_step "Cleanup orphan nodes (round 2)" \
    "$VENV_PYTHON" src/entity_resolver.py --cleanup-orphans

run_step "Detect contradictions" \
    "$VENV_PYTHON" src/detect_contradictions.py --output "$CONTRADICTIONS"

run_step "Final ingest to Neo4j" \
    "$VENV_PYTHON" src/ingest_to_neo4j.py

log "Post-cleanup KG counts:"
kg_counts | tee -a "$LOG"

# =============================================================================
# PHASE 5: Final audit + summary report
# =============================================================================
separator
log "PHASE 5: Final Audit"
separator

run_step "Final audit" \
    "$VENV_PYTHON" src/audit_kg_quality.py --output "$AUDIT_FINAL"

run_step "Final validation" \
    "$VENV_PYTHON" src/validate_run.py --neo4j

# ── Generate summary report ──────────────────────────────────────────────────
log "Generating summary report..."

"$VENV_PYTHON" - "$AUDIT_BEFORE" "$AUDIT_FINAL" "$CONTRADICTIONS" "$SUMMARY" <<'PYEOF'
import json, sys, os
from datetime import datetime

before_path, final_path, contra_path, summary_path = sys.argv[1:5]

def load_latest(path):
    """Load audit JSON; it may be a list (history) — take last entry."""
    if not os.path.exists(path):
        return {}
    data = json.load(open(path))
    if isinstance(data, list):
        return data[-1] if data else {}
    return data

before = load_latest(before_path)
after  = load_latest(final_path)

# Contradiction count
contra_count = 0
if os.path.exists(contra_path):
    cdata = json.load(open(contra_path))
    if isinstance(cdata, list):
        contra_count = len(cdata)
    elif isinstance(cdata, dict):
        contra_count = cdata.get("total_contradictions", cdata.get("count", 0))

metrics = [
    "total_nodes", "total_relationships", "duplicate_groups",
    "orphan_nodes", "nonstandard_node_count", "weak_predicate_pct",
    "empty_journal_pct", "unique_sources",
]

lines = []
lines.append("=" * 66)
lines.append("  OVERNIGHT KG RUN — SUMMARY REPORT")
lines.append(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
lines.append("=" * 66)
lines.append("")
lines.append(f"{'Metric':<35s}  {'Before':>10s}  {'After':>10s}  {'Delta':>10s}")
lines.append("-" * 66)

for m in metrics:
    b = before.get(m, "?")
    a = after.get(m, "?")
    try:
        if isinstance(b, float) or isinstance(a, float):
            delta = f"{float(a) - float(b):+.2f}"
        else:
            delta = f"{int(a) - int(b):+d}"
    except (TypeError, ValueError):
        delta = "?"
    lines.append(f"{m:<35s}  {str(b):>10s}  {str(a):>10s}  {delta:>10s}")

lines.append("-" * 66)
lines.append(f"{'contradiction_count':<35s}  {'—':>10s}  {str(contra_count):>10s}")
lines.append("")
lines.append("Audit files:")
lines.append(f"  Before:         {before_path}")
lines.append(f"  After Phase 1:  {before_path.replace('BEFORE', 'AFTER_PHASE1')}")
lines.append(f"  Final:          {final_path}")
lines.append(f"  Contradictions: {contra_path}")
lines.append("")

report = "\n".join(lines)
print(report)
with open(summary_path, "w") as f:
    f.write(report + "\n")
PYEOF

# ── Final stats ──────────────────────────────────────────────────────────────
ELAPSED=$(( $(date +%s) - START_EPOCH ))
HOURS=$((ELAPSED / 3600))
MINS=$(( (ELAPSED % 3600) / 60 ))

separator
log "OVERNIGHT RUN COMPLETE"
log "Duration:     ${HOURS}h ${MINS}m"
log "Steps passed: $STEP_PASS"
log "Steps failed: $STEP_FAIL"
log "Summary:      $SUMMARY"
log "Full log:     $LOG"
separator

# Cleanup PID file
rm -f "$PID_FILE"

exit 0
