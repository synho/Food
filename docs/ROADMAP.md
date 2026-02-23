# Development Roadmap

Phased plan to build the Health Navigation Platform **systematically**: web first, server as single backend, KG as zero-error reference.

---

## Phase 1: KG pipeline hardening (current repo)

**Goal**: Reliable, configurable pipeline that fills the KG from high-impact, recent-first literature.

- [x] Add **config** for pipeline: `days_back`, `max_results`, journal list (e.g. `kg_pipeline/config.yaml` or env).
- [x] Extend **extraction/ingest** to store `journal` and `pub_date` on relationships (align with KG_SCHEMA_AND_EVIDENCE.md).
- [ ] Run **Phase 1 expansion**: e.g. 30 days, 10–20 papers; validate triples and Neo4j content.
- [ ] Optional: **normalization** step or prompt update so entity names are canonical (e.g. “Vitamin D”).
- [x] Document run procedure and optional **incremental** fetch (skip already-downloaded PMCIDs).
- [ ] **Aging & biology**: Add pipeline queries (or a separate fetch pass) for aging, life course, physiology. Extend extraction for `AgeRelatedChange`, `LifeStage`, `BodySystem`, and relationships `OCCURS_AT`, `MODIFIABLE_BY`, `EXPLAINS_WHY`, `INCREASES_RISK_OF`. See [AGING_AND_HUMAN_BIOLOGY.md](./AGING_AND_HUMAN_BIOLOGY.md).
- [ ] **Early signals**: Extract and ingest **early signals of each disease** (symptom → disease as `EARLY_SIGNAL_OF`); use existing ALLEVIATES/AGGRAVATES for “foods that reduce” vs “foods to avoid” so users can prepare in advance and evacuate to safety. See [EARLY_SIGNALS_AND_SAFETY.md](./EARLY_SIGNALS_AND_SAFETY.md).

**Output**: A growing, accurate, diverse KG (core + aging + early signals) with full provenance — foundation for position prediction, nearby risks, and safe-path evacuation.

---

## Phase 2: Server and core APIs

**Goal**: Server that exposes health map position, food recommendations, and evidence for web (and future app).

- [ ] Create **server** project (e.g. `server/` or `api/` in repo): Python (FastAPI) or Node; Neo4j client.
- [ ] Implement **user context** model: age, gender, ethnicity, conditions, symptoms, goals.
- [ ] Implement **recommendations API**: recommended foods and restricted foods with `reason` and `evidence[]` from KG traversals.
- [ ] Implement **position prediction** API: where the user is on the map; **nearby risks** (diseases, early signals) so UI can show “you are here” and what to avoid.
- [ ] Implement **safest path** (evacuation to safety) API: actionable steps to avoid nearby disease/death; anti-aging / slow-aging as part of path.
- [ ] Implement **early-signal guidance** API: for user’s symptoms/risk diseases, return foods that reduce early signals vs foods to avoid (prepare in advance, before needing a doctor). See [EARLY_SIGNALS_AND_SAFETY.md](./EARLY_SIGNALS_AND_SAFETY.md).
- [ ] Enforce **zero-error rule** in code: no recommendation/restriction without at least one evidence record.
- [ ] **General guidance by age**: Implement endpoint for aging/biology guidance (age-related changes, why pay attention to diet and exercise) with evidence. See [AGING_AND_HUMAN_BIOLOGY.md](./AGING_AND_HUMAN_BIOLOGY.md).
- [ ] Design for **tiered access** later: e.g. user/account and optional plan or role so paid vs free can be added without re-architecting. See [PRICING_AND_MONETIZATION.md](./PRICING_AND_MONETIZATION.md).

**Output**: Working API that returns only KG-backed recommendations with evidence, plus general guidance and “why pay attention” by life stage; ready for free/paid tiers later.

---

## Phase 3: Web client (first product)

**Goal**: Web version where users get food guidance and see their position and path.

- [ ] **Web app** (e.g. React/Next/Vue) that calls the server APIs.
- [ ] **Input flow**: age, gender, ethnicity, conditions, symptoms, goals, plus **optional** place of living, way of living, culture (easy to add more, no forcing). With **consent**, support **auto-discovery** (e.g. location, time zone). See [USER_CONTEXT_AND_COLLECTION.md](./USER_CONTEXT_AND_COLLECTION.md).
- [ ] **Output**: Recommended foods (with why + evidence), restricted foods (with why + evidence), health map view (position + nearby risks), safest path (evacuation to safety).
- [ ] **Early-signal UX**: Show early signals to watch, foods that reduce them, foods to avoid — “prepare in advance so you can stay safe and reduce the need for a doctor.” See [EARLY_SIGNALS_AND_SAFETY.md](./EARLY_SIGNALS_AND_SAFETY.md).
- [ ] **General guidance & “why pay attention”**: Show age-related body changes and why diet/exercise matter for the user’s life stage (with evidence). See [AGING_AND_HUMAN_BIOLOGY.md](./AGING_AND_HUMAN_BIOLOGY.md).
- [ ] **Evidence display**: Every recommendation/restriction shows source (journal, date) and context/quote.
- [ ] **Visualization & trust**: Differentiate information/knowledge/wisdom; show source_type (FDA, PMC, drug_label) and evidence strength so users can judge credibility. See [VISUALIZATION_AND_TRUST.md](./VISUALIZATION_AND_TRUST.md).

**Output**: Public or private web MVP for health navigation with food-focused, evidence-based guidance and trust-aware visualization.

---

## Phase 4: Iterative KG expansion and quality

**Goal**: More coverage and confidence without breaking zero-error tolerance.

- [ ] Increase pipeline scope (e.g. 90 days, 50–100 papers) per PIPELINE_STRATEGY.md.
- [ ] Add **evidence type** (RCT, meta-analysis, etc.) to schema and extraction when feasible.
- [ ] **Deduplication/normalization** in pipeline so KG stays clean as we scale.
- [ ] Optional: **scheduled pipeline runs** (e.g. weekly) for latest papers.

**Output**: Richer KG and more robust recommendations.

---

## Phase 5: Mobile app (later)

**Goal**: Same platform on mobile; no new backend.

- [ ] **Mobile app** (e.g. React Native, Flutter) that consumes the **same server APIs**.
- [ ] Reuse user context, recommendations, health map, and safest path contracts.
- [ ] Only UX and form factor differ; evidence and logic remain on server.
- [ ] **(Later)** **Wearables integration**: e.g. **Apple Watch**, Apple Health, Google Fit — activity, heart rate, sleep, steps. **Consent-based only**; used to refine position and personalize recommendations. Same server accepts wearable-derived context. See [USER_CONTEXT_AND_COLLECTION.md](./USER_CONTEXT_AND_COLLECTION.md#wearables-eg-apple-watch--future).

**Output**: Web + app on one server and one KG; later, optional wearables (e.g. Apple Watch) for richer context.

---

## Phase 6 (later): Monetization — paid use

**Goal**: Turn the product into an **app users pay to use**, while keeping initial use **almost free**.

- [ ] **Pricing model**: Define free tier (e.g. limited requests or basic guidance) and paid tier(s) (e.g. subscription for full features, wearables, history). See [PRICING_AND_MONETIZATION.md](./PRICING_AND_MONETIZATION.md).
- [ ] **Server**: Add plan/subscription awareness (e.g. from auth); apply rate limits or feature flags by plan so paid users get clearly better value.
- [ ] **Billing**: Integrate payment (e.g. in-app purchase for app, or web subscription); keep free tier useful and transparent.

**Output**: Sustainable business with free entry and paid option for power users.

---

## Principles Across Phases

1. **Zero-error tolerance**: Every clinical/recommendation claim traceable to KG evidence.
2. **Web first, then app**: Server and APIs designed once for both.
3. **Recent, high-impact first**: Pipeline strategy (config + iterative expansion) documented and followed.
4. **Systematic KG**: Schema and evidence model (docs) drive pipeline and API design.
5. **Multiple layers, not one big KG**: Health map is composed from well-defined layers (core, aging/biology, later others); each layer maintained separately; align by user. See [HEALTH_MAP_LAYERS.md](./HEALTH_MAP_LAYERS.md).
6. **Reflect place, lifestyle, age, culture**: More context → more accurate, safer guidance. Don’t force; make it easy to add more; with consent, auto-discover (e.g. location, time zone). See [USER_CONTEXT_AND_COLLECTION.md](./USER_CONTEXT_AND_COLLECTION.md).
7. **Free at first, paid later**: Initial use is **almost free**; later we add **paid use** (e.g. subscription). We design for tiered access from the start. See [PRICING_AND_MONETIZATION.md](./PRICING_AND_MONETIZATION.md).
