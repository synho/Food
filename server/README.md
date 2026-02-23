# Health Navigation API (Server)

FastAPI server for health map, food recommendations, and evidence. Neo4j as KG backend.

## Principles

- **Zero-error**: Every recommendation/restriction has at least one `evidence` record (source_id required).
- **Term standardization**: All entity names canonical (see `canonical.py`; keep in sync with `kg_pipeline/src/ontology.py`).

## Setup

```bash
cd server
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create `.env` (optional; defaults match kg_pipeline):

- `NEO4J_URI=bolt://localhost:7687`
- `NEO4J_USER=foodnot4self`
- `NEO4J_PASSWORD=foodnot4self`
- `CONTEXT_ENCRYPTION_KEY` — optional; for encrypted save/restore of user context. Generate with:  
  `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`  
  If unset, `/api/me/context/save` and `/api/me/context/restore` return 503.

Start Neo4j (e.g. from kg_pipeline: `docker-compose up -d`).

## Run

From repo root (install deps first: `pip install -r server/requirements.txt`):

```bash
uvicorn server.main:app --reload
```

Or from `server/` with venv:

```bash
cd server && source venv/bin/activate && pip install -r requirements.txt && uvicorn main:app --reload
```
(If from server/, use relative imports in main: `from models...` / `from services...` or set PYTHONPATH to repo root.)

API: http://127.0.0.1:8000. Docs: http://127.0.0.1:8000/docs.

## Endpoints

- `GET /health` — health check
- `GET /api/suggest?q=...&field=conditions|symptoms|medications|goals` — suggest canonical/similar terms for spelling and autocomplete.
- `POST /api/context/from-text` — body: `{ "text": "free-form self-intro..." }`. Returns extracted `UserContext` (age, gender, conditions, symptoms, medications, goals).
- `POST /api/recommendations/foods` — body: `UserContext`. Returns recommended and restricted foods with reason and evidence.
- `POST /api/health-map/position` — body: `UserContext`. Returns active conditions/symptoms and nearby risks (diseases, early signals).
- `POST /api/health-map/safest-path` — body: `UserContext`. Returns actionable steps (increase/reduce) with evidence.
- `POST /api/guidance/early-signals` — body: `UserContext`. Returns early signals (symptom → disease), foods that reduce, foods to avoid.
- `POST /api/guidance/general` — body: `UserContext`. Returns general food summary and age-related guidance (why pay attention to diet/exercise) with evidence.
- `GET /api/recommendations/drug-substitution?drug=Metformin` — foods/ingredients that substitute or complement a drug; evidence from KG. Not medical advice.
- `POST /api/recommendations/drug-substitution` — body: `{ "drugs": ["Metformin", "…"] }`. Same as GET but for multiple drugs.
- `POST /api/me/context/save` — body: `UserContext`. Saves context encrypted at rest; returns one-time `restore_token`. Requires `CONTEXT_ENCRYPTION_KEY`.
- `GET /api/me/context/restore?restore_token=…` — returns saved context (one-time use); 404 if invalid/expired.
- Optional header **`X-Plan`**: `free` | `paid` (default `free`) for future tiered access. See `server/TIERED_ACCESS.md`.
