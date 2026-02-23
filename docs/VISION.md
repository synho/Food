# Vision: Health Navigation Platform

## Mission

Build a **systematic, evidence-based platform** that helps users **predict where they are** on a health map and **evacuate to a safe path** — avoiding **nearby disease or death** so they can **maintain life in a safe place**. **Anti-aging and slow-aging** are explicit goals. An **accurate, diverse knowledge map** (multiple layers, evidence-based) is essential.

We combine:

- **Knowledge** from high-impact medical literature and **trusted data sources** (e.g. **FDA**, 제약사/약물 라벨) stored in a Knowledge Graph; high-impact and recently published open journals first. We use these to present **foods/ingredients that can substitute or complement drugs** (약물 대체·보완 음식·성분) with evidence. See [DATA_SOURCES_AND_DRUG_SUBSTITUTION.md](./DATA_SOURCES_AND_DRUG_SUBSTITUTION.md).
- **Wisdom** derived from that KG (position prediction, safest path, recommendations, risk stratification).
- **Personal context**: **place of living**, **way of living**, **age**, **culture**, plus gender, ethnicity, conditions, symptoms, season, special diet, and any personalized input. The more of this we reflect, the **more accurate and safer** the guidance. We don’t force users to give everything; we make it **easy to provide more** and, with **consent**, **automatically discover** what we can (e.g. location, time zone). See [USER_CONTEXT_AND_COLLECTION.md](./USER_CONTEXT_AND_COLLECTION.md).

The primary lever is **food**: prevent disease or support recovery through **recommended foods** and **restricted foods**, always backed by **citable evidence** (zero-error tolerance).

We **find early signals of each disease** and tell users which **foods reduce** those signals and which **foods to avoid**, so they can act **before or while on medication** — **before they need to see a doctor** — and **prepare in advance** to evacuate to a safe path. See [EARLY_SIGNALS_AND_SAFETY.md](./EARLY_SIGNALS_AND_SAFETY.md).

We also collect **general human biology and aging** knowledge (what changes, when, why) to give general guidance and explain why diet and exercise matter. See [AGING_AND_HUMAN_BIOLOGY.md](./AGING_AND_HUMAN_BIOLOGY.md).

---

## DIKW Flow

| Layer | Meaning in This Platform |
|-------|--------------------------|
| **Data** | Raw articles, datasets from high-impact medical journals (e.g. PubMed Central, PMC). |
| **Information** | Structured extractions: entities (diseases, foods, nutrients, drugs, lifestyle factors) and relationships (PREVENTS, TREATS, CAUSES, CONTAINS, AGGRAVATES, REDUCES_RISK_OF). |
| **Knowledge** | The **Knowledge Graph**: normalized, deduplicated, versioned, with provenance (source, date, journal, study type). This is the single source of truth. |
| **Wisdom** | Inferences and recommendations: "safest path" on the health map, recommended vs restricted foods, reasoning chains, and evidence trails. Served by the server to web and future app. |

We extract **Knowledge** from **Data** in a controlled pipeline; we derive **Wisdom** from the **Knowledge** graph plus user context (inputs below).

---

## Health Map / Life Journey Map (Multi-Layer)

Like **Google Maps**, the health map has **multiple layers**; each layer has **different information**, and we **align them based on the user**. We do **not** build one big messy KG — we build **multiple, well-defined layers** (core disease/food/evidence, aging & biology, later: genetics, location, preferences). See [HEALTH_MAP_LAYERS.md](./HEALTH_MAP_LAYERS.md).

- We **predict where the user is** on the health map from their context (symptoms, conditions, age, etc.).
- **Nearby risks**: diseases or poor outcomes that are “close” on the map. Goal is to **avoid** them and **evacuate to a safe path** so the user can **maintain life in a safe place** (longevity, disease-free or best achievable state). **Anti-aging / slow-aging** are part of that safe path.
- User describes **health problems** (symptoms, diagnoses, concerns). System composes several **layers** (core evidence, early signals, aging/biology, future layers) into one view for that user.
- **Early signals**: We use **early signals of each disease** (symptoms/signs that warn of risk) to recommend **foods that reduce** those signals and **foods to avoid**, so users can **prepare in advance** — before or while on medication — and reduce the need to see a doctor. See [EARLY_SIGNALS_AND_SAFETY.md](./EARLY_SIGNALS_AND_SAFETY.md).
- The **safest path** is informed by KG facts (disease–food–evidence, early signals, aging) and wisdom: risk, recommendations, contraindications, evidence quality.

---

## User Inputs (Web → App)

Designed to be **robust and flexible**; same inputs for web and future app. **We don’t force** users to fill everything; we make it **easy to add more** so that place, lifestyle, age, and culture are reflected for **more accurate, safer** guidance. With **consent**, we can **automatically discover** some information (e.g. location, time zone). See [USER_CONTEXT_AND_COLLECTION.md](./USER_CONTEXT_AND_COLLECTION.md).

| Input | Purpose |
|-------|--------|
| **Age** | Life-stage, risk stratification, aging/biology layer. |
| **Place of living** | Location (region, country, city) for local food, season, grocery; optional, can be auto-detected with consent. |
| **Way of living** | Daily routine, activity level, work/cooking habits — so recommendations are feasible and safe. |
| **Culture** | Dietary traditions, restrictions, preferences (e.g. vegetarian, halal, traditional cuisines) so guidance is relevant. |
| **Gender** | Where evidence is gender-specific. |
| **Ethnicity** | Where evidence or risk differs by population. |
| **Current disease(s) / conditions** | Map position; filter recommendations and restrictions. |
| **Current symptoms** | Map position; link to foods that aggravate or alleviate; early signals. |
| **Medications / treatments** | Avoid food–drug interactions; align with TREATS/CONTAINS. |
| **Goals** | e.g. longevity, weight, specific disease prevention. |

---

## Outputs (Server → Web, Later App)

The **server** is the single backend for web and app. It must provide:

1. **General guidance (including aging & biology)**
   - Overall food and lifestyle choices aligned with user’s health map and **life stage**.
   - **Why pay attention**: explanations of age-related body changes and why diet, exercise, etc. matter (with evidence). See [AGING_AND_HUMAN_BIOLOGY.md](./AGING_AND_HUMAN_BIOLOGY.md).

2. **Recommended foods**
   - What to eat (or increase).
   - **Why**: short reasoning.
   - **Evidence**: source(s) from KG (paper, journal, date, quote/context), with zero tolerance for unsupported claims.

3. **Restricted / not-recommended foods**
   - What to avoid or reduce.
   - **Why**: short reasoning.
   - **Evidence**: same standard — every restriction tied to KG-backed evidence.

4. **Health map position**
   - Where the user sits on the life-journey / health map (for UI).

5. **Safest path**
   - High-level trajectory (e.g. “reduce sodium, increase potassium, focus on Mediterranean-style choices”) with evidence links.

All clinical or recommendation-style claims must be **traceable to the KG** (and thus to specific literature); no unsupported “wisdom.”

**Visualization and trust**: Presenting information, knowledge, and wisdom effectively and differentiating trust are essential. The UI must let users tell apart evidence (information), KG-backed facts (knowledge), and recommendations (wisdom), and show source_type (e.g. FDA, PMC, drug label) and evidence strength so credibility is clear. See [VISUALIZATION_AND_TRUST.md](./VISUALIZATION_AND_TRUST.md).

---

## Platform Strategy: Web First, Then App

- **Web version first**: full functionality on the web (inputs, health map, recommendations, evidence).
- **Server**: all logic and data access live on the server (APIs). The web client (and later the app) are thin clients.
- **App later**: reuse the same APIs; only presentation and form factor change. This keeps one source of truth (KG + Wisdom) and one set of business rules.

---

## Pricing: Free at First, Paid Later

- **Initially**, use is **almost free** — to grow adoption, get feedback, and prove value.
- **Later**, we want the product to be an **app users pay to use** (e.g. subscription). We design the system from the start to support **tiered access** (free vs paid) so we can add paid plans without re-architecting. See [PRICING_AND_MONETIZATION.md](./PRICING_AND_MONETIZATION.md).

---

## Design Principles

1. **Zero-error tolerance for references**: Every recommendation or restriction must point to at least one KG-backed evidence record (source_id, context, journal, date).
2. **Systematic KG**: Well-defined schema, entity types, relationship types, and evidence model (see KG_SCHEMA_AND_EVIDENCE.md).
3. **Recent, high-impact first**: Prioritize recent publications from high-impact journals, then iteratively expand (see PIPELINE_STRATEGY.md).
4. **Robust and flexible**: Same pipeline and server support many inputs and future extensions (e.g. new entity/relationship types, new journals).
5. **Multiple layers, not one big KG**: The health map is built from **multiple layers** (core, aging/biology, later others); each layer has a clear scope and is maintained separately; we align them by user so the map stays organized and scalable. See [HEALTH_MAP_LAYERS.md](./HEALTH_MAP_LAYERS.md).
6. **Reflect place, lifestyle, age, culture**: More context → more accurate, safer information. We **don’t force**; we make it **easy to provide more** and, with **consent**, support **auto-discovery** (e.g. location, time zone). See [USER_CONTEXT_AND_COLLECTION.md](./USER_CONTEXT_AND_COLLECTION.md).
