"""
Health Map Interrogation Agent — agentic assessment that evolves with each answer.

Given a UserContext, the agent:
  1. Scores assessment completeness (0-100)
  2. Queries the KG for data-driven insights (early signals, risk cascades, comorbidities)
  3. Generates the 2-3 most critical follow-up questions not yet answered
  4. Reports what it inferred vs what it needs to improve accuracy
  5. Runs a per-disease "landmine symptom check" — conversational questions about
     early warning signs for any landmine disease that has elevated risk

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


# ── Landmine symptom checks ───────────────────────────────────────────────────
# Per-disease: 3 warm, conversational questions about early warning signs.
# Each check has:
#   id            — unique question ID (used in answered_fields)
#   question      — friendly, non-clinical phrasing
#   context       — why we're asking (shown as subtext)
#   symptom_value — value added to ctx.symptoms if user says "yes"
#   options       — "yes_label" and "no_label" for the two response buttons

LANDMINE_SYMPTOM_CHECKS: dict[str, list[dict]] = {
    "Alzheimer's disease": [
        {
            "id": "lm_check:alzheimers:memory",
            "question": "Have you noticed yourself forgetting things more than usual lately — "
                        "like repeating questions, losing track of dates, or struggling to find words?",
            "context": "Occasional forgetfulness is normal, but a noticeable pattern can be an early signal worth tracking.",
            "symptom_value": "Memory loss",
            "yes_label": "Yes, I've noticed this",
            "no_label": "Not really",
        },
        {
            "id": "lm_check:alzheimers:navigation",
            "question": "Have you ever felt confused about where you are, or had trouble following "
                        "a familiar route or routine?",
            "context": "Spatial disorientation in familiar settings is one of the earliest signs to watch for.",
            "symptom_value": "Confusion",
            "yes_label": "Yes, occasionally",
            "no_label": "No, not at all",
        },
        {
            "id": "lm_check:alzheimers:fog",
            "question": "Do you often feel mentally foggy — trouble concentrating, slow thinking, "
                        "or feeling like your mind isn't as sharp as it used to be?",
            "context": "Brain fog can reflect metabolic effects on cognition — especially relevant with Type 2 diabetes.",
            "symptom_value": "Brain fog",
            "yes_label": "Yes, fairly often",
            "no_label": "Not particularly",
        },
    ],
    "Stroke": [
        {
            "id": "lm_check:stroke:tia",
            "question": "Have you ever had a sudden but brief episode of weakness, numbness, "
                        "slurred speech, or vision changes that passed within minutes or hours?",
            "context": "These 'mini-strokes' (TIAs) are the most important warning sign — each one is a call to act.",
            "symptom_value": "TIA (mini-stroke)",
            "yes_label": "Yes, something like that",
            "no_label": "No, never",
        },
        {
            "id": "lm_check:stroke:headache",
            "question": "Do you get severe or unusual headaches — especially ones that come on "
                        "suddenly and feel different from your normal headaches?",
            "context": "Sudden severe headache (sometimes called 'thunderclap') can signal vascular pressure changes.",
            "symptom_value": "Sudden severe headache",
            "yes_label": "Yes, I do",
            "no_label": "No",
        },
        {
            "id": "lm_check:stroke:bp_check",
            "question": "Do you regularly check your blood pressure, and if so — has it been "
                        "consistently above 140/90 recently?",
            "context": "Uncontrolled hypertension is the single biggest stroke risk factor — and it's silent.",
            "symptom_value": "Uncontrolled blood pressure",
            "yes_label": "Yes, it's been high",
            "no_label": "No / I don't check",
        },
    ],
    "Pancreatic cancer": [
        {
            "id": "lm_check:pancreatic:abdominal",
            "question": "Have you had persistent pain in your upper abdomen or back that doesn't "
                        "seem to have a clear cause?",
            "context": "Dull, persistent upper abdominal or back pain is one of the few early signs of pancreatic disease.",
            "symptom_value": "Upper abdominal pain",
            "yes_label": "Yes, I have",
            "no_label": "No",
        },
        {
            "id": "lm_check:pancreatic:weight",
            "question": "Have you lost weight recently without trying, or noticed a significant "
                        "decrease in appetite?",
            "context": "Unexplained weight loss is the most common presenting symptom — often dismissed as stress.",
            "symptom_value": "Unexplained weight loss",
            "yes_label": "Yes, some weight loss",
            "no_label": "No",
        },
        {
            "id": "lm_check:pancreatic:newdiabetes",
            "question": "Has your blood sugar recently become harder to control, or were you newly "
                        "diagnosed with diabetes in the past year or two?",
            "context": "New-onset diabetes in someone over 50 can sometimes be an early pancreatic signal.",
            "symptom_value": "New-onset diabetes (sudden)",
            "yes_label": "Yes, recently changed",
            "no_label": "No change",
        },
    ],
    "Chronic kidney disease": [
        {
            "id": "lm_check:ckd:fatigue",
            "question": "Do you feel unusually tired or fatigued — even after a full night's sleep — "
                        "that you can't quite explain?",
            "context": "Persistent fatigue is often the first symptom of reduced kidney function, as toxins accumulate.",
            "symptom_value": "Fatigue",
            "yes_label": "Yes, often",
            "no_label": "Not really",
        },
        {
            "id": "lm_check:ckd:swelling",
            "question": "Have you noticed swelling in your ankles, feet, or legs — especially "
                        "toward the end of the day?",
            "context": "Fluid retention from impaired kidney filtration often shows up as ankle and foot swelling first.",
            "symptom_value": "Swollen ankles/feet",
            "yes_label": "Yes, I've noticed",
            "no_label": "No",
        },
        {
            "id": "lm_check:ckd:urine",
            "question": "Have you noticed any changes in your urine — foamy or bubbly appearance, "
                        "changes in colour, or going more or less often than usual?",
            "context": "Foamy urine can indicate protein loss — one of the earliest measurable signs of kidney stress.",
            "symptom_value": "Foamy urine",
            "yes_label": "Yes, I've noticed changes",
            "no_label": "No changes",
        },
    ],
    "Cardiovascular disease": [
        {
            "id": "lm_check:cvd:exertion",
            "question": "Do you get short of breath, chest tightness, or unusual fatigue when "
                        "doing things that didn't used to bother you — like climbing stairs or walking briskly?",
            "context": "Exertional symptoms are often the first sign the heart is working harder than it should.",
            "symptom_value": "Shortness of breath on exertion",
            "yes_label": "Yes, I've noticed",
            "no_label": "No",
        },
        {
            "id": "lm_check:cvd:palpitations",
            "question": "Do you ever feel your heart racing, fluttering, or skipping beats — "
                        "even when you're resting?",
            "context": "Palpitations at rest can signal arrhythmia, which is one of the strongest stroke and cardiac risk factors.",
            "symptom_value": "Palpitations",
            "yes_label": "Yes, sometimes",
            "no_label": "No",
        },
        {
            "id": "lm_check:cvd:leg_pain",
            "question": "Do your legs ache or cramp when you walk — and does the pain go away "
                        "when you stop and rest?",
            "context": "Calf pain that relieves with rest (claudication) can signal peripheral artery disease — a CVD warning sign.",
            "symptom_value": "Leg pain when walking (PAD)",
            "yes_label": "Yes, this happens",
            "no_label": "No",
        },
    ],
    "Major depressive disorder": [
        {
            "id": "lm_check:depression:mood",
            "question": "Over the past few weeks, have you often felt persistently sad, empty, "
                        "or just unable to enjoy things you usually like?",
            "context": "A persistent low mood lasting more than two weeks — especially with loss of interest — is worth taking seriously.",
            "symptom_value": "Persistent low mood",
            "yes_label": "Yes, fairly often",
            "no_label": "Not really",
        },
        {
            "id": "lm_check:depression:sleep",
            "question": "Has your sleep changed significantly — either sleeping much more than "
                        "usual, or struggling to sleep even when tired?",
            "context": "Sleep disruption is both a symptom and a driver of depression — it creates a reinforcing cycle.",
            "symptom_value": "Sleep disturbance",
            "yes_label": "Yes, my sleep has changed",
            "no_label": "Sleep is okay",
        },
        {
            "id": "lm_check:depression:withdrawal",
            "question": "Have you been pulling back from friends, family, or activities you used "
                        "to enjoy — and finding it hard to motivate yourself?",
            "context": "Social withdrawal and loss of motivation are core early symptoms that often precede a full depressive episode.",
            "symptom_value": "Social withdrawal",
            "yes_label": "Yes, I've been withdrawing",
            "no_label": "No, I'm still engaged",
        },
    ],
}


def _get_landmine_checks(ctx: UserContext, answered: set[str]) -> list[dict]:
    """
    Build landmine symptom check questions for diseases with elevated risk.

    Returns a list of check dicts (at most 2 at a time — highest-risk disease first,
    then the next unanswered question within that disease).
    Each check has a `landmine_check: True` flag so the frontend can style it distinctly.
    """
    try:
        from server.services.landmine_detector import get_landmines
        result = get_landmines(ctx)
    except Exception:
        return []

    checks = []
    _order = {"high": 0, "medium": 1, "low": 2, "none": 3}
    sorted_lm = sorted(result.get("landmines", []), key=lambda l: _order[l["risk_level"]])

    for lm in sorted_lm:
        if lm["risk_level"] not in ("high", "medium"):
            continue
        disease_checks = LANDMINE_SYMPTOM_CHECKS.get(lm["name"], [])
        for chk in disease_checks:
            chk_id = chk["id"]
            answered_yes = f"{chk_id}:yes" in answered
            answered_no  = f"{chk_id}:no"  in answered
            if answered_yes or answered_no:
                continue
            checks.append({
                **chk,
                "disease_name": lm["name"],
                "disease_korean": lm["korean"],
                "risk_level": lm["risk_level"],
                "why_critical": lm["why_critical"],
                "field": "symptoms",
                "type": "landmine_symptom",
                "landmine_check": True,
                "priority": 0,  # Always highest priority
            })
            # Only surface the first unanswered question per disease
            break

        if len(checks) >= 2:
            break  # Surface at most 2 landmine checks per call

    return checks


# ── Critical question generation ─────────────────────────────────────────────

def _generate_questions(
    ctx: UserContext,
    missing: list[str],
    insights: list[dict],
    inferred: list[dict],
    answered: set[str],
) -> list[dict]:
    """Generate the most impactful unanswered questions (up to 3)."""
    questions: list[dict] = []

    # 0. Landmine symptom checks — always highest priority for elevated-risk diseases
    landmine_checks = _get_landmine_checks(ctx, answered)
    questions.extend(landmine_checks)

    # 1. Confirm inferred conditions (diagnosis shapes everything)
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

    # Sort by priority (landmine checks have priority=0), deduplicate by id
    seen_ids: set[str] = set()
    unique: list[dict] = []
    for q in sorted(questions, key=lambda x: x.get("priority", 2)):
        qid = q["id"]
        if qid not in seen_ids and qid not in answered:
            seen_ids.add(qid)
            unique.append(q)

    return unique[:3]  # Max 3 at a time


# ── Self-improvement delta ────────────────────────────────────────────────────

def _improvement_delta(score: int, answered: set[str], has_landmine_checks: bool) -> str:
    """Return a short message about what answering the questions would gain."""
    gains = 100 - score
    if gains <= 0:
        return "Assessment is comprehensive. Recommendations are fully personalized."
    if has_landmine_checks:
        return (
            f"Assessment {score}% complete. "
            "These quick questions help detect early warning signs of serious conditions — "
            "your honest answers will update your map position."
        )
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
                         (prevents re-asking; format: "confirm_condition:X", "age",
                         "lm_check:alzheimers:memory:yes", "lm_check:alzheimers:memory:no", etc.)

    Returns dict with:
        completeness_score: int 0-100
        missing_fields: list[str]
        kg_insights: list[dict]
        inferred_conditions: list[dict]
        critical_questions: list[dict]  — max 3, sorted by priority (landmine checks first)
        delta_message: str
        landmine_checks_remaining: int  — how many unanswered landmine checks remain
    """
    answered = set(answered_fields or [])

    cond_canonical = [normalize_entity_name(c) for c in (ctx.conditions or []) if c]
    sym_canonical = [normalize_entity_name(s) for s in (ctx.symptoms or []) if s]

    score, missing = _completeness_score(ctx, answered)
    insights = _get_kg_insights(cond_canonical, sym_canonical)
    inferred = _infer_likely_conditions(ctx, insights, answered)
    questions = _generate_questions(ctx, missing, insights, inferred, answered)

    has_lm_checks = any(q.get("landmine_check") for q in questions)
    delta = _improvement_delta(score, answered, has_lm_checks)

    # Count remaining unanswered landmine checks (for progress indicator)
    remaining_checks = 0
    try:
        from server.services.landmine_detector import get_landmines
        result = get_landmines(ctx)
        for lm in result.get("landmines", []):
            if lm["risk_level"] not in ("high", "medium"):
                continue
            for chk in LANDMINE_SYMPTOM_CHECKS.get(lm["name"], []):
                chk_id = chk["id"]
                if f"{chk_id}:yes" not in answered and f"{chk_id}:no" not in answered:
                    remaining_checks += 1
    except Exception:
        pass

    return {
        "completeness_score": score,
        "missing_fields": missing,
        "kg_insights": insights[:8],
        "inferred_conditions": inferred,
        "critical_questions": questions,
        "delta_message": delta,
        "landmine_checks_remaining": remaining_checks,
    }
