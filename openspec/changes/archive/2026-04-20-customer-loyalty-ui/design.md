## Context

Affected modules: **[web-customer]** only.

Backend loyalty endpoints (`GET /api/v1/profile/loyalty`, `GET /api/v1/profile/loyalty/transactions`) and Pydantic schemas (`services/core-api/app/schemas/loyalty.py`) already exist (PDD §3, §4.4). The customer SPA currently has no loyalty surface — `/profile` shows language and logout only, and there is no route to view points or history.

This change adds read-only customer-facing UI mirroring the shape of the existing `/profile/addresses` flow (which is the sibling pattern in `web/customer/src/pages/Profile/Addresses/`) and of `OrderHistoryPage` from phase 3.5 (which establishes the infinite-pagination pattern).

## Goals / Non-Goals

**Goals:**
- Customer MUST be able to view current balance and lifetime accrued total on `/profile/loyalty`.
- Customer MUST be able to paginate through their loyalty transaction history.
- `/profile` MUST show a summary card with balance and a link to `/profile/loyalty`.
- Single React Query cache key MUST be reused between `LoyaltyCard` (on `/profile`) and `LoyaltyPage` so navigation does not refetch balance unnecessarily.

**Non-Goals:**
- Redeeming points (spending happens only at checkout, separate change).
- Realtime balance updates via polling or WebSocket.
- Admin adjustment UI.
- Exporting transaction history.
- Backend changes — endpoints and schemas already exist.

## Decisions

### D1. Balance value is an integer count of points (not kopecks)
Points are tracked as whole units where 1 point = 1 ₽ per PDD §3. API returns integers; UI renders them directly with no division by 100. Alternative considered: treat as kopecks to match price formatting — rejected because backend schema already uses point units and dual representation would invite bugs.

### D2. One React Query key for balance, separate key for transactions
- Balance query key: `['loyalty', 'balance']` — shared between `LoyaltyCard` and `LoyaltyPage` header.
- Transactions query key: `['loyalty', 'transactions']` (infinite) — only used on `LoyaltyPage`.

Rationale: navigating `/profile` → `/profile/loyalty` reuses the balance cache (no flash/refetch), while transactions stay scoped to the detail page.

### D3. Infinite pagination, not page-number pagination
Matches `OrderHistoryPage` from phase 3.5. `useInfiniteQuery` with `per_page=20`; `getNextPageParam` returns `page + 1` when `items.length === per_page` (i.e., page was full). Alternative considered: classic `?page=N` with numbered controls — rejected for consistency with sibling history page and mobile-first UX.

### D4. Transaction row layout is three-column flex
Left: date + localized type label. Center: optional description + order link. Right: amount + `balance_after`. Empty center collapses on mobile. Amount color rules:
- `amount > 0` → green (accrual, reversal that credits back)
- `amount < 0` → red (redemption, admin_adjustment that debits)
- `amount === 0` → black

Rule is driven by the signed `amount` value itself, not by `type`, so future transaction types work without UI changes.

### D5. Order short-id is `uuid.slice(0, 8)`
Same convention as `customer-orders-ui`. Link target is `/orders/{full_uuid}`, displayed label is `#{short}`.

### D6. Zod runtime validation on API responses
Mirrors `api/addresses.ts` and `api/orders.ts`. Schema types are derived from zod via `z.infer` so TypeScript and runtime validation share one source of truth with backend shape.

## Risks / Trade-offs

- [Risk] Backend response shape differs from what this UI expects → Mitigation: zod validation fails loud with a visible error; contributors can re-check `services/core-api/app/schemas/loyalty.py` before wiring.
- [Risk] Infinite scroll tests are flaky if `IntersectionObserver` isn't mocked → Mitigation: reuse the `OrderHistoryPage` test pattern — explicit "Load more" button as a fallback / test hook rather than pure scroll trigger.
- [Risk] Balance drift between card and page → Mitigation: shared React Query key (D2); no local duplication of state.

## Atomicity Analysis (INV-004)

This change is **read-only** — no financial mutations, no point accrual, no redemption. Balance is computed server-side as `SUM(amount)` over `LoyaltyTransaction` rows within the existing endpoint. INV-004 (atomicity of points + promo + payment) continues to apply to the checkout path, which is out of scope here.

## Migration Plan

Feature-flag-free, additive UI only. Rollback = revert the PR; no data, schema, or API changes.

## Open Questions

None — backend contract is frozen by existing schemas in `services/core-api/app/schemas/loyalty.py`, and UI patterns are established by sibling `Profile/Addresses/` and phase 3.5 `OrderHistoryPage`.
