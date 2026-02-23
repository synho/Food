# Mobile App (Phase 5)

## Goal

A **mobile app** (e.g. React Native, Flutter) that consumes the **same server APIs** as the web client. No new backend; same contracts, same zero-error evidence, same user context.

## API Contract (unchanged)

- **Base URL**: Configure per environment (e.g. production API URL).
- **Endpoints**: Same as web. See [API_AND_SERVER.md](./API_AND_SERVER.md) and `server/README.md`.
  - `POST /api/recommendations/foods` — body: `UserContext`
  - `POST /api/health-map/position`
  - `POST /api/health-map/safest-path`
  - `POST /api/guidance/early-signals`
  - `POST /api/guidance/general`
- **Request**: JSON body = `UserContext` (age, conditions, symptoms, goals, location, way_of_living, culture, etc.; all optional).
- **Response**: Same DTOs (recommendations with evidence, position, steps, early signals, general guidance). **Term standardization**: use canonical names in UI (same as server).

## Tech Options

- **React Native**: Reuse TypeScript types from `web/lib/types.ts` (or a shared package); same API client pattern.
- **Flutter**: Define equivalent models and call REST API; same contracts.
- **Auth / plan**: When we add auth and tiered access, the app sends the same `X-Plan` header (or token that implies plan); server applies rate limits or feature flags. See [PRICING_AND_MONETIZATION.md](./PRICING_AND_MONETIZATION.md) and `server/TIERED_ACCESS.md`.

## UX (aligned with web)

- Input flow: age, conditions, symptoms, goals (optional); easy to add more (place, lifestyle, culture).
- Output: Recommended foods, restricted foods, position & nearby risks, safest path, early-signal guidance, general guidance.
- Evidence display: Every recommendation/restriction shows source (journal, date) and context. Trust badges: **blue** (Information), **green** (Knowledge), **gold** (Wisdom) per project rules.

## Wearables (보류)

- **현재는 넣지 않음.** Apple Watch, Apple Health, Google Fit 등 웨어러블 연동은 추후 검토. 필요 시 [USER_CONTEXT_AND_COLLECTION.md](./USER_CONTEXT_AND_COLLECTION.md) 참고.

## Placeholder

- Repo may contain a `mobile/` directory (or separate repo) when the app is started. Until then, this doc and the server API define the contract for any future mobile client.
