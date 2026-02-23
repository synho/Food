"""
Suggest canonical / most similar terms for user input. Used for spelling correction and autocomplete.
Combines: canonical map (exact + substring) and KG node names (Disease, Symptom, Drug).
"""
from server.canonical import CANONICAL_ENTITY_NAMES, normalize_entity_name
from server.neo4j_client import run_query

LIMIT = 10


def _from_canonical(q: str) -> list[str]:
    """Exact match and all keys that contain q (or q contains key); return canonicals, deduped."""
    if not q or not q.strip():
        return []
    q = q.strip().lower()
    seen: set[str] = set()
    out: list[str] = []
    # Exact
    canonical = CANONICAL_ENTITY_NAMES.get(q)
    if canonical and canonical not in seen:
        seen.add(canonical)
        out.append(canonical)
    # Keys that contain q
    for key, canonical in CANONICAL_ENTITY_NAMES.items():
        if canonical in seen:
            continue
        if q in key or key in q:
            seen.add(canonical)
            out.append(canonical)
    return out[:LIMIT]


def _from_kg(label: str, q: str) -> list[str]:
    """Return node names from Neo4j where name contains q (case-insensitive)."""
    if not q or not q.strip():
        return []
    q = q.strip().lower()
    try:
        # Parameterized; CONTAINS is case-sensitive in some versions, so we use toLower
        query = f"""
        MATCH (n:{label})
        WHERE n.name IS NOT NULL AND toLower(toString(n.name)) CONTAINS $q
        RETURN DISTINCT n.name AS name
        LIMIT {LIMIT}
        """
        rows = run_query(query, {"q": q})
        return [r["name"] for r in rows if r.get("name")]
    except Exception:
        return []


# Goals: fixed list for suggestions (no KG label)
GOAL_OPTIONS = [
    "longevity",
    "weight_management",
    "weight management",
    "hypertension_management",
    "blood_sugar_management",
    "heart_health",
]


def _from_goals(q: str) -> list[str]:
    if not q or not q.strip():
        return []
    q = q.strip().lower()
    return [g for g in GOAL_OPTIONS if q in g.replace("_", " ")][:LIMIT]


def get_suggestions(q: str, field: str) -> list[str]:
    """
    Return suggested canonical/similar terms for the given query and field.
    field: conditions | symptoms | medications | goals
    """
    if not q or not isinstance(q, str):
        return []
    q = q.strip()
    if not q:
        return []
    q_lower = q.lower()
    seen: set[str] = set()
    out: list[str] = []

    # 1) From canonical map (covers typos and variants)
    for term in _from_canonical(q):
        if term not in seen:
            seen.add(term)
            out.append(term)

    # 2) From KG by field
    if field == "conditions":
        for name in _from_kg("Disease", q):
            n = (name or "").strip()
            if n and n not in seen:
                seen.add(n)
                out.append(n)
    elif field == "symptoms":
        for name in _from_kg("Symptom", q):
            n = (name or "").strip()
            if n and n not in seen:
                seen.add(n)
                out.append(n)
    elif field == "medications":
        for name in _from_kg("Drug", q):
            n = (name or "").strip()
            if n and n not in seen:
                seen.add(n)
                out.append(n)
    elif field == "goals":
        for g in _from_goals(q):
            if g not in seen:
                seen.add(g)
                out.append(g)

    return out[:LIMIT]
