"""
Health Navigation API. FastAPI server; Neo4j for KG.
Zero-error: recommendations/restrictions only with evidence. Standardized terms throughout.
Run from repo root: uvicorn server.main:app --reload
"""
from contextlib import asynccontextmanager
from pathlib import Path

import os

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

from server.models.user_context import UserContext
from server.models.responses import (
    RecommendationsResponse,
    PositionResponse,
    SafestPathResponse,
    EarlySignalGuidanceResponse,
    GeneralGuidanceResponse,
    DrugSubstitutionResponse,
    BiomarkerResponse,
    MechanismResponse,
    DrugInteractionResponse,
)
from server.services.recommendations import get_recommendations
from server.services.position import get_position
from server.services.safest_path import get_safest_path
from server.services.early_signals import get_early_signal_guidance
from server.services.general_guidance import get_general_guidance
from server.services.drug_substitution import get_drug_substitution
from server.neo4j_client import close_driver


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize persistent storage
    from server.db import init_db
    init_db()
    # Start adaptive pipeline scheduler (background thread)
    from server.pipeline_scheduler import scheduler
    scheduler.start(initial_delay_minutes=int(os.getenv("SCHEDULER_INITIAL_DELAY_MIN", "10")))
    yield
    scheduler.stop()
    close_driver()


app = FastAPI(
    title="Health Navigation API",
    description="Food recommendations and health map; all recommendations with evidence (zero-error).",
    lifespan=lifespan,
)
_cors_env = os.getenv("CORS_ORIGINS", "").strip()
if _cors_env == "*":
    _cors_origins = ["*"]
elif _cors_env:
    _cors_origins = [o.strip() for o in _cors_env.split(",") if o.strip()]
else:
    _cors_origins = ["http://localhost:3000"]
app.add_middleware(CORSMiddleware, allow_origins=_cors_origins, allow_methods=["*"], allow_headers=["*"])


class TieredAccessMiddleware(BaseHTTPMiddleware):
    """Set request.state.plan from X-Plan header (default: free). For future rate limits / feature flags."""

    async def dispatch(self, request: Request, call_next):
        plan = request.headers.get("X-Plan", "free").strip().lower()
        if plan not in ("free", "paid"):
            plan = "free"
        request.state.plan = plan
        return await call_next(request)


app.add_middleware(TieredAccessMiddleware)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/pipeline/status")
def pipeline_status():
    """Pipeline scheduler status: state, last run, next run, adaptive interval."""
    from server.pipeline_scheduler import scheduler
    return scheduler.status()


@app.post("/api/pipeline/trigger")
def pipeline_trigger():
    """Force an immediate pipeline run (smart-fetch → extract → ingest)."""
    from server.pipeline_scheduler import scheduler
    return scheduler.trigger_now()


@app.get("/api/pipeline/history")
def pipeline_history(limit: int = 20):
    """Pipeline run history from persistent storage (survives restarts)."""
    from server.db import get_run_history
    return get_run_history(limit=min(limit, 100))


@app.get("/api/pipeline/yield")
def pipeline_yield():
    """Per-query fetch yield statistics — shows which queries produce useful triples."""
    from server.db import get_yield_stats
    return get_yield_stats()


@app.get("/api/kg/food-chain")
def kg_food_chain(food: str = ""):
    """
    Multi-hop KG chain for a food: Food → Nutrient → Disease/Symptom.
    Shows *why* a food is beneficial or risky via the nutrient mechanism.
    Example: GET /api/kg/food-chain?food=Salmon
    Returns: { food, chain: [{ nutrient, relationship_type, target, evidence[] }] }
    """
    if not food.strip():
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="food query parameter is required")
    from server.services.food_chain import get_food_chain
    return get_food_chain(food.strip())


@app.get("/api/kg/stats")
def kg_stats():
    """
    Knowledge Graph statistics for dashboard: Neo4j node/relationship counts,
    breakdown by label and relationship type. Includes 30-day trend from SQLite.
    Optionally pipeline triples if MASTER_GRAPH_PATH is set.
    """
    import os
    from server.neo4j_client import get_kg_stats as neo4j_kg_stats
    from server.db import save_kg_snapshot, get_kg_trend
    neo4j_data = neo4j_kg_stats()
    out = {"neo4j": neo4j_data}
    # Save daily snapshot if we got valid data
    if "nodes" in neo4j_data and not neo4j_data.get("error"):
        try:
            save_kg_snapshot(
                total_nodes=neo4j_data["nodes"],
                total_relationships=neo4j_data["relationships"],
                by_label=neo4j_data.get("by_label"),
                by_relationship_type=neo4j_data.get("by_relationship_type"),
            )
        except Exception:
            pass
    # Map DB field names to frontend-expected names; reverse to chronological
    trend_raw = get_kg_trend(90)
    out["trend"] = [
        {
            "date": t["recorded_at"],
            "nodes": t["total_nodes"],
            "relationships": t["total_relationships"],
        }
        for t in reversed(trend_raw)
    ]
    master_path = os.getenv("MASTER_GRAPH_PATH")
    if master_path and os.path.isfile(master_path):
        try:
            import json
            with open(master_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            triples = data if isinstance(data, list) else []
            with_sid = [t for t in triples if t.get("source_id")]
            out["pipeline"] = {
                "triples": len(triples),
                "with_source_id": len(with_sid),
                "unique_sources": len(set(t.get("source_id") for t in with_sid if t.get("source_id"))),
            }
        except Exception:
            pass
    return out


@app.get("/api/kg/live")
def kg_live():
    """Live expansion metrics: process status, corpus counts, cycle history.

    Reads from the filesystem (PID files, paper directories, expansion logs)
    so the dashboard can show real-time progress during overnight runs.
    """
    import glob
    import re
    import subprocess
    from pathlib import Path

    kg_root = Path(__file__).resolve().parent.parent / "kg_pipeline"
    data_root = kg_root / "data"
    logs_dir = kg_root / "logs"
    run_dir = kg_root / ".run"

    result: dict = {"active": False, "corpus": {}, "cycles": [], "processes": []}

    # ── Corpus counts ─────────────────────────────────────────────────────
    raw_dir = data_root / "raw_papers"
    ext_dir = data_root / "extracted_triples"
    raw_count = len(list(raw_dir.glob("*.json"))) if raw_dir.is_dir() else 0
    ext_count = len([f for f in ext_dir.glob("*_triples.json")]) if ext_dir.is_dir() else 0
    result["corpus"] = {
        "raw_papers": raw_count,
        "extracted": ext_count,
        "backlog": max(0, raw_count - ext_count),
    }

    # ── Process detection ─────────────────────────────────────────────────
    try:
        ps = subprocess.run(
            ["ps", "aux"], capture_output=True, text=True, timeout=5,
        )
        procs = []
        for line in ps.stdout.splitlines():
            for name in ("watch_kg", "run_expansion", "run_overnight",
                         "fetch_papers", "extract_triples", "smart_fetch",
                         "ingest_to_neo4j", "run_pipeline"):
                if name in line and "grep" not in line:
                    parts = line.split()
                    procs.append({
                        "pid": int(parts[1]),
                        "cpu": parts[2],
                        "mem": parts[3],
                        "elapsed": parts[9] if len(parts) > 9 else "",
                        "name": name,
                    })
                    break
        result["processes"] = procs
        result["active"] = any(p["name"] in ("watch_kg", "run_expansion", "run_overnight") for p in procs)
    except Exception:
        pass

    # ── Latest expansion cycle log ────────────────────────────────────────
    cycle_logs = sorted(logs_dir.glob("expansion_cycles_*.log"), reverse=True)
    if cycle_logs:
        try:
            text = cycle_logs[0].read_text()
            cycles = []
            for line in text.splitlines():
                m = re.search(
                    r"\[CYCLE\s+(\d+)\]\s+papers \+(\d+)\s+nodes \+(\d+)\s+rels \+(\d+)\s+total=(\d+) nodes / (\d+) rels",
                    line,
                )
                if m:
                    ts_match = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
                    cycles.append({
                        "cycle": int(m.group(1)),
                        "papers": int(m.group(2)),
                        "nodes_delta": int(m.group(3)),
                        "rels_delta": int(m.group(4)),
                        "total_nodes": int(m.group(5)),
                        "total_rels": int(m.group(6)),
                        "time": ts_match.group(1) if ts_match else "",
                    })
            result["cycles"] = cycles[-20:]  # last 20 cycles
            # Extract start time
            start_match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*\[START\]", text)
            if start_match:
                result["started_at"] = start_match.group(1)
        except Exception:
            pass

    return result


@app.get("/api/kg/demand")
def kg_demand(limit: int = 20):
    """Top queried conditions/symptoms ranked by demand — drives gap prioritization."""
    from server.db import get_top_demand
    return get_top_demand(limit=min(limit, 100))


@app.get("/api/kg/contradictions")
def kg_contradictions():
    """
    Return detected evidence contradictions — entities that both help and harm
    the same disease. Each record includes verdict: negative_contested, positive_contested, or debated.
    """
    from server.db import get_contradictions
    return get_contradictions()


@app.get("/api/suggest")
def suggest(q: str = "", field: str = "conditions"):
    """
    Suggest canonical or most similar terms for user input (spelling / autocomplete).
    field: conditions | symptoms | medications | goals
    """
    from server.services.suggest import get_suggestions
    allowed = ("conditions", "symptoms", "medications", "goals")
    f = field if field in allowed else "conditions"
    return {"suggestions": get_suggestions(q or "", f)}


class InterrogateRequest(BaseModel):
    context: UserContext = Field(default_factory=UserContext)
    answered_fields: list[str] = Field(default_factory=list,
        description="Question IDs already answered by user — prevents re-asking")


def _log_demand_from_context(ctx: UserContext) -> None:
    """Lightweight background demand logging from user context."""
    try:
        from server.db import log_demand
        if ctx.conditions:
            log_demand(ctx.conditions, "condition")
        if ctx.symptoms:
            log_demand(ctx.symptoms, "symptom")
    except Exception:
        pass  # Non-critical


@app.post("/api/health-map/landmines")
def health_map_landmines(ctx: UserContext):
    """
    Detect landmine disease risk levels from user context + KG evidence.
    Returns all 6 landmine diseases with risk_level (none|low|medium|high),
    risk factors present/missing, early warning signs, escape routes, and KG evidence.
    """
    _log_demand_from_context(ctx)
    from server.services.landmine_detector import get_landmines
    return get_landmines(ctx)


@app.post("/api/health-map/interrogate")
def health_map_interrogate(body: InterrogateRequest):
    """
    Agentic health map assessment.
    Returns completeness score (0-100), KG-driven insights, inferred conditions,
    and the 2-3 most critical follow-up questions not yet answered.
    Each call evolves: pass answered_fields from prior responses to get new questions.
    """
    from server.services.health_map_agent import interrogate
    return interrogate(body.context, body.answered_fields)


class FromTextRequest(BaseModel):
    text: str = Field(default="", description="Free-form self-introduction text")


@app.post("/api/context/from-text")
def context_from_text_endpoint(body: FromTextRequest):
    """
    Extract structured UserContext from free-form self-intro text.
    Returns:
      context: UserContext fields (age, gender, conditions, symptoms, medications, goals)
      inferred: list of field names whose values were guessed (not exact-matched)
      follow_up: list of targeted questions to confirm guesses or fill missing fields
    """
    from server.services.context_from_text import context_from_text
    ctx, inferred, follow_up = context_from_text(body.text or "")
    return {"context": ctx.model_dump(), "inferred": inferred, "follow_up": follow_up}


@app.post("/api/recommendations/foods", response_model=RecommendationsResponse)
def recommendations_foods(request: Request, ctx: UserContext):
    """
    Recommended and restricted foods from KG. Only items with at least one evidence record.
    User context (conditions, symptoms) is normalized to canonical names for KG lookup.
    Free plan: up to 5 items. Paid plan: up to 20 items.
    """
    _log_demand_from_context(ctx)
    return get_recommendations(
        conditions=ctx.conditions or [],
        symptoms=ctx.symptoms or [],
        age=ctx.age,
        gender=ctx.gender,
        limit=20,
        plan=request.state.plan,
    )


@app.post("/api/health-map/position", response_model=PositionResponse)
def health_map_position(request: Request, ctx: UserContext):
    """
    Where the user is on the map (active conditions/symptoms) and nearby risks (diseases, early signals).
    Free plan: up to 5 nearby risks. Paid plan: up to 30.
    """
    _log_demand_from_context(ctx)
    return get_position(
        conditions=ctx.conditions or [],
        symptoms=ctx.symptoms or [],
        plan=request.state.plan,
    )


@app.post("/api/health-map/safest-path", response_model=SafestPathResponse)
def health_map_safest_path(request: Request, ctx: UserContext):
    """
    Actionable steps to evacuate to safety (e.g. increase X, reduce Y) with evidence.
    Free plan: up to 3 foods per step. Paid plan: up to 5.
    """
    return get_safest_path(
        conditions=ctx.conditions or [],
        symptoms=ctx.symptoms or [],
        limit=10,
        plan=request.state.plan,
    )


@app.post("/api/guidance/early-signals", response_model=EarlySignalGuidanceResponse)
def guidance_early_signals(ctx: UserContext):
    """
    Early signals to watch (symptom → disease); foods that reduce vs foods to avoid. Prepare in advance.
    """
    return get_early_signal_guidance(symptoms=ctx.symptoms or [], limit=15)


@app.post("/api/guidance/general", response_model=GeneralGuidanceResponse)
def guidance_general(ctx: UserContext):
    """
    General guidance by age: age-related changes, why pay attention to diet and exercise. With evidence.
    """
    return get_general_guidance(age=ctx.age)


class DrugSubstitutionRequest(BaseModel):
    """Request body for drug-substitution API."""
    drugs: list[str] = Field(default_factory=list, description="Drug names (e.g. Metformin)")


@app.get("/api/recommendations/drug-substitution", response_model=DrugSubstitutionResponse)
def drug_substitution_get(drug: str | None = None):
    """
    Foods/ingredients that substitute or complement a drug. Evidence from KG (FDA, drug_label, PMC).
    Query param: drug=Metformin. Not medical advice; consult doctor/pharmacist.
    """
    drugs = [drug] if drug and drug.strip() else []
    return get_drug_substitution(drugs=drugs)


@app.post("/api/recommendations/drug-substitution", response_model=DrugSubstitutionResponse)
def drug_substitution_post(body: DrugSubstitutionRequest):
    """
    Foods/ingredients that substitute or complement given drugs. Evidence from KG.
    Not medical advice; consult doctor/pharmacist.
    """
    return get_drug_substitution(drugs=body.drugs or [])


# ----- Medical KG layer: biomarkers, mechanisms, drug interactions -----

class ClinicalBiomarkerRequest(BaseModel):
    conditions: list[str] = Field(default_factory=list, description="Conditions to find biomarkers for")


@app.post("/api/clinical/biomarkers", response_model=BiomarkerResponse)
def clinical_biomarkers(body: ClinicalBiomarkerRequest):
    """
    Given conditions, find relevant biomarkers and foods that improve them.
    Uses medical KG: Biomarker -BIOMARKER_FOR-> Disease,
    Food/Nutrient -INCREASES/DECREASES_BIOMARKER-> Biomarker.
    """
    from server.services.biomarkers import get_biomarkers
    return get_biomarkers(conditions=body.conditions or [])


@app.get("/api/clinical/mechanisms/{disease}", response_model=MechanismResponse)
def clinical_mechanisms(disease: str):
    """
    Mechanism graph for a disease: Food/Nutrient -> Mechanism -> Disease with evidence.
    Multi-hop chain showing *why* a food helps or harms through biological mechanism.
    """
    from server.services.mechanisms import get_mechanisms
    return get_mechanisms(disease=disease)


class ClinicalDrugInteractionRequest(BaseModel):
    medications: list[str] = Field(default_factory=list, description="Medications to check interactions for")


@app.post("/api/clinical/drug-interactions", response_model=DrugInteractionResponse)
def clinical_drug_interactions(body: ClinicalDrugInteractionRequest):
    """
    Given medications, find food contraindications and complements from the medical KG.
    Nutrient -CONTRAINDICATED_WITH-> Drug, Food/Nutrient -COMPLEMENTS_DRUG-> Drug.
    Not medical advice — consult doctor/pharmacist.
    """
    from server.services.mechanisms import get_drug_interactions
    return get_drug_interactions(medications=body.medications or [])


# ----- Encrypted context save/restore (optional; requires CONTEXT_ENCRYPTION_KEY) -----

try:
    from server.context_store import save_context, get_context, is_encryption_available
except ImportError:
    save_context = get_context = None
    is_encryption_available = lambda: False


class SaveContextResponse(BaseModel):
    restore_token: str
    message: str = "Saved. Your context is encrypted at rest. Use the restore code to load it later."


@app.post("/api/me/context/save", response_model=SaveContextResponse)
def me_context_save(ctx: UserContext):
    """
    Save user context encrypted at rest. Returns a one-time restore code.
    Requires CONTEXT_ENCRYPTION_KEY to be set on the server.
    """
    if save_context is None or not is_encryption_available():
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Encrypted save is not configured (CONTEXT_ENCRYPTION_KEY).")
    token = save_context(ctx)
    if not token:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Encrypted save is not configured.")
    return SaveContextResponse(restore_token=token)


@app.get("/api/me/context/restore")
def me_context_restore(restore_token: str = ""):
    """
    Restore previously saved context by one-time code. Returns the context; code is invalidated after use.
    """
    if get_context is None or not is_encryption_available():
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Encrypted restore is not configured.")
    ctx = get_context(restore_token)
    if ctx is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Invalid or expired restore code.")
    return ctx.model_dump()


# ----- Longitudinal user tracking (snapshots + trajectory) -----

class SnapshotRequest(BaseModel):
    user_token: str = Field(description="Hash of user context for grouping (no PII)")
    context: UserContext = Field(default_factory=UserContext)
    position_x: float | None = None
    position_y: float | None = None
    zone: str | None = None
    landmine_risks: dict | None = Field(default=None, description="JSON: {disease: risk_level}")


@app.post("/api/me/snapshot")
def me_snapshot(body: SnapshotRequest):
    """Save a context snapshot after map render. Returns snapshot id."""
    from server.db import save_snapshot
    snapshot_id = save_snapshot(
        user_token=body.user_token,
        age=body.context.age,
        conditions=body.context.conditions,
        symptoms=body.context.symptoms,
        position_x=body.position_x,
        position_y=body.position_y,
        zone=body.zone,
        landmine_risks=body.landmine_risks,
    )
    return {"snapshot_id": snapshot_id}


@app.get("/api/me/trajectory")
def me_trajectory(token: str = "", limit: int = 50):
    """Return trajectory snapshots for a user token, oldest first."""
    if not token.strip():
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="token query parameter is required")
    from server.db import get_trajectory
    return get_trajectory(token.strip(), limit=min(limit, 200))


# ----- KG Graph Explorer -----

@app.get("/api/kg/explore")
def kg_explore(entity: str = "", hops: int = 1, limit: int = 80):
    """
    Return a subgraph neighborhood around a named entity for interactive visualization.
    hops: 1 (direct neighbors) or 2 (2-hop neighbors, heavier).
    Returns: { center, nodes: [{id, name, type}], edges: [{source, target, type, context, source_id}] }
    """
    from fastapi import HTTPException
    if not entity.strip():
        raise HTTPException(status_code=422, detail="entity query parameter is required")

    limit = max(10, min(limit, 200))
    hops  = max(1, min(hops, 2))

    from server.neo4j_client import get_driver
    driver = get_driver()

    try:
        with driver.session() as s:
            # Step 1: find closest matching node
            match_result = s.run(
                """
                MATCH (n)
                WHERE toLower(n.name) = toLower($entity)
                   OR toLower(n.name) CONTAINS toLower($entity)
                RETURN n.name AS name, labels(n)[0] AS type
                ORDER BY
                  CASE WHEN toLower(n.name) = toLower($entity) THEN 0 ELSE 1 END,
                  size(n.name)
                LIMIT 1
                """,
                entity=entity.strip(),
            ).single()

            if not match_result:
                return {"center": None, "nodes": [], "edges": []}

            center_name = match_result["name"]
            center_type = match_result["type"] or "Unknown"

            # Step 2: fetch 1-hop (or 2-hop) neighborhood
            if hops == 1:
                rows = s.run(
                    """
                    MATCH (start {name: $name})-[r]-(neighbor)
                    RETURN
                      start.name  AS src_name,  labels(start)[0]    AS src_type,
                      type(r)     AS rel_type,  r.context            AS context,
                      r.source_id AS source_id,
                      neighbor.name AS tgt_name, labels(neighbor)[0] AS tgt_type
                    LIMIT $limit
                    """,
                    name=center_name, limit=limit,
                ).data()
            else:
                rows = s.run(
                    """
                    MATCH (start {name: $name})-[r1]-(n1)-[r2]-(n2)
                    WHERE n2.name <> $name
                    RETURN
                      start.name AS src_name, labels(start)[0] AS src_type,
                      type(r1)   AS rel_type,  r1.context       AS context,
                      r1.source_id AS source_id,
                      n1.name    AS tgt_name,  labels(n1)[0]    AS tgt_type
                    UNION
                    MATCH (start {name: $name})-[r]-(neighbor)
                    RETURN
                      start.name  AS src_name, labels(start)[0]    AS src_type,
                      type(r)     AS rel_type,  r.context            AS context,
                      r.source_id AS source_id,
                      neighbor.name AS tgt_name, labels(neighbor)[0] AS tgt_type
                    LIMIT $limit
                    """,
                    name=center_name, limit=limit,
                ).data()

        # Build deduplicated node + edge lists
        nodes_seen: dict[str, dict] = {}
        edges: list[dict] = []
        edge_seen: set[tuple] = set()

        nodes_seen[center_name] = {"id": center_name, "name": center_name, "type": center_type, "is_center": True}

        for row in rows:
            for key_n, key_t in [("src_name", "src_type"), ("tgt_name", "tgt_type")]:
                n, t = row.get(key_n), row.get(key_t)
                if n and n not in nodes_seen:
                    nodes_seen[n] = {"id": n, "name": n, "type": t or "Unknown", "is_center": False}

            src, tgt, rel = row.get("src_name"), row.get("tgt_name"), row.get("rel_type")
            if src and tgt and rel:
                edge_key = (min(src, tgt), max(src, tgt), rel)
                if edge_key not in edge_seen:
                    edge_seen.add(edge_key)
                    edges.append({
                        "source":    src,
                        "target":    tgt,
                        "type":      rel,
                        "context":   (row.get("context") or "")[:200],
                        "source_id": row.get("source_id") or "",
                    })

        return {
            "center": center_name,
            "nodes":  list(nodes_seen.values()),
            "edges":  edges,
        }

    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))
