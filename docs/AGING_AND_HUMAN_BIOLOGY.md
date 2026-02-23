# Aging & Human Biology Layer

## Why This Layer

As we get older we **feel our body change** but often don’t know **why** or **when** it happens. The platform should:

- **Collect general human biology and aging knowledge** (normative changes across the life course).
- **Provide general guidance** that applies even when the user has no specific disease.
- **Explain why** they need to pay attention to **what they eat**, **exercise**, and other lifestyle factors — with evidence.

This gives users context for their own experience and motivates diet and exercise through **understanding**, not just “do this.”

---

## Goals

1. **What changes**: Document which biological systems and functions change with age (e.g. muscle mass, bone density, metabolism, cognition, sleep, immunity).
2. **When**: Link changes to life stage or age bands (e.g. 30s, 40s, 50s, 60s+) where evidence supports it.
3. **Why it matters**: Connect each change to **actionable levers** (nutrition, exercise, sleep, etc.) and to risks if ignored (e.g. sarcopenia, osteoporosis).
4. **General guidance**: Serve “why pay attention” explanations and evidence-based guidance (food, exercise) by **age/life stage**, complementing disease-specific recommendations.

All of this should be **evidence-based** (from the same high-impact literature and KG) so we keep zero-error tolerance.

---

## Knowledge to Collect (Examples)

| Domain | Example changes | Why pay attention (levers) |
|--------|------------------|---------------------------|
| **Muscle & strength** | Sarcopenia, loss of strength from ~30s onward | Protein, resistance exercise; prevents frailty, falls. |
| **Bone** | Bone density peaks then declines; higher fracture risk with age | Calcium, vitamin D, weight-bearing exercise. |
| **Metabolism** | Slower metabolism, body composition shift | Diet quality, portion size, activity; weight and metabolic health. |
| **Cardiovascular** | Arterial stiffness, blood pressure tendency | Sodium, potassium, exercise; cardiovascular risk. |
| **Cognition** | Processing speed, memory (normative vs pathology) | Diet (e.g. Mediterranean), physical activity, sleep. |
| **Sleep** | Architecture changes, more awakenings | Sleep hygiene, light, caffeine; recovery and cognition. |
| **Immunity** | Immunosenescence | Nutrition (e.g. micronutrients), vaccination, exercise. |
| **Digestion** | Slower motility, absorption changes | Fiber, hydration, certain nutrients. |

We store these as **structured facts in the KG** (entities + relationships) so the server can generate “what’s changing,” “when,” and “why you should pay attention to diet and exercise” by age/life stage.

---

## KG Extension: Aging & Biology

### New or Extended Node Types

| Label | Description | Example |
|-------|-------------|--------|
| `BodySystem` | Organ system or physiological domain | Musculoskeletal, Cardiovascular, Metabolism |
| `AgeRelatedChange` | A normative change with age (not necessarily a disease) | Sarcopenia, Bone loss, Slower metabolism |
| `LifeStage` | Age band or life phase | 30s, 40s, 50s, 60s and older, Older adult |
| *(existing)* `Nutrient`, `Food`, `LifestyleFactor`, `Disease` | Used to link “why” and “what to do” | Vitamin D, Resistance exercise, Osteoporosis |

### New Relationship Types

| Relationship | From → To | Meaning |
|--------------|-----------|--------|
| `PART_OF` | AgeRelatedChange → BodySystem | Change belongs to this system |
| `OCCURS_AT` | AgeRelatedChange → LifeStage | When this change typically appears or accelerates (evidence-based) |
| `INCREASES_RISK_OF` | AgeRelatedChange → Disease | Unmitigated change raises risk of disease (e.g. bone loss → osteoporosis) |
| `MODIFIABLE_BY` | AgeRelatedChange → Nutrient / Food / LifestyleFactor | Diet or exercise can slow, prevent, or partly reverse the change |
| `EXPLAINS_WHY` | Nutrient / Food / LifestyleFactor → AgeRelatedChange | Why paying attention to this (e.g. protein, exercise) matters for this change |

Relationship properties: same evidence model — `source_id`, `context`, `journal`, `pub_date` (and optional `evidence_type`).

---

## Pipeline: Sourcing Aging & Biology Data

- **Same pipeline, different queries**: Use PMC (and high-impact journals) with search queries focused on **aging**, **life course**, **physiology**, **sarcopenia**, **bone health**, **metabolism and age**, etc.
- **Extraction**: Extend the extraction prompt (or add a dedicated pass) to pull:
  - Age-related changes (entity + body system + life stage when relevant).
  - Links from changes to nutrients, foods, exercise (MODIFIABLE_BY, EXPLAINS_WHY).
  - Links from changes to disease risk (INCREASES_RISK_OF).
- **Curated seed**: Optionally seed the KG with a small set of well-cited, textbook-level facts (with source) so we have baseline “general biology” even before many papers are processed. All still with source_id and context.

---

## Server / API: General Guidance by Age

- **Endpoint** (e.g. `GET /api/guidance/aging` or `GET /api/guidance/general?age=52`).
- **Input**: User’s age (and optionally gender, ethnicity for when evidence differs).
- **Returns**:
  - **Relevant age-related changes**: What typically happens at their life stage (with evidence).
  - **Why pay attention**: Short explanations (e.g. “Muscle mass declines from your 30s; protein and resistance exercise help preserve it”) with evidence.
  - **General guidance**: What to pay attention to (diet, exercise, sleep, etc.) and why, with links to KG (source_id, context, journal, date).
- **Integration**: This can be combined with the existing “general food guidance” and “safest path” so the UI shows both **disease-specific** and **age/life-course** reasons for diet and exercise.

---

## UX Angle

- Users see **their body’s story**: “Here’s what often changes at your stage of life, and why what you eat and how you move matter.”
- This supports **motivation** (understanding) and **trust** (evidence), and sets the stage for personalized food and exercise recommendations (recommended / restricted foods, safest path) that reference both disease and aging biology.
