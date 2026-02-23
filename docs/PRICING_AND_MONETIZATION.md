# Pricing & Monetization

**유료화 전략·상세 가격 모델은 추후 추가 예정.** 아래는 방향성과 설계 원칙만 정리.

## Direction

- **Initially**: Use is **almost free** — so we can grow adoption, gather feedback, and prove value. Free tier or very low cost is the default in the early phase.
- **Later**: The product is developed so it can become an **app users pay to use** (e.g. subscription or one-time purchase). We design the system from the start to support **tiered access** (free vs paid) without a big rewrite.

---

## Principles

1. **Start free (or nearly free)**  
   Early users get most or all features at no or minimal cost. This builds trust and usage before monetization.

2. **Design for paid later**  
   Server, APIs, and clients should be built so we can introduce **plans** (e.g. free / premium) later: e.g. usage limits, feature flags, or premium-only features (e.g. wearables, deeper personalization, export). No need to implement billing in day one, but **architecture should allow** it (e.g. user/account with plan or role, API checks).

3. **Clear value for paying users**  
   When we add paid tiers, paying users should get clearly better value: e.g. more recommendations per month, wearables sync, saved history, priority support, or advanced insights — always aligned with evidence and our zero-error stance.

4. **Transparent and fair**  
   Pricing and limits (if any) should be clear. Free tier remains useful so non-paying users still get real benefit.

---

## Implementation Notes (for later)

- **Accounts**: User accounts (or anonymous with limits) so we can associate usage with a plan. Auth can be added when we turn on monetization.
- **Plans**: e.g. **Free** (limited requests/month or basic guidance only) and **Premium** (full features, wearables, unlimited or higher caps). Exact limits and features TBD when we turn on monetization.
- **Server**: Implemented hook for tiered access. APIs accept optional header **`X-Plan`** (`free` | `paid`); middleware sets `request.state.plan`. When adding paid use: (1) resolve plan from auth/subscription, (2) add rate limits by plan (e.g. free: N req/day), (3) add feature flags (e.g. wearables data only for paid). See `server/TIERED_ACCESS.md`.
- **Billing**: No billing logic in repo yet. When ready: integrate payment (e.g. Stripe for web subscription; in-app purchase for mobile); server checks subscription status and sets plan for API layer.
- **App stores**: When we ship the mobile app, paid use may go through **in-app purchase** (subscription) or external payment; design so we can plug in either.

---

## Summary

| Phase | Approach |
|-------|----------|
| **Initial / early** | Use is **almost free**; focus on adoption and value. |
| **Later** | **Paid use** (e.g. subscription); we design server and product so tiered access (free vs paid) can be added without re-architecting. |
