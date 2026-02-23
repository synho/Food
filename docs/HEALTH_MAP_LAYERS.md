# Health Map Layers (Google Maps–Style)

## Idea

Like **Google Maps**, the health map has **multiple layers**. Each layer holds **different information**; the map **aligns and overlays** them based on the **user** (age, conditions, location, goals, etc.). We do **not** build one big messy KG — we build **multiple, well-defined layers** that stay organized and composable.

---

## Principles

1. **One map, many layers**: The health map is the **unified view** the user sees (position, safest path, recommendations). That view is **composed** from several layers, not from a single monolithic graph.
2. **Each layer has a clear scope**: One layer = one kind of knowledge (e.g. disease–food–evidence; aging/biology; later: genomics, location, season). Schema and pipeline per layer stay focused.
3. **Layers align by user**: The server (or a composition service) queries the relevant layers with the user’s context and **overlays** the results on the same map — e.g. “your conditions” (core) + “your life stage” (aging) + “where you live” (future) on one view.
4. **Cross-layer links where needed**: Layers can **reference** shared concepts (e.g. `Disease`, `Food`, `LifeStage`) or have explicit cross-layer relationships, but each layer is **owned and maintained separately** so we avoid one big messy KG.

---

## Layer Catalog

### Layer 1: Core (Disease, Food, Evidence, Early Signals)

- **Content**: Diseases, symptoms, foods, nutrients, drugs, lifestyle factors; relationships (PREVENTS, TREATS, CAUSES, CONTAINS, AGGRAVATES, REDUCES_RISK_OF, ALLEVIATES, **EARLY_SIGNAL_OF**); full evidence (source_id, context, journal, pub_date).
- **Purpose**: Evidence-based food recommendations and restrictions; **early signals of each disease** → foods that reduce them vs foods to avoid (so users can prepare in advance and evacuate to safety before needing a doctor); safest path; health map position by condition/risk. See [EARLY_SIGNALS_AND_SAFETY.md](./EARLY_SIGNALS_AND_SAFETY.md).
- **Source**: High-impact medical journals (PMC), current pipeline.
- **Schema**: See [KG_SCHEMA_AND_EVIDENCE.md](./KG_SCHEMA_AND_EVIDENCE.md) “Core” nodes and relationships.

### Layer 2: Aging & Human Biology

- **Content**: Body systems, age-related changes, life stages; when changes occur; what modifies them (diet, exercise); why pay attention; link to disease risk (e.g. INCREASES_RISK_OF).
- **Purpose**: General guidance by age; “why pay attention to what you eat and exercise”; aligns with user’s age/life stage on the map.
- **Source**: Same journals + aging/physiology/life-course queries; see [AGING_AND_HUMAN_BIOLOGY.md](./AGING_AND_HUMAN_BIOLOGY.md).
- **Schema**: BodySystem, AgeRelatedChange, LifeStage; PART_OF, OCCURS_AT, MODIFIABLE_BY, EXPLAINS_WHY, INCREASES_RISK_OF (to Disease in core).

### Future layers (examples)

- **Layer 3: Genetics / family history** — risk variants, family history; links to diseases and to personalized “pay attention” (same evidence rules).
- **Layer 4: Place & context** — **place of living** (location), season, local food availability, grocery; align recommendations with what’s feasible where the user lives. Can use **consent-based auto-discovery** (e.g. location, time zone). See [USER_CONTEXT_AND_COLLECTION.md](./USER_CONTEXT_AND_COLLECTION.md).
- **Layer 5: Preferences & constraints** — **way of living**, **culture**, special diets, allergies; filter and align recommendations without mixing into core evidence. We don’t force; we make it easy to add more so guidance is accurate and safe.
- **(Future) Layer 6: Wearables / device data** — e.g. **Apple Watch**, Garmin, Fitbit, or Apple Health / Google Fit: activity, heart rate, sleep, steps. With **consent only**; used to refine position on the map and personalize recommendations (e.g. activity level, sleep quality). See [USER_CONTEXT_AND_COLLECTION.md](./USER_CONTEXT_AND_COLLECTION.md#wearables-eg-apple-watch--future).

Each new layer is **added as its own schema and pipeline** (or data source); the health map **composes** them by user, so we never turn the KG into one big messy graph.

---

## How Layers Align on the Health Map

- **User context** (age, gender, conditions, symptoms, location, goals, …) is the **filter and alignment key**.
- **Server** (or a dedicated “map composer”):
  - Queries **Layer 1** for conditions, recommended/restricted foods, evidence.
  - Queries **Layer 2** for age-related changes and “why pay attention” for the user’s life stage.
  - (Later) Queries **Layer 3** for genetic/family risk, **Layer 4** for local options, **Layer 5** for preferences.
- **Alignment**: Results are merged into one **health map view** (position, safest path, recommendations, general guidance). Where layers share concepts (e.g. Disease, Food), the map uses the same identifiers so the view is consistent.
- **Storage**: Layers can live in the **same Neo4j database** (with clear label/namespace conventions, e.g. by node labels and relationship types) or in **separate graphs/databases** with a thin composition layer. What we avoid is **one undifferentiated KG** with everything mixed together.

---

## Implementation Notes

- **Namespace/labels**: Use consistent naming so “core” vs “aging” vs “place” are obvious (e.g. all aging nodes/rels under a prefix or a dedicated subgraph).
- **Shared entities**: Core layer can own canonical `Disease`, `Food`, `Nutrient`; other layers reference them (e.g. Aging’s INCREASES_RISK_OF points to core’s Disease). Avoid duplicating core entities in other layers.
- **APIs**: One “health map” API can internally call **layer-specific queries** and merge; or expose per-layer endpoints (e.g. `/api/guidance/aging`, `/api/recommendations/foods`) and let the client compose. Either way, the **user** sees one aligned map.

---

## Summary

| Principle | Meaning |
|-----------|--------|
| Multiple layers | Each layer = one kind of knowledge; we don’t build one big messy KG. |
| Different information per layer | Core = disease/food/evidence; Aging = biology/life stage/why; later = genetics, place, preferences. |
| Align by user | The health map overlays layers based on user context (age, conditions, location, etc.). |
| Composable | Server (or client) composes layer results into a single, aligned view for the user. |
