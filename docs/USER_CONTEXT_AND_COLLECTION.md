# User Context & Data Collection

## Why Context Matters

**Where they live, how they live, age, and culture** should all be reflected so we can provide **more accurate and safer** information. The more context we have (with user consent), the better we can:

- Align recommendations with **local food availability**, season, and region-specific evidence.
- Respect **cultural** and **dietary** preferences (e.g. halal, vegetarian, traditional cuisines).
- Tailor guidance to **way of living** (e.g. sedentary vs active, work schedule, cooking habits).
- Use **age** and **life stage** for aging/biology and risk layers.

We do **not** force users to give everything. The product should be designed so that **more information is easy to provide** when the user wants to — and, where appropriate, we **obtain consent and automatically discover** information to improve accuracy and safety.

---

## Principles

### 1. Reflect place, lifestyle, age, culture

- **Place of living**: Location (country, region, city) for local food, season, and future grocery/availability.
- **Way of living**: Daily routine, activity level, work pattern, cooking access, eating habits — so recommendations are feasible and safe.
- **Age**: Life stage, aging layer, risk stratification (already in scope).
- **Culture**: Dietary traditions, restrictions, preferences, language — so guidance is relevant and respectful.

All of this is used to **filter and align** the health map and recommendations (layers, evidence, local options). More context → more accurate, safer guidance.

### 2. Don’t force; make it easy to add more

- We do **not** require every field. Minimum viable context (e.g. age + a few symptoms or goals) can still yield useful guidance.
- **Progressive disclosure**: The product should make it **easy** to add more information when the user is willing — e.g. optional steps (“Add where you live for local tips”), clear benefits (“More accurate recommendations”), low friction (dropdowns, one-tap where possible).
- No pressure: we invite, we don’t force.

### 3. Consent-based auto-discovery

- **With user consent**, we should be able to **automatically find** information where possible:
  - **Location**: e.g. IP-based region or device location (with permission).
  - **Time / season**: device time zone and date for seasonality.
  - **Language / locale**: for UI and, where applicable, cultural assumptions.
  - (Future) **Wearables and health devices**: e.g. **Apple Watch**, Garmin, Fitbit, or health app exports (Apple Health, Google Fit) — activity, heart rate, sleep, steps, etc. Only with **explicit consent** and clear explanation of how we use the data to improve position prediction and recommendations. We’d like to support this later so users can get more accurate, personalized guidance.
- **Consent first**: Every auto-discovered data type must be **explained and agreed** (e.g. “Use my location to suggest foods available near me”). User can enable/disable by category.
- **Transparency**: Show what we inferred and let the user correct or remove it.

---

## Implementation Notes

- **User context schema**: Extend profile to include optional `location` (structured or free text), `lifestyle` / `way_of_living` (tags or free text), `culture` / `dietary_culture` (e.g. vegetarian, halal, Mediterranean), plus existing age, gender, ethnicity, conditions, symptoms, goals.
- **APIs**: Accept partial context; recommendations and health map endpoints use whatever context is present and degrade gracefully when less is available.
- **UX**: Onboarding or settings can offer “Add more for better recommendations” with clear, optional steps (place, lifestyle, culture); toggles for “Use my location,” “Use my time zone,” etc., with consent and explanation.
- **Privacy**: Store and use only what user provides or consents to; document in privacy policy; allow export and deletion.

---

## Wearables (e.g. Apple Watch) — Future

We’d like to support **integration with wearables** such as **Apple Watch** (and similar devices or health apps) in the future. With user consent, data such as activity, heart rate, sleep, steps could be used to:

- Refine **position on the health map** (e.g. activity level, recovery, sleep quality).
- Personalize **safest path** and food/lifestyle recommendations (e.g. more protein if activity is high; sleep hygiene if sleep data suggests issues).
- Support **early signal** awareness (e.g. trends that might align with early signs, always with evidence and never as a substitute for medical advice).

Integration would be **opt-in only**, with clear consent and transparency; same server and APIs would consume this as additional context. Web and app would both benefit once the backend accepts wearable-derived context.

---

## Summary

| Principle | Meaning |
|----------|--------|
| **Reflect place, lifestyle, age, culture** | All of these improve accuracy and safety of guidance; we use them to align layers and recommendations. |
| **Don’t force; make it easy** | We don’t require everything; we make it easy to add more (progressive, low-friction, benefit explained). |
| **Consent-based auto-discovery** | With permission, we automatically find what we can (e.g. location, time zone); consent first, transparency, user control. |
