"""
Landmine Disease Detector — identifies risk levels for 6 "landmine" diseases.

These diseases are uniquely dangerous because they are silent until too late,
irreversible once triggered, and life-altering. The detector uses:
  1. Hardcoded risk factor profiles (based on medical literature)
  2. KG enrichment: foods/nutrients that PREVENTS/TREATS/ALLEVIATES each disease
  3. UserContext matching to produce per-landmine risk scores

Risk levels:
  none   — 0 risk factors present (ghost on map)
  low    — 1 risk factor (amber, static)
  medium — 2 risk factors (orange, subtle pulse)
  high   — 3+ risk factors OR a direct trigger condition (red, pulse)
"""
from __future__ import annotations

from server.canonical import normalize_entity_name
from server.models.user_context import UserContext
from server.neo4j_client import run_query

# ── Landmine profiles ──────────────────────────────────────────────────────────

LANDMINE_PROFILES = [
    {
        "name": "Alzheimer's disease",
        "korean": "알츠하이머",
        "why_critical": "Erases identity and memory — no cure once started",
        "map_x": 720,
        "map_y": 62,
        "territory": "Longevity Coast",
        "risk_factors": [
            "Type 2 diabetes",
            "Hypertension",
            "Cardiovascular disease",
            "Obesity",
            "Sedentary lifestyle",
            "Age 65+",
            "Family history of dementia",
        ],
        "trigger_conditions": ["Dementia"],  # Already-diagnosed → force high
        "early_warning_signs": [
            "Memory loss",
            "Confusion",
            "Brain fog",
            "Difficulty word-finding",
            "Getting lost in familiar places",
        ],
        "escape_routes": [
            "Omega-3 (DHA/EPA) — neuroprotective",
            "Mediterranean diet — reduces risk by 30-40%",
            "Physical exercise — increases BDNF",
            "Leafy greens — folate for homocysteine control",
            "Blueberries — anthocyanins reduce amyloid",
        ],
    },
    {
        "name": "Stroke",
        "korean": "뇌졸중",
        "why_critical": "Sudden onset — permanent paralysis or cognitive loss in minutes",
        "map_x": 610,
        "map_y": 195,
        "territory": "Recovery Valley",
        "risk_factors": [
            "Hypertension",
            "Atrial fibrillation",
            "Cardiovascular disease",
            "Type 2 diabetes",
            "Smoking",
            "Obesity",
            "High cholesterol",
        ],
        "trigger_conditions": ["Atrial fibrillation"],  # AFib is direct trigger
        "early_warning_signs": [
            "Sudden facial drooping",
            "Arm weakness",
            "Slurred speech",
            "Sudden severe headache",
            "Transient vision loss",
            "TIA (mini-stroke)",
        ],
        "escape_routes": [
            "DASH diet — lowers blood pressure",
            "Omega-3 — anti-thrombotic",
            "Potassium-rich foods (bananas, sweet potato)",
            "Limit sodium below 2300mg/day",
            "Dark chocolate (flavanols) — vascular health",
        ],
    },
    {
        "name": "Pancreatic cancer",
        "korean": "췌장암",
        "why_critical": "Silent killer — near-zero survival if detected late",
        "map_x": 420,
        "map_y": 300,
        "territory": "Risk Territory",
        "risk_factors": [
            "Type 2 diabetes",
            "Chronic pancreatitis",
            "Smoking",
            "Obesity",
            "Family history of pancreatic cancer",
            "Age 60+",
        ],
        "trigger_conditions": ["Chronic pancreatitis"],
        "early_warning_signs": [
            "Upper abdominal pain",
            "Unexplained weight loss",
            "New-onset diabetes (sudden)",
            "Jaundice",
            "Back pain radiating to abdomen",
        ],
        "escape_routes": [
            "Cruciferous vegetables (broccoli, cauliflower) — anti-cancer",
            "Turmeric/curcumin — anti-inflammatory",
            "Avoid red and processed meat",
            "Limit alcohol",
            "High-fiber diet — reduces insulin resistance",
        ],
    },
    {
        "name": "Chronic kidney disease",
        "korean": "만성 신부전",
        "why_critical": "Silent progression to dialysis dependency — loss of independence",
        "map_x": 280,
        "map_y": 200,
        "territory": "Metabolic Crossroads",
        "risk_factors": [
            "Type 2 diabetes",
            "Hypertension",
            "Cardiovascular disease",
            "Obesity",
            "Family history of kidney disease",
            "Age 60+",
        ],
        "trigger_conditions": [],
        "early_warning_signs": [
            "Fatigue",
            "Swollen ankles/feet",
            "Foamy urine",
            "Decreased urine output",
            "Persistent back pain",
            "High creatinine",
        ],
        "escape_routes": [
            "Low-protein diet — slows progression",
            "Limit phosphorus (processed foods)",
            "Control blood pressure via DASH diet",
            "Omega-3 — anti-inflammatory for kidneys",
            "Avoid NSAIDs and nephrotoxic substances",
        ],
    },
    {
        "name": "Cardiovascular disease",
        "korean": "심혈관 질환",
        "why_critical": "Leading cause of sudden cardiac death — often no warning",
        "map_x": 530,
        "map_y": 340,
        "territory": "Cardiometabolic Ridge",
        "risk_factors": [
            "Hypertension",
            "Type 2 diabetes",
            "High cholesterol",
            "Obesity",
            "Smoking",
            "Sedentary lifestyle",
            "Family history of heart disease",
        ],
        "trigger_conditions": [],
        "early_warning_signs": [
            "Chest pain or pressure",
            "Shortness of breath on exertion",
            "Palpitations",
            "Leg pain when walking (PAD)",
            "Fatigue",
            "Swelling in legs",
        ],
        "escape_routes": [
            "Omega-3 — reduces triglycerides, anti-arrhythmic",
            "Mediterranean diet — 30% reduction in events",
            "Olive oil (extra virgin) — polyphenols",
            "Nuts (walnuts) — LDL reduction",
            "Oats/beta-glucan — cholesterol lowering",
        ],
    },
    {
        "name": "Major depressive disorder",
        "korean": "중증 우울증",
        "why_critical": "Destroys will to live and social connection — invisible but devastating",
        "map_x": 155,
        "map_y": 348,
        "territory": "Inflammatory Plains",
        "risk_factors": [
            "Chronic pain",
            "Cardiovascular disease",
            "Hypothyroidism",
            "Chronic inflammation",
            "Social isolation",
            "Sedentary lifestyle",
            "Vitamin D deficiency",
        ],
        "trigger_conditions": [],
        "early_warning_signs": [
            "Persistent low mood",
            "Loss of interest in activities",
            "Sleep disturbance",
            "Fatigue",
            "Difficulty concentrating",
            "Social withdrawal",
        ],
        "escape_routes": [
            "Omega-3 (EPA) — anti-inflammatory, mood stabilizing",
            "Vitamin D — reduces depressive symptoms",
            "Mediterranean diet — 30% lower depression risk",
            "Fermented foods — gut-brain axis",
            "Magnesium-rich foods — neurological function",
        ],
    },
]


# ── Age threshold helpers ─────────────────────────────────────────────────────

def _age_risk_factor(profile: dict, age: int | None) -> str | None:
    """Return age-based risk factor label if applicable."""
    if age is None:
        return None
    thresholds = {
        "Alzheimer's disease": ("Age 65+", 65),
        "Pancreatic cancer":   ("Age 60+", 60),
        "Chronic kidney disease": ("Age 60+", 60),
    }
    t = thresholds.get(profile["name"])
    if t and age >= t[1]:
        return t[0]
    return None


def _score_risk(profile: dict, ctx: UserContext) -> tuple[str, list[str], list[str]]:
    """
    Score risk level for one landmine given user context.

    Returns (risk_level, risk_factors_present, risk_factors_missing)
    """
    conditions_normalized = {normalize_entity_name(c).lower() for c in (ctx.conditions or [])}
    symptoms_normalized = {normalize_entity_name(s).lower() for s in (ctx.symptoms or [])}

    present: list[str] = []
    missing: list[str] = []

    for rf in profile["risk_factors"]:
        rf_key = rf.lower()
        # Check if risk factor matches a condition (direct or normalized)
        matched = (
            rf_key in conditions_normalized
            or normalize_entity_name(rf).lower() in conditions_normalized
            or any(rf_key in c for c in conditions_normalized)
        )
        # Age-based check
        if not matched and "age " in rf_key and ctx.age:
            age_threshold = None
            try:
                age_threshold = int("".join(filter(str.isdigit, rf)))
            except (ValueError, TypeError):
                pass
            if age_threshold and ctx.age >= age_threshold:
                matched = True
        if matched:
            present.append(rf)
        else:
            missing.append(rf)

    # Check trigger conditions (force high)
    is_triggered = any(
        normalize_entity_name(tc).lower() in conditions_normalized
        for tc in profile.get("trigger_conditions", [])
    )

    # Score
    count = len(present)
    if is_triggered or count >= 3:
        level = "high"
    elif count == 2:
        level = "medium"
    elif count == 1:
        level = "low"
    else:
        level = "none"

    return level, present, missing


# ── KG enrichment ─────────────────────────────────────────────────────────────

def _get_kg_evidence(disease_name: str) -> list[dict]:
    """Query Neo4j for food/nutrient nodes that PREVENTS/TREATS/ALLEVIATES/REDUCES_RISK_OF the disease.
    Uses case-insensitive name matching to catch variant capitalizations."""
    try:
        rows = run_query(
            """
            MATCH (f)-[r:PREVENTS|TREATS|ALLEVIATES|REDUCES_RISK_OF]->(d:Disease)
            WHERE toLower(d.name) = toLower($disease)
              AND (f:Food OR f:Nutrient OR f:LifestyleFactor)
              AND r.source_id IS NOT NULL
            RETURN f.name AS food, labels(f)[0] AS food_type, type(r) AS predicate,
                   r.source_id AS source_id, r.context AS context, r.journal AS journal,
                   r.pub_date AS pub_date
            ORDER BY r.source_id DESC
            LIMIT 8
            """,
            {"disease": disease_name},
        )
        return [
            {
                "food": row["food"],
                "food_type": row["food_type"],
                "predicate": row["predicate"],
                "source_id": row["source_id"],
                "context": row.get("context") or "",
                "journal": row.get("journal") or "",
                "pub_date": row.get("pub_date") or "",
            }
            for row in rows
            if row.get("food")
        ]
    except Exception:
        return []


# ── Main function ─────────────────────────────────────────────────────────────

def get_landmines(ctx: UserContext) -> dict:
    """
    Detect risk levels for all 6 landmine diseases.

    Returns dict with 'landmines' list — all 6 always returned, ordered by risk (high first).
    """
    results = []

    for profile in LANDMINE_PROFILES:
        risk_level, present, missing = _score_risk(profile, ctx)
        kg_evidence = _get_kg_evidence(profile["name"])

        results.append({
            "name": profile["name"],
            "korean": profile["korean"],
            "risk_level": risk_level,
            "risk_factors_present": present,
            "risk_factors_missing": missing,
            "early_warning_signs": profile["early_warning_signs"],
            "escape_routes": profile["escape_routes"],
            "kg_evidence": kg_evidence,
            "why_critical": profile["why_critical"],
            "map_x": profile["map_x"],
            "map_y": profile["map_y"],
            "territory": profile["territory"],
        })

    # Sort: high → medium → low → none
    _order = {"high": 0, "medium": 1, "low": 2, "none": 3}
    results.sort(key=lambda r: _order[r["risk_level"]])

    return {"landmines": results}
