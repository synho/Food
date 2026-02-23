#!/bin/bash
# Script to execute Phase 4 KG expansion
# This script should be run from the Food project root directory

set -e  # Exit on any error

echo "==== Running Phase 4 KG Expansion ===="

# Step 1: Validate Phase 1 expansion run
echo "Step 1: Validating previous KG run..."
cd kg_pipeline
source .venv/bin/activate || { echo "Failed to activate virtual environment. Please create it first."; exit 1; }
python src/validate_run.py --neo4j

# Step 2: Run Phase 4 expansion
echo "Step 2: Running Phase 4 expansion..."
RUN_ID=phase4 python run_pipeline.py --config config_phase4.yaml

# Step 3: Verify expansion results
echo "Step 3: Verifying expansion results..."
python src/audit_graph.py --n 10
python src/validate_run.py --neo4j

echo "==== Phase 4 KG Expansion Completed ===="
echo "To check KG status, run: make kg-status"