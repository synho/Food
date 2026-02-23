# Tiered Access (Free vs Paid)

Design so **free** and **paid** tiers can be added later without re-architecting. See `docs/PRICING_AND_MONETIZATION.md`.

## Current State

- All endpoints are **open** (no auth required). Request body carries user context.
- Optional header **`X-Plan`** (or query `plan`) can be set to `free` | `paid` for future use. Default: `free`.

## Later Additions (when monetizing)

1. **Auth**: Attach user/account to request; resolve plan from subscription or role.
2. **Rate limits**: Apply different limits by plan (e.g. free: N requests/day; paid: higher or unlimited).
3. **Feature flags**: Restrict certain endpoints or response fields by plan (e.g. wearables data only for paid).
4. **Middleware**: Read `X-Plan` or resolved plan from auth; set `request.state.plan` so services can branch if needed.

## Implementation Hook

- In `main.py`, an optional dependency or middleware can read `X-Plan` and set `request.state.plan = "free" | "paid"`.
- Services remain stateless; when we add limits or flags, we check `request.state.plan` (or a passed-in context) and apply rules.

No rate limiting or feature gating is implemented yet; this document describes the intended extension point.
