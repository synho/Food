"""
Health Map Interrogation Agent — agentic assessment that evolves with each answer.

Given a UserContext, the agent:
  1. Scores assessment completeness (0-100)
  2. Queries the KG for data-driven insights (early signals, risk cascades, comorbidities)
  3. Generates the 2-3 most critical follow-up questions not yet answered
  4. Reports what it inferred vs what it needs to improve accuracy

The agent gets smarter as the user answers: answered_fields tracks what's been confirmed,
so questions are never repeated and assessment depth increases over time.
"""
from server.canonical import normalize_entity_name
from server.models.user_context import UserContext
from server.neo4j_client import run_query


# ── Completeness scoring ──────────────────────────────────────────────────────

_SCORE_WEIGHTS = {
    "age": 15,
    "gender": 5,
    "conditions": 25,
    "symptoms": 10,
    "medications": 10,
    "goals": 10,
    "lifestyle": 10,   # way_of_living or location
    "severity": 10,    # tracked via answered_fields: "severity:<condition>"
    "exercise": 5,     # tracked via answered_fields
}

def _completeness_score(ctx: UserContext, answered: set[str]) -> tuple[int, list[str]]:
    """Returns (score 0-100, list of missing field names)."""
    score = 0
    missing = []

    if ctx.age and ctx.age > 0:
        score += _SCORE_WEIGHTS["age"]
    else:
        missing.append("age")

    if ctx.gender:
        score += _SCORE_WEIGHTS["gender"]
    else:
        missing.append("gender")

    if ctx.conditions:
        score += _SCORE_WEIGHTS["conditions"]
    else:
        missing.append("conditions")

    if ctx.symptoms:
        score += _SCORE_WEIGHTS["symptoms"]
    else:
        missing.append("symptoms")

    if ctx.medications:
        score += _SCORE_WEIGHTS["medications"]
    elif "medications" in answered:
        score += _SCORE_WEIGHTS["medications"]  # Confirmed "none"
    else:
        missing.append("medications")

    if ctx.goals:
        score += _SCORE_WEIGHTS["goals"]
    else:
        missing.append("goals")

    if ctx.way_of_living or ctx.location:
        score += _SCORE_WEIGHTS["lifestyle"]
    elif "lifestyle" in answered:
        score += _SCORE_WEIGHTS["lifestyle"]
    else:
        missing.append("lifestyle")

    # Severity: check if answered for any condition
    if any(f.startswith("severity:") for f in answered):
        score += _SCORE_WEIGHTS["severity"]

    # Exercise
    if "exercise" in answered:
        score += _SCORE_WEIGHTS["exercise"]

    return min(score, 100), missing


# ── KG insight queries ────────────────────────────────────────────────────────

def _get_kg_insights(conditions: list[str], symptoms: list[str]) -> list[dict]:
    """Query KG for data-driven insights about the user's conditions."""
    insights = []

    if conditions:
        # Risk cascades: what diseases is the user at elevated risk for?
        rows = run_query("""
            MATCH (d:Disease)-[r:INCREASES_RISK_OF|CAUSES]->(d2:Disease)
            WHERE d.name IN $conditions AND r.source_id IS NOT NULL
            RETURN d.name AS from_cond, d2.name AS risk, count(r) AS evidence
            ORDER BY evidence DESC LIMIT 6
        """, {"conditions": conditions})
        for row in rows:
            insights.append({
                "type": "risk_cascade",
                "text": f"{row['from_cond']} increases risk of {row['risk']}",
                "entity": row["risk"],
                "evidence_count": row["evidence"],
                "severity": "high" if row["evidence"] >= 2 else "medium",
            })

        # Protective foods: strongest evidence for this condition
        rows = run_query("""
            MATCH (f)-[r:PREVENTS|TREATS|ALLEVIATES|REDUCES_RISK_OF]->(d:Disease)
            WHERE (f:Food OR f:Nutrient) AND d.name IN $conditions
              AND r.source_id IS NOT NULL
            RETURN f.name AS food, d.name AS condition,
                   max(coalesce(r.evidence_strength, 1)) AS strength,
                   count(r) AS evidence
            ORDER BY strength DESC, evidence DESC LIMIT 5
        """, {"conditions": conditions})
        for row in rows:
            insights.append({
                "type": "protective_food",
                "text": f"{row['food']} has {row['evidence']} evidence record(s) supporting {row['condition']}",
                "entity": row["food"],
                "evidence_count": row["evidence"],
                "severity": "low",
            })

        # Avoidance: foods to limit
        rows = run_query("""
            MATCH (f)-[r:AGGRAVATES|CAUSES]->(d:Disease)
            WHERE (f:Food OR f:Nutrient) AND d.name IN $conditions
              AND r.source_id IS NOT NULL
            RETURN f.name AS food, d.name AS condition, count(r) AS evidence
            ORDER BY evidence DESC LIMIT 3
        """, {"conditions": conditions})
        for row in rows:
            insights.append({
                "type": "avoidance",
                "text": f"Limit {row['food']} — linked to worsening {row['condition']}",
                "entity": row["food"],
                "evidence_count": row["evidence"],
                "severity": "medium",
            })

    if symptoms:
        # Symptoms → conditions they're early signals of
        rows = run_query("""
            MATCH (s:Symptom)-[r:EARLY_SIGNAL_OF]->(d:Disease)
            WHERE s.name IN $symptoms AND r.source_id IS NOT NULL
            RETURN s.name AS symptom, d.name AS disease, count(r) AS evidence
            ORDER BY evidence DESC LIMIT 5
        """, {"symptoms": symptoms})
        for row in rows:
            insights.append({
                "type": "early_signal",
                "text": f"{row['symptom']} is an early signal of {row['disease']}",
                "entity": row["disease"],
                "evidence_count": row["evidence"],
                "severity": "high" if row["evidence"] >= 2 else "medium",
            })

    return insights


# ── Likely undiagnosed conditions ─────────────────────────────────────────────

def _infer_likely_conditions(
    ctx: UserContext, insights: list[dict], answered: set[str]
) -> list[dict]:
    """Based on symptoms + KG early signals, infer conditions the user may have."""
    already = set(normalize_entity_name(c) for c in (ctx.conditions or []))
    inferred = []
    seen = set()

    for ins in insights:
        if ins["type"] != "early_signal":
            continue
        disease = ins["entity"]
        if disease in already or disease in seen:
            continue
        if f"confirmed:{disease}" in answered or f"denied:{disease}" in answered:
            continue
        seen.add(disease)
        inferred.append({
            "name": disease,
            "confidence": "possible" if ins["evidence_count"] == 1 else "likely",
            "reason": ins["text"],
        })

    # Age-based inferences
    age = ctx.age or 0
    if age >= 50 and "Osteoporosis" not in already and "confirmed:Osteoporosis" not in answered:
        inferred.append({
            "name": "Osteoporosis",
            "confidence": "age-related risk",
            "reason": "Risk of bone density loss increases significantly after 50",
        })
    if age >= 60 and "Sarcopenia" not in already and "confirmed:Sarcopenia" not in answered:
        inferred.append({
            "name": "Sarcopenia",
            "confidence": "age-related risk",
            "reason": "Muscle mass loss (sarcopenia) commonly begins around 60",
        })

    # Landmine age/condition combos
    cond_set = {normalize_entity_name(c).lower() for c in (ctx.conditions or [])}
    if (age >= 65 or "type 2 diabetes" in cond_set) and \
            "Alzheimer's disease" not in already and "confirmed:Alzheimer's disease" not in answered:
        inferred.append({
            "name": "Alzheimer's disease",
            "confidence": "landmine risk",
            "reason": (
                "Type 2 diabetes doubles Alzheimer's risk; age 65+ significantly elevates it"
                if "type 2 diabetes" in cond_set
                else "Age 65+ significantly elevates Alzheimer's risk"
            ),
        })
    if ("hypertension" in cond_set or "cardiovascular disease" in cond_set) and \
            "Stroke" not in already and "confirmed:Stroke" not in answered:
        inferred.append({
            "name": "Stroke",
            "confidence": "landmine risk",
            "reason": "Hypertension and cardiovascular disease are the leading modifiable stroke risk factors",
        })

    return inferred[:4]


# ── Critical question generation ─────────────────────────────────────────────

def _generate_questions(
    ctx: UserContext,
    missing: list[str],
    insights: list[dict],
    inferred: list[dict],
    answered: set[str],
) -> list[dict]:
    """Generate the 2-3 most impactful unanswered questions."""
    questions = []

    # 1. Confirm inferred conditions (highest priority — diagnosis shapes everything)
    for cond in inferred[:2]:
        if f"confirmed:{cond['name']}" in answered or f"denied:{cond['name']}" in answered:
            continue
        questions.append({
            "id": f"confirm_condition:{cond['name']}",
            "field": "conditions",
            "priority": 1,
            "question": f"Has a doctor ever mentioned {cond['name']} to you?",
            "context": cond["reason"],
            "type": "confirm",
            "value": cond["name"],
            "confidence": cond["confidence"],
        })

    # 1b. Landmine-priority questions: when a landmine disease has elevated risk, surface it first
    try:
        from server.services.landmine_detector import get_landmines, LANDMINE_PROFILES
        landmine_result = get_landmines(ctx)
        for lm in landmine_result.get("landmines", []):
            if lm["risk_level"] in ("high", "medium") and lm["risk_factors_present"]:
                lm_id = f"landmine_risk:{lm['name']}"
                if lm_id not in answered:
                    top_rf = lm["risk_factors_present"][0]
                    top_sign = lm["early_warning_signs"][0] if lm["early_warning_signs"] else "early symptoms"
                    questions.append({
                        "id": lm_id,
                        "field": "symptoms",
                        "priority": 1,
                        "question": (
                            f"You have {top_rf} — this significantly raises your risk of "
                            f"{lm['name']} ({lm['korean']}). Do you monitor for {top_sign}?"
                        ),
                        "context": lm["why_critical"],
                        "type": "text",
                        "hint": f"Any signs of {top_sign}, or 'not noticed'",
                    })
                    break  # Only surface highest-priority landmine per call
    except Exception:
        pass  # Landmine enrichment is best-effort

    # 2. Medications for serious conditions
    serious = {"Type 2 diabetes", "Hypertension", "Cardiovascular disease",
               "Osteoporosis", "Sarcopenia", "Prediabetes",
               "Alzheimer's disease", "Stroke", "Chronic kidney disease",
               "Major depressive disorder", "Pancreatic cancer"}
    has_serious = any(c in serious for c in (ctx.conditions or []))
    if has_serious and not ctx.medications and "medications" not in answered:
        conditions_str = ", ".join(c for c in (ctx.conditions or []) if c in serious)
        questions.append({
            "id": "medications_for_condition",
            "field": "medications",
            "priority": 1,
            "question": f"Are you taking any medications or supplements for {conditions_str}?",
            "context": "Medications can interact with foods — knowing them helps us refine guidance.",
            "type": "text",
            "hint": "e.g. Metformin, Aspirin, or 'none'",
        })

    # 3. KG-driven: ask about highest-risk cascade condition
    cascade_risks = [i for i in insights if i["type"] == "risk_cascade"]
    if cascade_risks and "risk_awareness" not in answered:
        top_risk = cascade_risks[0]
        questions.append({
            "id": f"risk_awareness:{top_risk['entity']}",
            "field": "symptoms",
            "priority": 2,
            "question": f"Do you notice any symptoms of {top_risk['entity']}? "
                        f"(e.g. chest pain, shortness of breath, fatigue)",
            "context": top_risk["text"],
            "type": "text",
            "hint": "Any symptoms, or 'none noticed'",
        })

    # 4. Severity / management level for primary condition
    if ctx.conditions and not any(f"severity:{ctx.conditions[0]}" in answered for _ in [1]):
        cond = ctx.conditions[0]
        questions.append({
            "id": f"severity:{cond}",
            "field": "way_of_living",
            "priority": 2,
            "question": f"How well-managed is your {cond} right now?",
            "context": "This helps us prioritize which foods matter most.",
            "type": "select",
            "options": ["Well-controlled", "Somewhat managed", "Difficult to control", "Recently diagnosed"],
        })

    # 5. Missing age
    if "age" in missing:
        questions.append({
            "id": "age",
            "field": "age",
            "priority": 2,
            "question": "How old are you?",
            "context": "Age significantly shapes nutritional needs and risk profiles.",
            "type": "number",
            "hint": "e.g. 48",
        })

    # 6. Exercise / lifestyle
    if "lifestyle" in missing and "exercise" not in answered:
        questions.append({
            "id": "exercise",
            "field": "way_of_living",
            "priority": 3,
            "question": "How physically active are you on a typical week?",
            "context": "Physical activity level affects how diet recommendations are weighted.",
            "type": "select",
            "options": ["Sedentary (mostly sitting)", "Light (walking, easy activities)",
                        "Moderate (30+ min exercise most days)", "Very active (daily intense exercise)"],
        })

    # 7. Goals if missing
    if "goals" in missing and "goals" not in answered:
        questions.append({
            "id": "goals",
            "field": "goals",
            "priority": 3,
            "question": "What is your primary health goal right now?",
            "context": "Goals help us prioritize which recommendations to surface first.",
            "type": "select",
            "options": ["Manage a specific condition", "Lose weight", "Improve energy",
                        "Healthy aging / longevity", "Better sleep", "Reduce inflammation"],
        })

    # Sort by priority, deduplicate by id
    seen_ids = set()
    unique = []
    for q in sorted(questions, key=lambda x: x["priority"]):
        if q["id"] not in seen_ids and q["id"] not in answered:
            seen_ids.add(q["id"])
            unique.append(q)

    return unique[:3]  # Max 3 at a time


# ── Self-improvement delta ────────────────────────────────────────────────────

def _improvement_delta(score: int, answered: set[str]) -> str:
    """Return a short message about what answering the questions would gain."""
    gains = 100 - score
    if gains <= 0:
        return "Assessment is comprehensive. Recommendations are fully personalized."
    if answered:
        return f"Assessment {score}% complete. Answer the questions below to improve accuracy."
    return f"Assessment {score}% complete. A few answers below will sharpen your guidance significantly."


# ── Main entry point ──────────────────────────────────────────────────────────

def interrogate(ctx: UserContext, answered_fields: list[str] | None = None) -> dict:
    """
    Agentic health map interrogation.

    Args:
        ctx: current UserContext
        answered_fields: list of question IDs already answered by the user
                         (prevents re-asking; format: "confirm_condition:X", "age", etc.)

    Returns dict with:
        completeness_score: int 0-100
        missing_fields: list[str]
        kg_insights: list[dict]
        inferred_conditions: list[dict]
        critical_questions: list[dict]  — max 3, sorted by priority
        delta_message: str
    """
    answered = set(answered_fields or [])

    cond_canonical = [normalize_entity_name(c) for c in (ctx.conditions or []) if c]
    sym_canonical = [normalize_entity_name(s) for s in (ctx.symptoms or []) if s]

    score, missing = _completeness_score(ctx, answered)
    insights = _get_kg_insights(cond_canonical, sym_canonical)
    inferred = _infer_likely_conditions(ctx, insights, answered)
    questions = _generate_questions(ctx, missing, insights, inferred, answered)
    delta = _improvement_delta(score, answered)

    return {
        "completeness_score": score,
        "missing_fields": missing,
        "kg_insights": insights[:8],
        "inferred_conditions": inferred,
        "critical_questions": questions,
        "delta_message": delta,
    }
