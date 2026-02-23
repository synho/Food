"""
Extract structured UserContext from free-form self-introduction text.
Two passes:
  1. Exact extraction — regex / keyword matching for precise values.
  2. Fuzzy inference — decade phrases, health topic keywords, pronouns.
Returns (UserContext, inferred_fields, follow_up_questions) so the caller
can tell the user what was guessed and ask for confirmation.
"""
import re
from server.models.user_context import UserContext
from server.canonical import CANONICAL_ENTITY_NAMES, normalize_entity_name

# ---------------------------------------------------------------------------
# Age — exact
# ---------------------------------------------------------------------------
AGE_PATTERNS = [
    r"\b(?:i'?m|i am|age|turned|just turned)\s+(\d{1,3})\b",
    r"\b(\d{1,3})\s*(?:years?\s*old|y\.?o\.?|years? of age)\b",
    r"\b(\d{1,3})\s*[-–]\s*year[- ]old\b",
    r"(?:저는|나는)\s*(\d{1,3})\s*살",
    r"(\d{1,3})\s*살",
    r"(\d{1,3})\s*세\b",
    r"나이\s*(\d{1,3})",
    r"만\s*(\d{1,3})\s*(?:세|살)?",
]

# Age — fuzzy decade phrases  →  (pattern, base_age_fn)
# "early 50s" → 52, "mid 40s" → 45, "late 30s" → 37, "in my 60s" → 63
_DECADE_FUZZY = [
    (r"\b(?:in my\s+)?early\s+(\d0)s\b",    lambda d: d + 2),
    (r"\b(?:in my\s+)?mid(?:dle)?\s*[-–]?\s*(\d0)s\b", lambda d: d + 5),
    (r"\b(?:in my\s+)?late\s+(\d0)s\b",     lambda d: d + 7),
    (r"\bin my\s+(\d0)s\b",                  lambda d: d + 4),
    (r"\b(\d0)(?:s|-something)\b",           lambda d: d + 5),
    (r"\baround\s+(\d{2,3})\b",              lambda d: d),
    (r"\babout\s+(\d{2,3})\b",               lambda d: d),
    (r"\balmost\s+(\d{2,3})\b",              lambda d: d - 1),
    # Korean: "50대 초반" → 52, "40대 중반" → 45, "30대 후반" → 37
    (r"(\d0)대\s*초반",  lambda d: d + 2),
    (r"(\d0)대\s*중반",  lambda d: d + 5),
    (r"(\d0)대\s*후반",  lambda d: d + 7),
    (r"(\d0)대",         lambda d: d + 4),
]

# ---------------------------------------------------------------------------
# Gender — exact
# ---------------------------------------------------------------------------
GENDER_MAP = {
    "female": "female", "woman": "female", "f": "female",
    "male": "male", "man": "male", "m": "male",
    "non-binary": "non-binary", "nonbinary": "non-binary", "nb": "non-binary",
    "여성": "female", "여자": "female",
    "남성": "male",  "남자": "male",
}

# Gender — fuzzy pronoun inference
_GENDER_PRONOUN = [
    (r"\b(she|her)\b",   "female"),
    (r"\b(he|him|his)\b", "male"),
]

# ---------------------------------------------------------------------------
# Conditions — exact keyword matching
# ---------------------------------------------------------------------------
CONDITION_KEYS = {
    "type 2 diabetes", "t2dm", "type 2 diabetes mellitus", "prediabetes",
    "pre diabetes", "pre-diabetes", "pre diabetic", "pre diabetics",
    "hypertension", "high blood pressure", "cardiovascular disease", "cvds",
    "sarcopenia", "osteoporosis", "mediterranean diet",
}
CONDITION_KO = {
    "전당뇨": "Prediabetes", "당뇨": "Type 2 diabetes", "제2형 당뇨": "Type 2 diabetes",
    "고혈압": "Hypertension", "골다공증": "Osteoporosis", "근감소증": "Sarcopenia",
}

# Conditions — fuzzy health topic keywords  →  canonical condition
_CONDITION_FUZZY: list[tuple[str, str]] = [
    # Blood sugar / diabetes
    (r"\b(blood sugar|glucose|glycem|insulin resist|a1c|hba1c|diabetic)\b", "Type 2 diabetes"),
    # Cardiovascular
    (r"\b(heart|cardiac|cholesterol|ldl|hdl|triglyceride|atheroscler|artery|arteries)\b", "Cardiovascular disease"),
    # Bone health
    (r"\b(bone density|weak bones?|fragile bones?|fracture risk|calcium deficiency)\b", "Osteoporosis"),
    # Muscle loss
    (r"\b(muscle loss|muscle weakness|losing muscle|weak muscles?|muscle wasting)\b", "Sarcopenia"),
    # Blood pressure (without "high" already caught)
    (r"\b(blood pressure|hypertensive|bp reading)\b", "Hypertension"),
    # Korean fuzzy
    (r"혈당", "Type 2 diabetes"),
    (r"심장|콜레스테롤", "Cardiovascular disease"),
    (r"뼈.*약|약한.*뼈", "Osteoporosis"),
    (r"근력.*약|근육.*감소", "Sarcopenia"),
]

# ---------------------------------------------------------------------------
# Medications, goals, symptoms — exact
# ---------------------------------------------------------------------------
MEDICATION_KEYS = {"metformin", "mounjaro", "maunzaro", "tirzepatide", "aspirin"}
MEDICATION_KO = {"메트포민": "Metformin", "몬자로": "Mounjaro", "아스피린": "Aspirin"}

GOAL_KEYS = {"longevity", "weight_management", "weight management", "hypertension_management"}
GOAL_KO = {"혈당 관리": "weight_management", "체중 관리": "weight_management", "장수": "longevity"}

# Goals — fuzzy
_GOAL_FUZZY: list[tuple[str, str]] = [
    (r"\b(lose weight|weight loss|lose some weight|slim|diet)\b", "weight_management"),
    (r"\b(live longer|longevity|healthy aging|age well)\b", "longevity"),
    (r"\b(lower.*blood pressure|manage.*pressure)\b", "hypertension_management"),
    (r"체중.*감량|살.*빼|다이어트", "weight_management"),
]

SYMPTOM_PHRASES = [
    "shoulder pain", "joint pain", "back pain", "fatigue", "bloating",
    "headache", "headaches", "insomnia", "anxiety", "stress", "inflammation",
    "brain fog", "memory", "dizziness",
]
SYMPTOM_KO = {
    "어깨 통증": "Shoulder pain", "관절 통증": "Joint pain", "요통": "Back pain",
    "피로": "Fatigue", "두통": "Headache", "불면증": "Insomnia", "스트레스": "Stress",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_age(text: str) -> tuple[int | None, bool]:
    """Returns (age, is_fuzzy). Exact match first, then fuzzy decade phrases."""
    tl = text.lower()
    for pat in AGE_PATTERNS:
        m = re.search(pat, tl, re.IGNORECASE | re.UNICODE)
        if m:
            n = int(m.group(1))
            if 1 <= n <= 120:
                return n, False
    # Fallback exact: "45 years"
    m = re.search(r"\b(\d{2,3})\s*years?\b", tl)
    if m:
        n = int(m.group(1))
        if 10 <= n <= 120:
            return n, False
    # Fuzzy decade phrases
    for pat, fn in _DECADE_FUZZY:
        m = re.search(pat, tl, re.IGNORECASE | re.UNICODE)
        if m:
            decade = int(m.group(1))
            age = fn(decade)
            if 10 <= age <= 120:
                return age, True
    return None, False


def _extract_gender(text: str) -> tuple[str | None, bool]:
    """Returns (gender, is_fuzzy)."""
    tl = text.lower()
    for variant, canonical in GENDER_MAP.items():
        if variant.isascii():
            if re.search(r"\b" + re.escape(variant) + r"\b", tl):
                return canonical, False
        elif variant in text:
            return canonical, False
    # Fuzzy: pronouns (less reliable — mark as inferred)
    for pat, gender in _GENDER_PRONOUN:
        if re.search(pat, tl, re.IGNORECASE):
            return gender, True
    return None, False


def _find_phrases_in_text(text: str, phrases: set[str] | list[str]) -> list[str]:
    tl = text.lower()
    found: list[str] = []
    for phrase in phrases:
        if re.search(r"\b" + re.escape(phrase) + r"\b", tl):
            canonical = CANONICAL_ENTITY_NAMES.get(phrase) or phrase.strip()
            if canonical and canonical not in found:
                found.append(canonical)
    return found


def _find_ko_phrases(text: str, ko_map: dict[str, str]) -> list[str]:
    found: list[str] = []
    for ko, canonical in ko_map.items():
        if ko in text and canonical not in found:
            found.append(canonical)
    return found


def _find_symptom_phrases(text: str) -> list[str]:
    tl = text.lower()
    found: list[str] = []
    for phrase in SYMPTOM_PHRASES:
        if re.search(r"\b" + re.escape(phrase) + r"\b", tl):
            cap = phrase.title()
            if cap not in found:
                found.append(cap)
    for ko, en in SYMPTOM_KO.items():
        if ko in text and en not in found:
            found.append(en)
    return found


def _find_conditions_fuzzy(text: str, already: list[str]) -> list[str]:
    """Health topic keywords that imply a condition not already found."""
    tl = text.lower()
    found: list[str] = []
    for pat, canonical in _CONDITION_FUZZY:
        if re.search(pat, tl, re.IGNORECASE | re.UNICODE):
            if canonical not in already and canonical not in found:
                found.append(canonical)
    return found


def _find_goals_fuzzy(text: str, already: list[str]) -> list[str]:
    tl = text.lower()
    found: list[str] = []
    for pat, canonical in _GOAL_FUZZY:
        if re.search(pat, tl, re.IGNORECASE | re.UNICODE):
            if canonical not in already and canonical not in found:
                found.append(canonical)
    return found


def _build_follow_up(
    age: int | None, age_fuzzy: bool,
    gender: str | None, gender_fuzzy: bool,
    conditions: list[str], conditions_inferred: list[str],
) -> list[dict]:
    """Build targeted follow-up questions for missing or inferred fields."""
    questions: list[dict] = []

    if age is not None and age_fuzzy:
        questions.append({
            "field": "age",
            "question": f"We guessed you're around {age} — is that right?",
            "type": "confirm",
            "value": str(age),
        })
    elif age is None:
        questions.append({
            "field": "age",
            "question": "How old are you? (helps us tailor recommendations)",
            "type": "number",
            "hint": "e.g. 45",
        })

    for cond in conditions_inferred:
        questions.append({
            "field": "conditions",
            "question": f"We inferred you may have {cond} — is that correct?",
            "type": "confirm",
            "value": cond,
        })

    if not conditions and not conditions_inferred:
        questions.append({
            "field": "conditions",
            "question": "Is there a health condition you're managing or watching?",
            "type": "text",
            "hint": "e.g. Type 2 diabetes, Hypertension",
        })

    if gender is None:
        questions.append({
            "field": "gender",
            "question": "What's your biological sex? (optional — improves nutritional advice)",
            "type": "select",
            "options": ["female", "male", "prefer not to say"],
        })

    return questions


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def context_from_text(text: str) -> tuple[UserContext, list[str], list[dict]]:
    """
    Parse free-form self-intro text into structured UserContext.
    Returns (UserContext, inferred_fields, follow_up_questions).

    inferred_fields: list of field names whose values were guessed (not exact).
    follow_up_questions: targeted questions to confirm/correct guessed values
                         or fill in missing key fields.
    """
    if not text or not text.strip():
        return UserContext(), [], []

    t = text.strip()
    inferred: list[str] = []

    # Age
    age, age_fuzzy = _extract_age(t)
    if age_fuzzy:
        inferred.append("age")

    # Gender
    gender, gender_fuzzy = _extract_gender(t)
    if gender_fuzzy:
        inferred.append("gender")

    # Conditions — exact first
    conditions: list[str] = _find_phrases_in_text(t, CONDITION_KEYS)
    conditions += _find_ko_phrases(t, CONDITION_KO)
    conditions = list(dict.fromkeys(conditions))

    # Conditions — fuzzy inference
    conditions_inferred = _find_conditions_fuzzy(t, conditions)
    if conditions_inferred:
        inferred.append("conditions")
    all_conditions = list(dict.fromkeys(conditions + conditions_inferred)) or None

    # Medications
    medications = _find_phrases_in_text(t, MEDICATION_KEYS)
    medications += _find_ko_phrases(t, MEDICATION_KO)
    medications = list(dict.fromkeys(medications)) or None

    # Goals — exact + fuzzy
    goals: list[str] = _find_phrases_in_text(t, GOAL_KEYS)
    goals += _find_ko_phrases(t, GOAL_KO)
    goals = list(dict.fromkeys(goals))
    goals_fuzzy = _find_goals_fuzzy(t, goals)
    if goals_fuzzy:
        inferred.append("goals")
    all_goals = list(dict.fromkeys(goals + goals_fuzzy)) or None

    # Symptoms
    symptoms = _find_symptom_phrases(t) or None

    ctx = UserContext(
        age=age,
        gender=gender or None,
        conditions=all_conditions,
        symptoms=symptoms,
        medications=medications,
        goals=all_goals,
    )

    follow_up = _build_follow_up(age, age_fuzzy, gender, gender_fuzzy, conditions, conditions_inferred)

    return ctx, inferred, follow_up
