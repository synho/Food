# Health Navigation Platform — Documentation

This folder contains the vision, design, and plan for the platform.

| Document | Purpose |
|----------|--------|
| **[SUMMARY_PLAN_AND_ARCHITECTURE.md](./SUMMARY_PLAN_AND_ARCHITECTURE.md)** | **개발 플랜·아키텍처 전체 요약 (한 문서)** |
| [VISION.md](./VISION.md) | Mission, DIKW flow, health map, user inputs, outputs, web→app strategy |
| [HEALTH_MAP_LAYERS.md](./HEALTH_MAP_LAYERS.md) | Multi-layer health map (Google Maps–style); we don’t build one big messy KG |
| [EARLY_SIGNALS_AND_SAFETY.md](./EARLY_SIGNALS_AND_SAFETY.md) | Early signals of disease; foods that reduce vs avoid; evacuate to safety; prepare before needing a doctor |
| [USER_CONTEXT_AND_COLLECTION.md](./USER_CONTEXT_AND_COLLECTION.md) | Place, lifestyle, age, culture; don’t force but make it easy; consent-based auto-discovery |
| [KG_SCHEMA_AND_EVIDENCE.md](./KG_SCHEMA_AND_EVIDENCE.md) | Knowledge Graph schema per layer, relationship types (incl. EARLY_SIGNAL_OF), evidence model (zero-error tolerance) |
| [PIPELINE_STRATEGY.md](./PIPELINE_STRATEGY.md) | Recent-first, high-impact journals, iterative expansion of the KG |
| [PIPELINE_AGENTS.md](./PIPELINE_AGENTS.md) | Fetch agent: volume limits, smart keyword expansion; Extract agent: cheap model first, accuracy vs cost balance |
| [DATA_SOURCES_AND_DRUG_SUBSTITUTION.md](./DATA_SOURCES_AND_DRUG_SUBSTITUTION.md) | Trusted sources (FDA, 제약사/라벨); foods/ingredients that can substitute or complement drugs |
| [VISUALIZATION_AND_TRUST.md](./VISUALIZATION_AND_TRUST.md) | Visualization of information/knowledge/wisdom; trust/credibility differentiation (source_type, evidence) |
| [AGENTS_AND_ARTIFACTS.md](./AGENTS_AND_ARTIFACTS.md) | Specialized agents (Fetch/Extract/Ingest), manifests, cascade, RUN_ID; adding new steps |
| [API_AND_SERVER.md](./API_AND_SERVER.md) | Server API: food recommendations, restricted foods, evidence, health map, safest path |
| [AGING_AND_HUMAN_BIOLOGY.md](./AGING_AND_HUMAN_BIOLOGY.md) | General human biology & aging: what changes, when, why pay attention to diet/exercise |
| [ROADMAP.md](./ROADMAP.md) | Phased development: pipeline → server → web → expansion → app |
| [PRICING_AND_MONETIZATION.md](./PRICING_AND_MONETIZATION.md) | Start almost free; later paid use (subscription); design for tiered access |

Start with **SUMMARY_PLAN_AND_ARCHITECTURE.md** for the full picture in one place, or **VISION.md** and **ROADMAP.md**; use the others when implementing pipeline, KG, or API.
