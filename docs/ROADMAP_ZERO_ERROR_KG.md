# Zero-Error Health Knowledge Graph — Additional Roadmap

This document describes the **additional** KG roadmap (three data streams, ontology extensions, autonomous builder, verification) and the **incremental execution strategy**: step-by-step, little-by-little improvements so the system is not disrupted and agent/API credits stay under control.

See also: [KG_SCHEMA_AND_EVIDENCE.md](KG_SCHEMA_AND_EVIDENCE.md), [PIPELINE_STRATEGY.md](PIPELINE_STRATEGY.md), [.cursor/plans/roadmap.md](../.cursor/plans/roadmap.md).

---

## High-level phases (future work)

| Phase | Scope |
|-------|--------|
| **Phase 1** | Three data streams: (A) USDA API for food/nutrient data, (B) NLM API for clinical code mapping (ICD-10-CM, MeSH), (C) PubMed relationship extraction with explicit Food→Nutrient→Effect→Disease chain and SourceID. |
| **Phase 2** | Ontology: **Study** node, **(Study)-[:EVIDENCE_FOR]->(Relationship)**, **AFFECTS** with `impact` and `confidence`. |
| **Phase 3** | Autonomous builder: .cursorrules for pipeline/format, optional “Big Mission” script (USDA + PubMed → Cypher). |
| **Phase 4** | Verification: Gemini audit (downgrade overclaims), multi-hop queries (e.g. nutrients for age/gender to mitigate sarcopenia). |

---

## Incremental execution strategy (step-by-step, no disruption)

Improve the KG **little by little**: each step is small, optional, and does not change existing behavior by default. This avoids interrupting the system and keeps agent/API usage low.

### Principles

- **One small step per session**: Implement or enable one micro-step at a time; validate (e.g. `make validate`, `./run.sh check`) before the next.
- **Off by default**: New pipeline steps (USDA, NLM, audit) are **optional** (config flag or separate script). Default `run_pipeline.py` behavior stays **fetch → extract → ingest** only.
- **Credit guards**: Use **strict limits** in config (e.g. `max_results: 5` for testing, `extract.max_papers_per_run: 3`, audit `sample_size: 10`) so a single run cannot exhaust API/agent credits. Increase limits only after validation.
- **No big rewrites**: Prefer adding a new script or config block over changing existing logic in place. Existing code paths remain the default.

---

### Micro-steps (ordered, one at a time)

#### Batch 1 – Validation and provenance (no new APIs)

1. **Validate source_id**  
   In `kg_pipeline/src/validate_run.py`, add a check that every triple has a non-empty `source_id`; log count of invalid triples and optionally exclude them from ingest. No change to fetch or extract.

2. **Reject triples without source_id at ingest**  
   In `kg_pipeline/src/ingest_to_neo4j.py`, skip (and log) triples missing `source_id` instead of ingesting with empty string. Keeps graph clean without touching Gemini.

3. **Config cap for testing**  
   In `kg_pipeline/config.yaml`, ensure `fetch.max_results` has a low default (e.g. 5) or document a "test mode" (e.g. `max_results: 3`) so pipeline runs stay cheap until you raise it.

#### Batch 2 – Extraction prompt tweaks (minimal Gemini use)

4. **Prompt chain hint**  
   In `kg_pipeline/src/extract_triples.py`, add one short sentence to the extraction prompt: "When possible, emit the chain Food → CONTAINS → Nutrient and Nutrient → AFFECTS/ALLEVIATES/AGGRAVATES → Symptom/Disease so the paper trail is explicit." No new steps; next run will occasionally produce more structured triples.

5. **Optional AFFECTS in ontology**  
   Add **AFFECTS** to `kg_pipeline/src/ontology.py` `PREDICATES` and to the prompt section. Ingest already accepts unknown predicate names via `normalize_predicate`; no ingest code change required. Run extract once with `max_results: 3` to confirm.

#### Batch 3 – Schema and docs only (no pipeline run)

6. **Study node in ontology and schema doc**  
   Add **Study** to `ENTITY_TYPES` in `kg_pipeline/src/ontology.py` and to the index list in `kg_pipeline/src/ingest_to_neo4j.py`. Update [KG_SCHEMA_AND_EVIDENCE.md](KG_SCHEMA_AND_EVIDENCE.md) with Study and EVIDENCE_FOR. Do **not** yet ingest Study nodes or EVIDENCE_FOR edges; this only reserves the schema for later.

7. **Document incremental roadmap**  
   This file. No code change.

#### Batch 4 – One small new data path (optional)

8. **USDA stub**  
   Add a **standalone** script `kg_pipeline/src/fetch_usda.py` that, when given a config key (e.g. `usda.enabled: false`), does nothing and exits 0. Add `usda.enabled` and `usda.max_foods: 5` to config. Document in `kg_pipeline/RUN.md` that "USDA step is optional and currently a stub." No call to USDA API yet; no integration into `run_pipeline.py`.

9. **USDA one-call**  
   Implement a single USDA API call (e.g. one food or one search), write result to `kg_pipeline/data/usda_sample.json`, and exit. Run manually; do not wire into `run_pipeline.py` yet. Keeps credit use to one request.

#### Batch 5 – Audit and automation (strict limits)

10. **Audit script with tiny sample**  
    Add `kg_pipeline/src/audit_graph.py` that reads **only the first 5 relationships** from `master_graph.json` (or from Neo4j with LIMIT 5), calls Gemini once with a short prompt ("Classify claim strength: strong / supportive / overclaim"), and writes a small report to `kg_pipeline/data/audit_report_sample.json`. No writes to Neo4j; no automatic re-ingest. Run manually.

11. **.cursorrules one line**  
    Add a single line to `.cursorrules`: "Extracted KG data must include source_id; nutrient values must have units (flag if missing)." No pipeline code change.

---

### After each step

Run `make validate` or `./run.sh check` to confirm the system still works. Increase `max_results` or add full USDA/NLM/audit only when you are ready and credits allow.
