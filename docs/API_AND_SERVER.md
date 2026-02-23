# Server API & Food Recommendation Contract

we can start providing, foods, users can buy in the local grocery market. later we can provide the price and quality too.
later, we will provide online shopping information.


## Role of the Server

- **Single backend** for the web app and future mobile app.
- Hosts **business logic**: health map position, safest path, recommended/restricted foods.
- **Composes multiple layers** (core disease/food, aging/biology, later others) into one aligned view per user — see [HEALTH_MAP_LAYERS.md](./HEALTH_MAP_LAYERS.md). We do not build one big messy KG; the server queries the relevant layers and overlays results.
- All recommendations and restrictions are **derived from the KG** (per layer) and returned with **evidence** (source_id, context, journal, date).

---

## Core API Surface (To Implement)

### 1. User context (input)

Server accepts a **user profile** (or session) with the following. **None are required**; the more we have, the more accurate and safer the guidance. We don’t force; we make it easy to add more, and with consent we can auto-discover some fields (e.g. location, time zone). See [USER_CONTEXT_AND_COLLECTION.md](./USER_CONTEXT_AND_COLLECTION.md).

- `age`, `gender`, `ethnicity` (optional)
- **`location`** / **place of living**: country, region, city — for local food, season, future grocery
- **`way_of_living`** / **lifestyle**: e.g. activity level, work pattern, cooking access, eating habits
- **`culture`** / **dietary_culture**: e.g. vegetarian, halal, Mediterranean, or free text — so guidance is relevant and respectful
- `conditions`: list of current diseases/conditions (KG entity names or IDs)
- `symptoms`: list of current symptoms
- `medications`: optional, for interaction checks
- `goals`: e.g. `["longevity", "weight_management", "hypertension_management"]`
- `timezone` or `season` (optional; can be inferred with consent from device)

### 2. Health map position

- **Endpoint** (e.g. `GET /api/health-map/position` or `POST /api/user/position` with body).
- **Returns**: A representation of the user’s “location” on the health map (e.g. dimensions, risk tags, active conditions). Used by the front end to render the map and the safest path.

### 3. Food recommendations (with evidence)

- **Endpoint** (e.g. `POST /api/recommendations/foods` with user context).
- **Returns**:
  - **Recommended foods**: list of items, each with:
    - `food` (name or ID)
    - `reason`: short “why” (e.g. “Associated with reduced risk of X”)
    - `evidence`: list of `{ source_id, source_type, context, journal, pub_date }` (source_type e.g. PMC, FDA, drug_label for trust; see [VISUALIZATION_AND_TRUST.md](./VISUALIZATION_AND_TRUST.md))
    - (optional) `evidence_count`, `source_types` for UI trust badges and "N sources"
  - **Restricted / not-recommended foods**: same structure (food, reason, evidence [+ optional counts]).

Rule: **Every** recommended or restricted item must have at least one evidence entry from the KG. Include **source_type** so the client can differentiate trust in the UI.

### 4. General guidance (food + aging / biology — “why pay attention”)

- **Endpoint** (e.g. `GET /api/recommendations/summary` or `GET /api/guidance/general` with query `age=52`).
- **Returns**:
  - High-level **food** guidance (e.g. “Prefer Mediterranean-style choices; limit sodium”) with evidence links.
  - **Aging & biology**: relevant **age-related changes** for the user’s life stage (what changes, when), and **why pay attention** to diet, exercise, etc. — each with evidence (source_id, context, journal, pub_date). See [AGING_AND_HUMAN_BIOLOGY.md](./AGING_AND_HUMAN_BIOLOGY.md).

### 5. Safest path (evacuation to safety)

- **Endpoint** (e.g. `GET /api/health-map/safest-path` with user context).
- **Returns**: A small set of actionable steps to **evacuate to safety** (e.g. “Increase potassium-rich foods; reduce processed meat”) with evidence — so the user can avoid nearby disease/death and maintain life in a safe place. Anti-aging / slow-aging can be part of this path.

### 6. Position prediction & nearby risks

- **Endpoint** (e.g. `GET /api/health-map/position` or `POST /api/user/position` with body).
- **Returns**: **Where the user is** on the map (predicted from context); **nearby risks** (diseases, early signals) so the UI can show “you are here” and what to avoid.

### 7. Drug-substituting foods/ingredients (약물 대체·보완 음식·성분)

- **Endpoint** (e.g. `GET /api/drug-substitution?drug=Metformin` or `POST /api/recommendations/drug-substitution` with body `{ "drugs": ["Metformin"] }`).
- **Returns**: For each drug, **foods/ingredients** that can **substitute** (SUBSTITUTES_FOR) or **complement** (COMPLEMENTS_DRUG) it, with **reason** and **evidence** (source_id, source_type e.g. FDA/drug_label/PMC, context). Evidence only from trusted sources (FDA, drug labels, literature). User-facing disclaimer: not medical advice; consult doctor/pharmacist.
- See [DATA_SOURCES_AND_DRUG_SUBSTITUTION.md](./DATA_SOURCES_AND_DRUG_SUBSTITUTION.md).

### 8. Early-signal guidance (prepare in advance)

- **Endpoint** (e.g. `GET /api/guidance/early-signals` or included in recommendations with user’s symptoms / risk diseases).
- **Returns**: For relevant diseases or user’s symptoms: **early signals to watch** (symptom → disease); **foods that reduce** those signals (ALLEVIATES + evidence); **foods to avoid** (AGGRAVATES + evidence). Messaging: prepare in advance so they can evacuate to a safe path and reduce the need for medication or a doctor visit. See [EARLY_SIGNALS_AND_SAFETY.md](./EARLY_SIGNALS_AND_SAFETY.md).

---

## Visualization & Trust

All API responses that return recommendations, guidance, or paths must include **evidence** with **source_type** (and optionally evidence_type, counts) so the client can:
- **Differentiate** information vs knowledge vs wisdom (see [VISUALIZATION_AND_TRUST.md](./VISUALIZATION_AND_TRUST.md)).
- **Display trust**: e.g. FDA vs PMC vs drug_label via badges/icons/color.
- Show "N sources" or "Based on X studies" and let users expand to see source_id, journal, date, context.

---

## Data Contract (Zero-Error Tolerance)

- **Recommendation / restriction**:  
  `{ "food": string, "reason": string, "evidence": Evidence[] }`  
  where `Evidence = { "source_id": string, "context": string, "journal": string, "pub_date": string }`.

- **No recommendation or restriction** should be returned without at least one `evidence` item that traces to the KG (and thus to a real source).

- **Health map** and **safest path** can reference KG entities and evidence in their payloads so the UI can show “based on N studies” or “source: Journal, date.”

---

## Technology (Guidance)

- **Web first**: Implement these APIs for the web client (e.g. REST or GraphQL). Same APIs will be consumed by the future app.
- **Server**: Can be Python (e.g. FastAPI) or Node, in the same repo or a dedicated `server/` or `api/` service. Neo4j driver used to query the KG and build recommendations from graph traversals.
- **Auth / persistence**: User profiles and sessions can be added later; initially, API can accept user context in the request body for stateless use.
- **Pricing / plans**: We start **almost free** and later offer **paid use** (e.g. subscription). Design APIs and server so **tiered access** (free vs paid) can be added later — e.g. plan or role in auth, rate limits or feature flags by plan. See [PRICING_AND_MONETIZATION.md](./PRICING_AND_MONETIZATION.md).

---

## Summary

| Need | API / behavior |
|------|-----------------|
| **Where user is** (position prediction) | Position endpoint; nearby risks (diseases, early signals) for “you are here” and what to avoid |
| **Evacuate to safety** | Safest-path endpoint; actionable steps to avoid nearby disease/death; anti-aging part of path |
| **Drug-substituting foods/ingredients** | For a drug, list foods/ingredients that substitute or complement it (evidence: FDA, drug label, PMC) |
| **Early signals** (prepare in advance) | Early-signal guidance: foods that reduce signals, foods to avoid; act before needing a doctor |
| General food choice | Summary or guidance endpoint with evidence |
| Recommended food + why + evidence | Recommendations endpoint; every item has `reason` + `evidence[]` |
| Restricted food + why + evidence | Same endpoint; restricted list with `reason` + `evidence[]` |
| Health map position | Position endpoint for map UI |
| Web then app | Same server and APIs for both |
