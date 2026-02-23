#!/usr/bin/env bash
# setup_cron.sh — Install weekly pipeline cron job (Sundays at 2am)
# Usage: bash scripts/setup_cron.sh
# Remove: bash scripts/setup_cron.sh --remove

set -euo pipefail

KG_PIPELINE_DIR="$(cd "$(dirname "$0")/.." && pwd)/kg_pipeline"
LOG_FILE="/tmp/food_kg_pipeline.log"
CRON_TAG="food_kg_pipeline_weekly"

CRON_CMD="0 2 * * 0 cd \"$KG_PIPELINE_DIR\" && source venv/bin/activate && RUN_ID=\$(date +\\%Y\\%m\\%d_weekly) python run_pipeline.py --config config.yaml >> \"$LOG_FILE\" 2>&1 # $CRON_TAG"

if [[ "${1:-}" == "--remove" ]]; then
    echo "Removing food_kg_pipeline_weekly cron job..."
    crontab -l 2>/dev/null | grep -v "$CRON_TAG" | crontab -
    echo "Removed. Current crontab:"
    crontab -l 2>/dev/null || echo "(empty)"
    exit 0
fi

# Check venv exists
if [[ ! -f "$KG_PIPELINE_DIR/venv/bin/activate" ]]; then
    echo "ERROR: venv not found at $KG_PIPELINE_DIR/venv"
    echo "Run: cd kg_pipeline && python -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Check config.yaml exists
if [[ ! -f "$KG_PIPELINE_DIR/config.yaml" ]]; then
    echo "ERROR: config.yaml not found at $KG_PIPELINE_DIR/config.yaml"
    exit 1
fi

# Remove any existing entry for this job, then add the new one
(crontab -l 2>/dev/null | grep -v "$CRON_TAG"; echo "$CRON_CMD") | crontab -

echo "Cron job installed. Runs every Sunday at 2:00am."
echo "Log file: $LOG_FILE"
echo ""
echo "Current crontab:"
crontab -l
echo ""
echo "To remove: bash scripts/setup_cron.sh --remove"
