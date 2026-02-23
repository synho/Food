# Health Navigation — Mobile App (placeholder)

Future **mobile app** (React Native or Flutter) consuming the same Health Navigation server APIs.

- **API contract**: See `docs/API_AND_SERVER.md` and `server/README.md`. All endpoints accept `UserContext` (JSON body) and return recommendations, position, safest path, early-signal guidance, and general guidance with evidence.
- **Design**: See `docs/MOBILE_APP.md` (same APIs as web, term standardization, trust badges, optional wearables later).
- **Tiered access**: 유료화 전략은 추후 추가. 필요 시 `X-Plan` 또는 auth; see `server/TIERED_ACCESS.md`, `docs/PRICING_AND_MONETIZATION.md`.

No app code in this repo yet; add a React Native or Flutter project here (or in a separate repo) when starting the mobile client.
