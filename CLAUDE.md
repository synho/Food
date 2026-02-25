# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Before Starting Any Task

Read `.cursor/plans/roadmap.md` to identify the **current phase** and the **next unchecked item**. All work should advance the current phase and stay aligned with it. After any pipeline code change, run regression: `cd kg_pipeline && python src/validate_run.py --neo4j`.

## Overview

Health navigation platform using a knowledge graph built from medical literature. Users get evidence-based food recommendations, health map positioning, and early-signal guidance — all traceable to KG evidence.

## Architecture (DIKW Layers)

Strict separation — do not mix responsibilities across layers:

| Layer | Stage | Key Files | Output |
|-------|-------|-----------|--------|
| **Data** | Fetch | `kg_pipeline/src/fetch_papers.py`, `smart_fetch.py` | `data/raw_papers/`, fetch manifest |
| **Information** | Extract | `kg_pipeline/src/extract_triples.py` | `data/extracted_triples/`, `master_graph.json`, extract manifest |
| **Knowledge** | Ingest | `kg_pipeline/src/ingest_to_neo4j.py` | Neo4j graph, ingest manifest |
| **Wisdom** | API/Server | `server/` | Recommendations with evidence |

Each pipeline agent writes a **manifest** to `data/manifests/` so the next agent can cascade using the same `RUN_ID`.

### KG Pipeline (`kg_pipeline/`)

- **`src/ontology.py`** — Single source of truth for entity types (`ENTITY_TYPES`, `ENTITY_TYPE_ALIASES`), predicates (`ALL_PREDICATES`), and canonical names (`CANONICAL_ENTITY_NAMES`). All normalization flows through `normalize_entity_name()`, `normalize_entity_type()`, `normalize_predicate()`.
- **`src/extract_triples.py`** — Calls Gemini (default: `gemini-2.0-flash-lite`) to extract triples; delegates master file write to `consolidate_graph.py`.
- **`src/consolidate_graph.py`** — Single writer for `master_graph.json`; returns path for downstream steps.
- **`src/ingest_to_neo4j.py`** — MERGEs nodes/relationships by `{source_id}` so each paper gets its own relationship and evidence accumulates. Calls `setup_schema()` at start to create indexes.
- **`src/entity_resolver.py`** — Entity resolution and deduplication.
- **`src/kg_gap_analyzer.py`** — Identifies gaps in KG coverage for targeted fetching.
- **`run_pipeline.py`** — Orchestrator; supports `--steps fetch,extract,ingest`.
- **`config.yaml`** — Controls `fetch.days_back`, `fetch.max_results`, `fetch.journals`, `extract.model`, smart-fetch settings, gap analysis.
- Separate `docker-compose.yml` for Neo4j only (used during pipeline development).

### FastAPI Server (`server/`)

- **`main.py`** — App entry point; CORS via `CORS_ORIGINS` env (default: `localhost:3000`); `TieredAccessMiddleware` sets `request.state.plan` from `X-Plan` header.
- **`neo4j_client.py`** — Singleton Neo4j driver; `close_driver()` called in lifespan shutdown.
- **`db.py`** — SQLite persistence (`data/health_map.db`) for pipeline history, KG stats trends, demand tracking, contradictions.
- **`canonical.py`** — `CANONICAL_ENTITY_NAMES` for the server side; **must be kept in sync with `kg_pipeline/src/ontology.py`**.
- **`pipeline_scheduler.py`** — Adaptive background scheduler that triggers pipeline runs (1–30 min intervals).
- **`context_store.py`** — Encrypted user context save/restore (requires `CONTEXT_ENCRYPTION_KEY`).
- **`models/user_context.py`** — `UserContext` Pydantic model (age, gender, ethnicity, conditions, symptoms, medications, goals, location, way_of_living, culture).
- **`models/responses.py`** — Response models enforcing zero-error (every item requires `evidence[]`).
- **`services/`** — One file per API domain: `recommendations.py`, `position.py`, `safest_path.py`, `early_signals.py`, `general_guidance.py`, `drug_substitution.py`, `suggest.py`, `context_from_text.py`, `health_map_agent.py`, `landmine_detector.py`, `food_chain.py`, `contradiction_detector.py`.

Key API groups:
- `/api/recommendations/foods` (POST), `/api/recommendations/drug-substitution` — food/drug guidance
- `/api/health-map/position`, `/api/health-map/safest-path`, `/api/health-map/landmines`, `/api/health-map/interrogate` — health map
- `/api/guidance/early-signals`, `/api/guidance/general` — guidance
- `/api/kg/stats`, `/api/kg/food-chain`, `/api/kg/demand`, `/api/kg/contradictions` — KG introspection
- `/api/pipeline/status`, `/api/pipeline/trigger`, `/api/pipeline/history`, `/api/pipeline/yield` — pipeline management
- `/api/context/from-text`, `/api/me/context/save`, `/api/me/context/restore` — user context
- `/api/suggest` — autocomplete suggestions

### Web (`web/`)

- Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS.
- Routes: `app/page.tsx` (main), `app/kg/page.tsx` (KG dashboard at `/kg`), `app/map/` (health map).
- `lib/api.ts` — All API client functions.
- `lib/types.ts` — TypeScript interfaces.
- `lib/i18n.ts` — Internationalization (English + Korean).
- `next.config.js` — Rewrites `/api-backend/*` to the backend URL.
- `web/.env.local` — set `NEXT_PUBLIC_API_URL` to override API server (default: port 8000).

### Persistence

- **Neo4j** — Knowledge graph (primary).
- **SQLite** (`data/health_map.db`) — Pipeline run history, KG stats snapshots, demand tracking, contradictions, yield stats.
- **Manifests** (`data/manifests/`) — Pipeline cascade coordination.
- **PID/logs** (`.run/`) — Local service management.

## Common Commands

### Full Stack (from repo root)

```bash
make start          # Start everything: Neo4j → Server → Web (background)
make stop           # Stop everything
make check          # Check status of all modules (Neo4j, Pipeline, Server, Web)
make ports          # Check port usage (7474, 7687, 8000, 3000)
make kg-status      # KG node/relationship counts by label and type
make test           # Run all tests (kg_pipeline + server)
```

### Docker (from repo root)

```bash
docker compose up -d   # Start all services (web: 3001, API: 8000, Neo4j: 7474)
docker compose down
```

### KG Pipeline (from `kg_pipeline/` with venv active)

```bash
cd kg_pipeline && source venv/bin/activate
# First time: python -m venv venv && pip install -r requirements.txt
# Copy .env.example to .env and add GEMINI_API_KEY

python run_pipeline.py                        # Full run: Fetch → Extract → Ingest
python run_pipeline.py --steps fetch,extract  # Selective steps
python src/fetch_papers.py                    # Step 1 only
python src/extract_triples.py                 # Step 2 only
python src/ingest_to_neo4j.py                 # Step 3 only
python src/validate_run.py --neo4j            # Regression test — run after ANY pipeline code change
docker-compose up -d                          # Start Neo4j if not running (kg_pipeline's own compose)
```

### Tests

```bash
# Pipeline tests (from kg_pipeline/ with venv active)
python -m pytest tests/ -v
python -m pytest tests/test_ontology.py -v
python -m pytest tests/test_ontology.py::test_name -v

# Server tests (from repo root)
python -m pytest server/tests/ -v
python -m pytest server/tests/test_canonical.py -v
```

### Server (from repo root)

```bash
uvicorn server.main:app --reload              # Port 8000
uvicorn server.main:app --reload --port 8001  # Alternate port
# API docs: http://127.0.0.1:8000/docs
```

### Web (from `web/`)

```bash
cd web && npm run dev         # Port 3000
npm run dev:3001              # Alternate port (3001)
npm run build && npm start    # Production
next lint                     # Lint
```

### Monitoring with port overrides

```bash
SKIP_CHECKS=web make check
SERVER_URL=http://127.0.0.1:8001 WEB_URL=http://127.0.0.1:3001 make check
```

## Service Ports

- Neo4j: 7474 (HTTP), 7687 (Bolt)
- FastAPI Server: 8000
- Web Client: 3000 (local dev), 3001 (Docker or alternate)

## Database Credentials

- Neo4j: `foodnot4self` / `foodnot4self` at `bolt://localhost:7687`

## Core Principles

### Zero-Error Tolerance
Every recommendation/restriction must be linked to at least one KG relationship with `source_id`. API response models enforce this — no food is returned without an `evidence[]` array.

### Term Standardization (Critical)
All entity names, API fields, UI labels must use canonical forms (e.g. "Vitamin D" not "vitamin d", "Type 2 diabetes" not "T2DM"). When adding new entity name variants:
1. Add to `CANONICAL_ENTITY_NAMES` and `ENTITY_TYPE_ALIASES` in `kg_pipeline/src/ontology.py`
2. Mirror changes in `server/canonical.py`

### KG Schema
Relationship properties required on every triple: `source_id`, `context`, `journal`, `pub_date`. Optional: `source_type` (PMC, FDA, drug_label), `evidence_type` (RCT, meta-analysis, etc.).

Predicates: `PREVENTS`, `CAUSES`, `TREATS`, `CONTAINS`, `AGGRAVATES`, `REDUCES_RISK_OF`, `ALLEVIATES`, `EARLY_SIGNAL_OF`, `SUBSTITUTES_FOR`, `COMPLEMENTS_DRUG`, `PART_OF`, `OCCURS_AT`, `INCREASES_RISK_OF`, `MODIFIABLE_BY`, `EXPLAINS_WHY`.

### UI Trust Visualization
- **Blue** badge = Information (raw evidence, single source)
- **Green** badge = Knowledge (KG-backed, possibly multi-source)
- **Gold** badge = Wisdom (recommendation, path, conclusion)

## Environment Variables

| Var | Location | Purpose |
|-----|----------|---------|
| `GEMINI_API_KEY` | `kg_pipeline/.env` | Required for Extract step |
| `NEO4J_URI/USER/PASSWORD` | `kg_pipeline/.env`, `server/.env` | Override Neo4j connection |
| `CORS_ORIGINS` | `server/.env` | Comma-separated origins or `*` |
| `CONTEXT_ENCRYPTION_KEY` | root `.env` or `server/.env` | Enables encrypted `/api/me/context/save` |
| `MASTER_GRAPH_PATH` | `server/.env` | Enables pipeline stats in `/api/kg/stats` |

## New Agent Checklist

When adding a new pipeline agent/step, ensure it:
1. Reads the previous step's manifest when using the same `RUN_ID`
2. Writes its own manifest to `data/manifests/`
3. Uses ontology normalization (`normalize_entity_name`, `normalize_entity_type`, `normalize_predicate`)
4. Attaches `source_id` and `pub_date` to every triple (zero-error rule)