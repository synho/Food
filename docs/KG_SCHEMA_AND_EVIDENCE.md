# Knowledge Graph Schema & Evidence Model

## Layered Design

We do **not** build one big messy KG. We use **multiple layers** (see [HEALTH_MAP_LAYERS.md](./HEALTH_MAP_LAYERS.md)): each layer has its own node/relationship types and scope; the health map **aligns** them by user. This document describes the **schema per layer** (core + aging/biology); shared entities (e.g. Disease, Food) live in the core layer and can be referenced by other layers.

---

## Purpose

A **well-organized, systematic** knowledge base (per layer) that supports:

- Zero-error tolerance: every recommendation/restriction is backed by traceable evidence.
- Flexible querying: by disease, symptom, food, nutrient, user context (age, gender, ethnicity).
- Safe path and food recommendations with full provenance.

---
Ontology approach. We need to add any health related specifics. gemomics, family history, current medication, input should be easy and free text based input but we need to oranized in the behind the curtain.
## Node Types (Entity Labels)

### Core (disease, food, lifestyle)

| Label | Description | Example |
|-------|-------------|--------|
| `Disease` | Condition, disorder, syndrome | Hypertension, Type 2 Diabetes |
| `Symptom` | Clinical symptom or sign | Fatigue, Bloating |
| `Food` | Food or food group | Olive oil, Leafy greens |
| `Nutrient` | Vitamin, mineral, compound | Vitamin D, Potassium |
| `Drug` | Medication or treatment | Metformin |
| `LifestyleFactor` | Activity, habit, behavior | Physical activity, Smoking |

### Aging & human biology (general guidance, “why pay attention”)

| Label | Description | Example |
|-------|-------------|--------|
| `BodySystem` | Organ system or physiological domain | Musculoskeletal, Cardiovascular, Metabolism |
| `AgeRelatedChange` | Normative change with age (not necessarily a disease) | Sarcopenia, Bone loss, Slower metabolism |
| `LifeStage` | Age band or life phase | 30s, 40s, 50s, 60s and older |

### Evidence graph (reserved; not yet populated by pipeline)

| Label | Description | Example |
|-------|-------------|--------|
| `Study` | A published study or clinical trial node | "RCT: Omega-3 and Hypertension (PMCID 12345)" |

`Study` nodes are reserved for the future evidence graph where individual studies can be queried directly and related to claims via `(Study)-[:EVIDENCE_FOR]->(Relationship)`. The schema index is created at ingest time; no Study nodes are ingested from the current pipeline yet.

All nodes have at least:

- `name` (string, normalized): canonical display name.
- `id` (optional): stable internal ID for deduplication and versioning.

---

## Relationship Types (Predicates)

| Relationship | From → To | Meaning |
|--------------|-----------|--------|
| `PREVENTS` | Nutrient / Food / LifestyleFactor → Disease | Reduces risk or prevents onset |
| `CAUSES` | Food / Drug / LifestyleFactor → Disease / Symptom | Increases risk or causes |
| `TREATS` | Drug / Food / Nutrient → Disease / Symptom | Used in treatment or management |
| `CONTAINS` | Food → Nutrient | Food contains nutrient |
| `AGGRAVATES` | Food / Drug / LifestyleFactor → Disease / Symptom | Worsens condition or symptom |
| `REDUCES_RISK_OF` | LifestyleFactor / Food / Nutrient → Disease | Lowers risk |
| `ALLEVIATES` | Food / Nutrient / Drug → Symptom | Reduces symptom severity |
| `EARLY_SIGNAL_OF` | Symptom → Disease | This symptom/sign is an early indicator of that disease (enables “prepare in advance, evacuate to safety”) |
| `SUBSTITUTES_FOR` | Food / Nutrient → Drug | This food/ingredient can partly substitute for the drug (evidence from FDA, drug labels, or literature). See [DATA_SOURCES_AND_DRUG_SUBSTITUTION.md](./DATA_SOURCES_AND_DRUG_SUBSTITUTION.md). |
| `COMPLEMENTS_DRUG` | Food / Nutrient → Drug | This food/ingredient complements the drug when used together (evidence required). |
| `AFFECTS` | Food / Nutrient → Disease / Symptom | Direction or magnitude unspecified; use when the text supports a relationship but not PREVENTS/CAUSES/TREATS/ALLEVIATES/AGGRAVATES. |

**Early signals and safety**: For each disease we curate **early signals** (symptoms/signs). “Foods that reduce early signals” = foods that **ALLEVIATES** that symptom; “foods to avoid” = **AGGRAVATES** that symptom. See [EARLY_SIGNALS_AND_SAFETY.md](./EARLY_SIGNALS_AND_SAFETY.md).

### Aging & biology (general guidance, “why pay attention”)

| Relationship | From → To | Meaning |
|--------------|-----------|--------|
| `PART_OF` | AgeRelatedChange → BodySystem | Change belongs to this system |
| `OCCURS_AT` | AgeRelatedChange → LifeStage | When this change typically appears or accelerates |
| `INCREASES_RISK_OF` | AgeRelatedChange → Disease | Unmitigated change raises risk of disease |
| `MODIFIABLE_BY` | AgeRelatedChange → Nutrient / Food / LifestyleFactor | Diet or exercise can slow, prevent, or partly reverse the change |
| `EXPLAINS_WHY` | Nutrient / Food / LifestyleFactor → AgeRelatedChange | Why paying attention to this matters for this change |

Relationship properties (required for evidence):

- `source_id`: e.g. PMCID (PMC12345), PMID, FDA document ID, drug label ID, or dataset ID.
- `source_type` (optional but recommended): e.g. `PMC`, `FDA`, `drug_label`, `pharma` — to distinguish trusted sources (FDA, 제약사/라벨) from literature. See [DATA_SOURCES_AND_DRUG_SUBSTITUTION.md](./DATA_SOURCES_AND_DRUG_SUBSTITUTION.md).
- `context`: Short quote or summary from source justifying the claim.
- `journal`: Journal name (when from a paper).
- `pub_date`: Publication date (YYYY-MM-DD or YYYY).
- `evidence_type` (optional): e.g. RCT, meta-analysis, cohort, review — for future ranking.

---

## Evidence Model (Zero-Error Tolerance)

1. **Every claim is a relationship** in the KG with at least:
   - `source_id`, `context`, `journal`, `pub_date`.
2. **No recommendation without evidence**: The Wisdom/API layer only recommends or restricts foods by traversing the KG and returning these relationship properties as evidence.
3. **Display rule**: UI (web/app) always shows “why” and “evidence” (source, quote, journal, date) for each recommended or restricted food.
4. **Deduplication**: Same fact from multiple sources can create multiple relationships (same subject/object, different source_id/context) — we preserve all evidence; aggregation (e.g. “3 studies”) can be computed at query time.
5. **Normalization**: Entity names are normalized (e.g. one “Vitamin D” node) so that evidence from many papers attaches to the same node. Normalization rules and synonym handling to be implemented in pipeline (e.g. in extraction or in a dedicated step).

---

## Optional Extensions (Later)

- **Study type / evidence strength**: `evidence_type`, `confidence_score` for ranking recommendations.
- **Population**: `gender`, `ethnicity`, `age_group` on relationships for personalized evidence.
- **Dosage / amount**: e.g. “high sodium” vs “sodium” as separate relationships or properties for foods.

---

## Consistency With Current Pipeline

The existing `extract_triples.py` and `ingest_to_neo4j.py` already use:

- Subject/object types and predicates aligned with the above.
- `source_id` and `context` on relationships.

To align fully with this schema:

- Add `journal` and `pub_date` to the extraction prompt and to the ingest step (from article metadata).
- Introduce `evidence_type` when we have structured study-type extraction.
- Enforce normalization and deduplication in pipeline or in a dedicated normalization module.
