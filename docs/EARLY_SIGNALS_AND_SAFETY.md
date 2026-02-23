# Early Signals & Evacuation to Safety

## Goal

- **Predict where the user is** on the health map.
- Help them **avoid nearby disease or death** and **evacuate to a safe path** so they can **maintain life in a safe place**.
- **Anti-aging and slow-aging** are explicit goals; an **accurate, diverse knowledge map** is essential to support this.

A core product goal: **find early signals of each disease**, tell users which **foods reduce** those signals and which **foods to avoid**, so they can act **before or while on medication** — **before they need to see a doctor** — and evacuate to a safe path in advance.

---

## Early Signals (질병의 초기 신호)

- **Early signal**: A symptom, sign, or biomarker that often appears **before** or in early stages of a disease. Catching it early gives the user time to act (diet, lifestyle, possibly medical follow-up).
- We need to **curate and model** in the KG:
  - **Which symptoms/signs are early signals of which diseases** (with evidence: source_id, context, journal, date).
  - **Foods/nutrients that reduce or alleviate** those early signals → recommend.
  - **Foods/lifestyle factors that aggravate** those early signals → restrict.
- **User flow**: User reports symptoms (or we infer risk from age/conditions). System:
  1. Maps symptoms to **early signals** and linked diseases.
  2. Shows **foods that help reduce** those signals (with evidence).
  3. Shows **foods to avoid** that worsen them (with evidence).
  4. Frames this as **“prepare in advance, evacuate to safety”** — so they can stay on a safe path and reduce the chance of needing medication or a doctor later.

Works **before** starting medication (primary prevention / delay) and **while** on medication (support and avoid worsening).

---

## Evacuation to Safety (안전한 곳으로 대피)

- **Health map**: User’s **position** is predicted from context (age, symptoms, conditions, biomarkers if available).
- **Nearby risks**: Diseases or outcomes (e.g. complications, death) that are “close” on the map — e.g. conditions they are at risk for, or early signals that point to those conditions.
- **Safe path**: Recommendations (foods to increase, foods to avoid, lifestyle) that **move the user away from** those risks and toward longevity / disease-free or best achievable state.
- **Anti-aging / slow-aging**: Part of the safe path — slowing or reversing age-related decline (see [AGING_AND_HUMAN_BIOLOGY.md](./AGING_AND_HUMAN_BIOLOGY.md)) so the user stays in a “safer” region of the map longer.

All of this depends on an **accurate, diverse knowledge map** (multiple layers, evidence-based, with early signals and disease–food links).

---

## KG: Early Signals

- **Link symptom/sign to disease as early signal**: Relationship `EARLY_SIGNAL_OF` from `Symptom` (or a dedicated `EarlySignal` node if we want to distinguish) to `Disease`. Evidence on the relationship (source_id, context, journal, pub_date).
- **Foods that reduce early signals**: Use existing `ALLEVIATES` (Food/Nutrient/LifestyleFactor → Symptom). So “foods that reduce this early signal” = foods that ALLEVIATE that symptom.
- **Foods to avoid**: Use existing `AGGRAVATES` (Food/LifestyleFactor → Symptom). So “foods to avoid” = foods that AGGRAVATE that symptom.
- **Pipeline**: Extraction should capture “early sign of X” and “alleviates/aggravates symptom Y” from literature; we populate EARLY_SIGNAL_OF and ALLEVIATES/AGGRAVATES with evidence.

See [KG_SCHEMA_AND_EVIDENCE.md](./KG_SCHEMA_AND_EVIDENCE.md) for the formal schema addition.

---

## API / Product

- **Position API**: Returns predicted “where the user is” and “nearby” risks (diseases, early signals) so the UI can show “you are here” and “risks nearby.”
- **Safe path API**: Returns actionable steps (foods to eat, foods to avoid, lifestyle) to evacuate to safety, with evidence.
- **Early-signal guidance**: For user’s symptoms (or risk diseases), return:
  - Early signals to watch (symptom → disease links).
  - Foods that **reduce** those signals (ALLEVIATES + evidence).
  - Foods to **avoid** (AGGRAVATES + evidence).
  - Messaging: “Prepare in advance so you can stay on a safe path and reduce the need for medication or a doctor visit.”

---

## Summary

| Concept | Meaning |
|--------|--------|
| Predict position | Where the user is on the health map (from context and, when available, symptoms/labs). |
| Nearby disease/death | Risks “close” on the map; we help them avoid these. |
| Evacuate to safety | Recommendations (food, lifestyle) to move toward a safe path (longevity, disease-free or best outcome). |
| Anti-aging / slow-aging | Explicit goals; part of staying in a safe region. |
| Early signals | Symptoms/signs that are early indicators of disease; we model and use them for early action. |
| Foods that reduce / avoid | ALLEVIATES vs AGGRAVATES for those signals; recommend vs restrict with evidence. |
| Before or while on medication | Act early so they can prepare and, when possible, avoid or delay the need to see a doctor. |
