# Running the KG Pipeline

Run all commands from the **kg_pipeline** directory so paths in `config.yaml` resolve correctly.

## 1. Setup

```bash
cd kg_pipeline
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

- Create `.env` (copy from `.env.example`):
  - **GEMINI_API_KEY** — 필수. [Google AI Studio](https://aistudio.google.com/apikey)에서 API 키 발급 후 `.env`에 넣기. 없으면 Extract 단계가 데모 모드(LLM 미사용)로 동작.
  - Optional: `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` (기본값: foodnot4self / foodnot4self, URI: bolt://localhost:7687)

## 2. Config

Edit `config.yaml` to change:

- **fetch.days_back**: how many days back to search (default 30)
- **fetch.days_back**, **fetch.max_results**, **fetch.journals**: as above
- **fetch.skip_existing**: if `true` (default), skip PMCIDs that already have a file in `raw_papers` (incremental fetch). Set to `false` to re-download all.
- **fetch.humans_only**: if `true` (default), only human studies (no animal models); uses "humans"[MeSH Terms] in the query.
- **fetch.topic_keywords**: optional list (e.g. `["nutrition", "diet"]`) to narrow search; expand gradually or set to `[]` for no keyword filter. See `docs/PIPELINE_AGENTS.md`.
- **extract.model**: Gemini model (default `gemini-2.0-flash-lite`). Use a cheap model first; change after accuracy checks. See `docs/PIPELINE_AGENTS.md`.
- **paths**: where raw papers and extracted triples are stored

## 3. Pipeline steps (in order)

### Step 1: Fetch papers (PMC)

```bash
python src/fetch_papers.py
```

- Reads `config.yaml` (journals, days_back, max_results, paths).
- Saves JSON per article under `data/raw_papers/` (or path in config).

### Step 2: Extract triples (ontology-based, Gemini)

```bash
python src/extract_triples.py
```

- **Ontology-based**: Entity types and relationship types are defined in `src/ontology.py` (aligned with `docs/KG_SCHEMA_AND_EVIDENCE.md`). The extractor uses only these types and normalizes output for Neo4j.
- Reads from `data/raw_papers/`, writes to `data/extracted_triples/` and `master_graph.json`.
- Needs `GEMINI_API_KEY` in `.env`.
- Optionally run **consolidate** if you added triples manually or from another run:
  ```bash
  python src/consolidate_graph.py
  ```

### Step 3: Ingest to Neo4j

- Start Neo4j (e.g. `docker-compose up -d` in kg_pipeline). If you run Neo4j locally (e.g. Homebrew) instead of Docker, use the same URI and credentials in `.env`: `NEO4J_URI=bolt://localhost:7687`, `NEO4J_USER=foodnot4self`, `NEO4J_PASSWORD=foodnot4self`.
- Then:

```bash
python src/ingest_to_neo4j.py
```

- Reads `data/extracted_triples/master_graph.json` and loads into Neo4j.

## 4. Incremental fetch

By default, **fetch_papers.py** skips PMCIDs that already have a JSON file in `data/raw_papers/` (config: `fetch.skip_existing: true`). So repeated runs only fetch new articles. Set `skip_existing: false` in `config.yaml` to force re-download.

## 5. Full run (one command, cascade)

From `kg_pipeline` (venv active, Neo4j running e.g. `docker-compose up -d`):

```bash
python run_pipeline.py
```

- Runs **specialized agents** in order: **Fetch** → **Extract** → **Ingest** (cascade).
- Each agent writes a **manifest** to `data/manifests/`; the next agent can read the previous manifest (e.g. Ingest uses Extract’s `master_graph_path` when same RUN_ID).
- A **RUN_ID** (timestamp or env `RUN_ID`) ties the run; manifests are `fetch_{RUN_ID}.json`, `extract_{RUN_ID}.json`, `ingest_{RUN_ID}.json`. See `docs/AGENTS_AND_ARTIFACTS.md`.

## 6. Full run (manual steps)

```bash
cd kg_pipeline
source venv/bin/activate
docker-compose up -d    # if Neo4j not running
python src/fetch_papers.py
python src/extract_triples.py
python src/ingest_to_neo4j.py
```

## 7. Phase 1 expansion (30 days, 10–20 papers)

- In `config.yaml`: `fetch.days_back: 30`, `fetch.max_results: 15` (or 20). Then run the full pipeline (step 5 or 6).
- After a run, validate triples and optionally Neo4j:

```bash
python src/validate_run.py        # triples only
python src/validate_run.py --neo4j # triples + Neo4j node/rel counts
```

- Validation checks: `master_graph.json` exists, triples count, and that every triple has `source_id` (zero-error rule). See `.cursor/plans/roadmap.md` Phase 1.

## 8. Phase 4 expansion (90 days, 50–100 papers)

- In `config.yaml` set `fetch.days_back: 90` and `fetch.max_results: 50` (or 100) for a broader KG. Then run the full pipeline (step 5 or 6). See `docs/PIPELINE_STRATEGY.md`.
- **Deduplication/normalization**: Entity names are normalized (e.g. `ontology.CANONICAL_ENTITY_NAMES`, `normalize_entity_name`) so the same entity from different papers maps to one node. Same (subject, predicate, object) from multiple papers currently overwrite one relationship per run; for aggregating multiple evidence per triple, extend the schema (e.g. evidence list on relationship) in a later step.

## 9. Optional: USDA FoodData Central data stream

Adds quantitative CONTAINS triples (e.g. "Salmon CONTAINS Omega-3 — 2.5g/100g") from the USDA FDC API.

```bash
# 1. Get a free API key at https://fdc.nal.usda.gov/api-guide.html
# 2. Enable in config.yaml:
#      usda:
#        enabled: true
#        api_key: "YOUR_KEY"
#        max_foods: 5
# 3. Run manually:
python src/fetch_usda.py
# Output: data/usda_sample.json — inspect before integrating into pipeline
```

Not yet wired into `run_pipeline.py`. Review `data/usda_sample.json` output and finalize the CONTAINS-with-amount schema before full integration.

## 10. Optional: Gemini claim quality audit

Classifies a sample of extracted triples as **strong / supportive / overclaim** using Gemini, without touching Neo4j.

```bash
python src/audit_graph.py           # audit 5 triples (default, config: audit.sample_size)
python src/audit_graph.py --n 10   # override sample size
# Output: data/audit_report_sample.json
```

Run after extraction (`python src/extract_triples.py`) to catch overclaims before ingesting into Neo4j. Config (`config.yaml`):
```yaml
audit:
  sample_size: 5
  model: "gemini-2.0-flash-lite"
```

## 12. Optional: scheduled pipeline runs (e.g. weekly)

- To keep the KG updated with recent papers, run the pipeline on a schedule. Example (cron, run from repo `kg_pipeline`):
  - Set `fetch.days_back: 7` and `fetch.max_results: 20` in `config.yaml` (or use a separate config file).
  - Run weekly: `0 2 * * 0 cd /path/to/kg_pipeline && . venv/bin/activate && python run_pipeline.py`
- Incremental fetch (`skip_existing: true`) avoids re-downloading already-fetched PMCIDs.
