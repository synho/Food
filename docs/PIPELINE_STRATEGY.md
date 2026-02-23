# Pipeline Strategy: Recent First, Iterative Expansion

Eventually, we want to accumulted human medical, health knowledge, with high accuracy. if there are other reliable sources (definitely reliable) we can also use and collect those information

## Goal

Extract **Knowledge** from medical literature in a controlled way:

1. **High-impact journals only** (curated list).
2. **Human studies only** — no animal models; we restrict to papers indexed as human studies (e.g. "humans"[MeSH Terms]).
3. **Recent publications first** (e.g. last 30 days, then 90, then 1 year).
4. **Iterative expansion**: after validating quality and coverage, increase time window and/or add journals.

This keeps the KG evidence-based and allows us to grow without overwhelming the system or diluting quality.

---

## Current Implementation (Baseline)

- **Journals**: `fetch_papers.py` uses config journals (e.g. Nat Med, Lancet, NEJM, JAMA, BMJ, Cell, Science, Nature, Ann Intern Med, Am J Clin Nutr).
- **Recency**: `build_search_query(..., days_back=30)` and `max_results` from config.
- **Source**: PubMed Central (PMC), open access filter, human studies only.

---

## Trusted Data Sources (믿을 수 있는 추가 소스)

Besides PMC, we include **trusted sources** so we can present **foods/ingredients that can substitute or complement drugs** (약물 대체·보완 음식·성분) with evidence:

| Source | Role |
|--------|------|
| **FDA** | Drug approvals, labels, dietary/food guidance; evidence for drug–food/ingredient relations. |
| **Drug labels (제약사/라벨)** | Official drug information, indications, dietary recommendations; basis for SUBSTITUTES_FOR / COMPLEMENTS_DRUG. |
| **Other verified sources** | National pharmacopoeias, public health DBs — add with same evidence model (source_id, source_type). |

Data from these sources is ingested with the **same evidence schema** (source_id, source_type, context, date) and linked in the KG (e.g. SUBSTITUTES_FOR, COMPLEMENTS_DRUG). See [DATA_SOURCES_AND_DRUG_SUBSTITUTION.md](./DATA_SOURCES_AND_DRUG_SUBSTITUTION.md).

---

## Phased Expansion (Recommended)

| Phase | Scope | Purpose |
|-------|--------|--------|
| **1. Seed** | 30 days, 5–10 papers, current journal list | Validate pipeline end-to-end; check triple quality and Neo4j schema. |
| **2. Recent** | 90 days, 50–100 papers | Build initial KG for web MVP; recent evidence first. |
| **3. Expand time** | 1 year, same journals | Deeper coverage without adding new journals. |
| **4. Expand journals** | Add more high-impact journals (e.g. specialty) | Broader conditions and nutrients. |
| **5. Ongoing** | Scheduled runs (e.g. weekly) for last 7–14 days | Keep KG updated with latest evidence. |

Expansion should be **configurable** (e.g. `days_back`, `max_results`, journal list in config or env) so we can run different strategies without code changes.

---

## Quality and Validation

- **Deduplication**: Same (subject, predicate, object) from multiple papers → keep all evidence (multiple relationships or evidence records), one normalized node pair.
- **Normalization**: Canonical names for entities (e.g. “Vitamin D” not “vitamin D”) to avoid splintered nodes; can be done in extraction (prompt) or in a post-step.
- **Provenance**: Every triple has `source_id`, `context`, and (after schema update) `journal`, `pub_date`. No triple without provenance.
- **Review**: Optional human-in-the-loop or automated checks (e.g. predicate set, entity type set) before marking a batch “production.”

---

## Implementation Notes

- Move `days_back`, `max_results`, and optionally journal list to **config** (e.g. `config.yaml` or env) so pipeline runs are reproducible and tunable.
- Add a **pipeline run manifest**: store each run’s parameters and list of ingested PMCIDs so we can re-run or backfill.
- Consider **incremental ingestion**: only fetch papers not yet in `data/raw_papers` (by PMCID) to avoid re-processing.
