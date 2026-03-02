# Project Status — Food (Health Navigation Platform)
Generated: 2026-03-01

---

## 👋 When You Come Back — Say "Hi Food"

**One command to start everything:**
```bash
cd ~/Projects/Food
bash hi_food.sh
```

This will:
1. Start Neo4j + FastAPI server + Next.js web (`make start`)
2. Health-check all services (`make check`)
3. Run the pipeline to catch new papers published since last session
4. Start `watch_kg.py` daemon (continuous 10-min gap-filling)

**Then open:**
- App → http://localhost:3000
- KG Dashboard → http://localhost:3000/kg
- **Graph Explorer → http://localhost:3000/kg/explore** ← try "Vitamin D", "Type 2 diabetes"
- API Docs → http://localhost:8000/docs

**To continue improving KG:**
```bash
cd kg_pipeline && source venv/bin/activate
python improve_kg.py --iters 10   # 10-iteration gap-fill loop
```

**To check what's changed:**
```bash
make kg-status                    # node/rel counts
tail -f kg_pipeline/logs/watch_kg.log  # watcher activity
```

**Last session left off at:**
- KG: **17,291 nodes · 31,826 rels · 19,727 triples** from 2,710 papers
- Next focus: **UI refinement in Cursor** (see TODOs section)

---

## 1. Directory Structure

```
Food/
├── server/                        # FastAPI backend (port 8000)
│   ├── main.py                    # App entry + all API routes (30+ endpoints)
│   ├── neo4j_client.py            # Singleton Neo4j driver + kg_stats
│   ├── db.py                      # SQLite persistence (pipeline runs, KG snapshots, demand)
│   ├── pipeline_scheduler.py      # Adaptive background scheduler
│   ├── canonical.py               # Canonical entity names (mirror of kg_pipeline/src/ontology.py)
│   ├── context_store.py           # Encrypted user context save/restore
│   ├── models/                    # Pydantic models (UserContext, zero-error responses)
│   └── services/                  # One file per API domain (14 services)
│
├── kg_pipeline/                   # DIKW pipeline: Data → Information → Knowledge → Wisdom
│   ├── run_pipeline.py            # Orchestrator: fetch → extract → ingest
│   ├── improve_kg.py              # N-iteration gap-aware improvement loop  ← NEW
│   ├── watch_kg.py                # Continuous 10-min watcher daemon        ← NEW
│   ├── config.yaml                # 66 journals, 10 yr, 500 max results
│   └── src/
│       ├── ontology.py            # Single source of truth: entity types, predicates, names
│       ├── fetch_papers.py        # NCBI PMC fetcher
│       ├── fetch_europe_pmc.py    # Europe PMC fetcher                      ← NEW
│       ├── fetch_fda_labels.py    # FDA drug label fetcher (26 drug classes) ← NEW
│       ├── extract_triples.py     # LLM triple extraction (Bedrock Nova Micro)
│       ├── consolidate_graph.py   # Master graph writer
│       ├── ingest_to_neo4j.py     # Neo4j MERGE ingestor
│       ├── reextract.py           # Haiku re-extraction for zero-triple papers (bug-fixed)
│       ├── entity_resolver.py     # Duplicate node merger
│       ├── smart_fetch.py         # Gap-targeted PMC fetch (28 topic clusters)
│       └── kg_gap_analyzer.py     # KG coverage gap analysis
│
├── web/                           # Next.js 14 frontend (port 3000)
│   ├── app/
│   │   ├── page.tsx               # Home — context form + recommendations + clinical insights
│   │   ├── kg/
│   │   │   ├── page.tsx           # KG Dashboard (/kg)
│   │   │   └── explore/
│   │   │       └── page.tsx       # KG Graph Explorer (/kg/explore)         ← NEW
│   │   ├── clinical/page.tsx      # Clinical Explorer
│   │   └── map/                   # Health Map
│   ├── components/
│   │   ├── kg/
│   │   │   ├── KgGraphExplorer.tsx  # Force-graph visualization (react-force-graph-2d) ← NEW
│   │   │   ├── ChartComponents.tsx
│   │   │   ├── TrendChart.tsx
│   │   │   └── PipelinePanel.tsx
│   │   ├── clinical/MechanismChainSVG.tsx
│   │   └── ClinicalInsights.tsx
│   └── lib/
│       ├── api.ts                 # All API client functions (30+)
│       ├── types.ts               # TypeScript interfaces
│       └── i18n.ts                # English + Korean i18n
│
├── Makefile                       # start / stop / check / kg-status / test
├── docker-compose.yml             # Neo4j + API + web
└── CLAUDE.md                      # Architecture & development guidance
```

---

## 2. Knowledge Graph — Current State

| Metric            | Value          |
|-------------------|----------------|
| **Nodes**         | 17,291         |
| **Relationships** | 31,826         |
| **Triples**       | 19,727         |
| **Papers**        | 2,710          |
| **Data sources**  | NCBI PMC · Europe PMC · FDA Drug Labels |
| **Journals**      | 66             |
| **Time window**   | 10 years       |

**Top node types:** Biomarker (2,715) · Disease (2,481) · LifestyleFactor (2,182) · Mechanism (2,085) · Symptom (1,334) · Drug (1,204) · Nutrient (1,118) · Food (960)

**Top relationship types:** INCREASES_RISK_OF (5,786) · CAUSES (3,493) · ALLEVIATES (3,027) · RELATES_TO (2,827) · REDUCES_RISK_OF (2,751) · TREATS (1,800) · TARGETS_MECHANISM (1,782) · BIOMARKER_FOR (1,618)

---

## 3. API Endpoints (server/main.py)

### KG & Pipeline
- `GET /api/kg/stats` — node/rel counts, 30-day trend, pipeline triples
- `GET /api/kg/explore?entity=&hops=&limit=` — subgraph neighborhood  **← NEW**
- `GET /api/kg/food-chain?food=` — food → nutrient → disease chain
- `GET /api/kg/demand` — top queried conditions
- `GET /api/kg/contradictions` — conflicting evidence
- `GET|POST /api/pipeline/status|trigger|history|yield`

### Recommendations
- `POST /api/recommendations/foods` — recommended + restricted foods with evidence
- `GET|POST /api/recommendations/drug-substitution`

### Health Map
- `POST /api/health-map/position` — map location from user context
- `POST /api/health-map/safest-path` — actionable escape steps
- `POST /api/health-map/landmines` — 6 landmine disease risk levels
- `POST /api/health-map/interrogate` — agentic follow-up questions

### Clinical
- `POST /api/clinical/biomarkers` — biomarkers for conditions + improving foods
- `GET  /api/clinical/mechanisms/{disease}` — food→mechanism→disease chains
- `POST /api/clinical/drug-interactions` — food contraindications per drug

### User
- `POST /api/context/from-text` — NLP context extraction
- `POST /api/me/context/save` · `GET /api/me/context/restore`
- `POST /api/me/snapshot` · `GET /api/me/trajectory`
- `GET  /api/suggest` — autocomplete

---

## 4. Recent Changes (this sprint)

| Commit    | What                                                                 |
|-----------|----------------------------------------------------------------------|
| `42cb324` | KG Graph Explorer — `/kg/explore` force-graph visualization          |
| `0091cfc` | Europe PMC + FDA drug label sources; improve_kg.py multi-source fetch |
| `0d1a84e` | 66 journals, 10-year window, longevity aging keywords                |
| `8ac4306` | watch_kg.py daemon, improve_kg.py loop, reextract.py bug fix         |
| `8254a64` | 4 bug fixes: crash risk, SVG compat, memory leak, re-render loop     |

---

## 5. Pipeline Tooling

| Script                        | Purpose                                      |
|-------------------------------|----------------------------------------------|
| `run_pipeline.py`             | Full NCBI fetch → extract → ingest           |
| `watch_kg.py`                 | Continuous 10-min watcher (running: PID 58205) |
| `improve_kg.py --iters N`     | N-iteration gap-aware improvement loop        |
| `src/reextract.py --limit N`  | Haiku re-extraction of zero-triple papers    |
| `src/entity_resolver.py`      | Merge case-variant duplicate nodes           |
| `src/fetch_europe_pmc.py`     | Europe PMC broad sweep                       |
| `src/fetch_fda_labels.py`     | FDA drug label interactions                  |
| `src/smart_fetch.py`          | Gap-targeted PMC queries (28 clusters)       |
| `src/kg_gap_analyzer.py`      | Coverage gap analysis (8 gap types)          |

---

## 6. Remaining TODOs

### Phase 5 — Mobile (current roadmap phase)
- [ ] Wearables integration (Apple Watch, Apple Health, Google Fit) — deferred / 보류

### Phase 6 — Monetization
- [ ] Pricing model (free + paid tiers)
- [ ] Server plan/rate limits/feature flags
- [ ] Billing integration

### KG Quality
- [ ] ClinicalTrials.gov as data source (RCT intervention data)
- [ ] USDA FoodData Central — quantitative nutrient composition (needs API key + quantity schema design)
- [ ] FDA label extraction quality — `CONTRAINDICATED_WITH` filtered by ontology; needs ontology extension or prompt tuning for drug-nutrient triples
- [ ] Europe PMC pagination — currently 500×2 results; cursor pagination available for deeper pull

### Visualization
- [ ] Full graph overview (clustered summary of all 17K nodes)
- [ ] Saved entity searches / bookmarks
- [ ] Side-by-side entity comparison

---

## 7. Service Ports

| Service           | Port  |
|-------------------|-------|
| Neo4j HTTP        | 7474  |
| Neo4j Bolt        | 7687  |
| FastAPI Server    | 8000  |
| Next.js (local)   | 3000  |
| Next.js (Docker)  | 3001  |

**Neo4j credentials:** `foodnot4self` / `foodnot4self` at `bolt://localhost:7687`
