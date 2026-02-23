"""
Health Navigation API. FastAPI server; Neo4j for KG.
Zero-error: recommendations/restrictions only with evidence. Standardized terms throughout.
Run from repo root: uvicorn server.main:app --reload
"""
from contextlib import asynccontextmanager

import os

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
    yield
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
    breakdown by label and relationship type. Optionally pipeline triples if
    MASTER_GRAPH_PATH is set and the file exists.
    """
    import os
    from server.neo4j_client import get_kg_stats as neo4j_kg_stats
    out = {"neo4j": neo4j_kg_stats()}
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


class FromTextRequest(BaseModel):
    text: str = Field(default="", description="Free-form self-introduction text")


@app.post("/api/context/from-text")
def context_from_text_endpoint(body: FromTextRequest):
    """
    Extract structured UserContext from free-form self-intro text.
    Returns the same shape as UserContext (age, gender, conditions, symptoms, medications, goals).
    """
    from server.services.context_from_text import context_from_text
    ctx = context_from_text(body.text or "")
    return ctx.model_dump()


@app.post("/api/recommendations/foods", response_model=RecommendationsResponse)
def recommendations_foods(ctx: UserContext):
    """
    Recommended and restricted foods from KG. Only items with at least one evidence record.
    User context (conditions, symptoms) is normalized to canonical names for KG lookup.
    """
    return get_recommendations(
        conditions=ctx.conditions or [],
        symptoms=ctx.symptoms or [],
        age=ctx.age,
        gender=ctx.gender,
        limit=20,
    )


@app.post("/api/health-map/position", response_model=PositionResponse)
def health_map_position(ctx: UserContext):
    """
    Where the user is on the map (active conditions/symptoms) and nearby risks (diseases, early signals).
    """
    return get_position(
        conditions=ctx.conditions or [],
        symptoms=ctx.symptoms or [],
    )


@app.post("/api/health-map/safest-path", response_model=SafestPathResponse)
def health_map_safest_path(ctx: UserContext):
    """
    Actionable steps to evacuate to safety (e.g. increase X, reduce Y) with evidence.
    """
    return get_safest_path(
        conditions=ctx.conditions or [],
        symptoms=ctx.symptoms or [],
        limit=10,
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
