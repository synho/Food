# Phase 4 KG Expansion Guide

This document provides instructions for executing Phase 4 Knowledge Graph expansion, which broadens the KG with additional medical literature (90 days, 50-100 papers).

## Prerequisites

1. Neo4j database must be running
2. Python virtual environment with requirements installed
3. GEMINI_API_KEY must be set in `.env` file
4. Working Docker installation

## Configuration

Phase 4 expansion uses `config_phase4.yaml`, which includes:
- 90-day lookback period (vs. 30 days in earlier phases)
- 50-100 papers (vs. 10-20 in earlier phases)
- Additional aging-related keywords
- Multi-hop chain extraction for Food→Nutrient→Disease pathways

## Execution Steps

### 1. Validate Previous KG Run

Before starting expansion, validate the existing KG to ensure it's in a good state:

```bash
cd kg_pipeline
source .venv/bin/activate  # Use appropriate venv activation
python src/validate_run.py --neo4j
```

This checks that the KG has valid nodes and relationships, consistent ontology, and all required properties.

### 2. Run Phase 4 Expansion

Execute the pipeline with the Phase 4 configuration:

```bash
RUN_ID=phase4 python run_pipeline.py --config config_phase4.yaml
```

This will:
- Fetch papers from PMC with 90-day lookback period
- Extract triples with enhanced multi-hop chain extraction
- Ingest to Neo4j with zero-error enforcement

The process may take 2-3 hours depending on API rate limits.

### 3. Verify Expansion Results

After expansion completes, verify the results:

```bash
python src/audit_graph.py --n 10
python src/validate_run.py --neo4j
```

Additionally, check the KG status:

```bash
cd ..  # Return to project root
make kg-status
```

## Monitoring

During execution, monitor:

- `data/manifests/fetch_manifest_phase4.json` - Papers fetched
- `data/manifests/extract_manifest_phase4.json` - Triples extracted
- `data/manifests/ingest_manifest_phase4.json` - Neo4j ingestion stats

## Troubleshooting

- If the API rate limit is reached, the pipeline will automatically pause and retry.
- If extraction fails for some papers, they will be logged in `data/errors/`.
- If validation fails, check the error logs and fix any issues before proceeding.

## Automated Execution

For convenience, use the provided script:

```bash
./scripts/run_phase4_expansion.sh
```

This script automates all three steps of the expansion process.