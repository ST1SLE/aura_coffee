## Context

Phase 1 (`customer-auth`, `sms-otp`) built the `users` / `user_profiles` schema and the customer-scoped OTP login flow. Phase 2 (`user-profile-api`) gave customers a `/api/v1/profile` surface over their own row. Phase 3–5 stacked orders, loyalty, promocodes. Phase 6 (`admin-panel`) now requires the admin to triage, block, unblock, and credit arbitrary users — today there is no endpoint that does any of these things.

The existing customer-scoped `/api/v1/profile/*` routes enforce `sub == user_id`. Staff cannot reuse them — either we branch on role inside customer code (leaking INV-010) or we disable the `sub` filter (wrong). A dedicated `/api/v1/admin/users/*` prefix wired to `{ADMIN}` only keeps INV-010 crisp.

For the block cascade, the Order Cancellation Chain (PDD §7.6) is already implemented in `core_api.services.order_cancel.cancel_order` — it owns refund enqueue, loyalty REVERSAL, promocode decrement, SMS notification, and commits its own per-order transaction. The block path MUST delegate and MUST NOT duplicate that logic (INV-004's per-order scope is already guaranteed by `cancel_order`).

This RED change is a pure test-authoring change: it locks the HTTP contract, the service API, the DTOs, and the RBAC matrix for `admin-users-api` before any implementation exists. Per AGENTS.md Two-Change Model, the change MUST end with every new test failing and every pre-existing test still passing.

**Affected modules:** `[core-api]`.

## Goals / Non-Goals

**Goals:**
- Author failing tests that pin every bullet of the `admin-users-api` capability against PDD §4.5, §6.5 (User Account Lifecycle), §7.1 Phase 6 item 2, §7.6 (Order Cancellation Chain), INV-004, INV-010, INV-013.
- Lock the query semantics for list: `status ∈ {"active","blocked","pending_verification","deleted","all"}` with default `"all"`, optional `search` string (prefix match, case-insensitive, `display_name` ONLY — NEVER `phone_hash`), `page ≥ 1`, `per_page ∈ [1, 100]`, sort `users.created_at DESC`.
- Lock the state-machine gates from PDD §6.5 per endpoint:
  - `block`: `{ACTIVE, BLOCKED}` accepted (BLOCKED → idempotent 200); `{PENDING_VERIFICATION, DELETED}` → 409 "invalid_user_state".
  - `unblock`: `{ACTIVE, BLOCKED}` accepted (ACTIVE → idempotent 200); `{PENDING_VERIFICATION, DELETED}` → 409.
  - `loyalty/adjust`: `{ACTIVE, BLOCKED}` accepted; `{PENDING_VERIFICATION, DELETED}` → 409.
  - Detail: `deleted_at IS NOT NULL` tombstone → 404 (INV-013).
- Lock the RBAC matrix: all 5 new routes SHALL be allowed for `{ADMIN}` only and denied for `{CUSTOMER, BARISTA, COURIER}`.
- Keep the RED signal clean: target-module imports SHALL live inside test bodies so a missing implementation fails per test, not at collection.
- Reuse the existing factory conventions (`_factories/loyalty.py`, `_factories/orders.py`) — add a small `_factories/admin_users.py` helper rather than duplicating setup across test modules.

**Non-Goals:**
- Writing any service function, router, schema, or `main.py` wiring (GREEN phase).
- Modifying the customer-scoped `/api/v1/profile/*` routes — they remain strictly `sub`-filtered.
- Adding a DELETE user endpoint (§6.5 ACTIVE→DELETED is the customer self-delete path, out of scope for Phase 6 admin).
- Introducing new ORM fields, indexes, or migrations — the existing `users`, `user_profiles`, `loyalty_accounts`, `loyalty_transactions`, `orders` schemas suffice.
- Exposing phone / `phone_hash` in any response (INV-013 — `phone_hash` is one-way).
- Phone-based admin search — `phone_hash` is not reversible.
- Admin UI (web-admin) — lands in a separate frontend change.

## Decisions

### D1 — New capability `admin-users-api`, not a delta to `user-profile-api`

**Decision:** Introduce `admin-users-api` as a NEW capability.
**Why:** `user-profile-api` is customer-scoped by construction (`sub == user_id`). The admin surface has a different filter set (no `sub` filter), different RBAC row, different DTO shape (`UserDetailResponse` with `active_orders_count` + last-20 loyalty txs), and write transitions the customer cannot invoke. Folding these under `user-profile-api` would require MODIFIED markers on every requirement in that spec. A fresh capability keeps the two surfaces separately reviewable.
**Alternative:** MODIFIED delta on `user-profile-api`. Rejected — the overlap is narrow (the existing `/api/v1/profile` routes stay intact) and the admin surface is large enough to stand alone.

### D2 — Service module placement: new `services/admin_users.py`

**Decision:** The five service functions (`list_users`, `get_user_detail`, `block_user`, `unblock_user`, `adjust_loyalty`) SHALL live in a new module `core_api.services.admin_users`. RED tests import from that module inside test bodies.
**Why:** Unlike `admin-orders-api` (where staff helpers reused the customer `list_orders` ORM wiring and shared the `OrderListResponse` DTO), the admin-users surface has its own dedicated DTOs, joins (`users ⨝ user_profiles ⨝ loyalty_accounts`), and write paths that do not overlap with anything in `services/profile.py` or `services/loyalty.py`. A sibling module keeps the admin and customer code paths from tangling.
**Alternative:** colocate in `services/profile.py`. Rejected — profile service is strictly customer-scoped and mixing admin writes with customer reads muddies INV-010 audit trails.

### D3 — Tests MUST fail via `ImportError` / `KeyError`, not via collection failure

**Decision:** Every RED test SHALL import `core_api.services.admin_users` (and any DTOs from `core_api.schemas.admin_users`) inside the test body — not at module top-level. Router tests SHALL first probe `app.routes` rather than relying on HTTP-level 404s. RBAC tests SHALL index `ROUTE_MATRIX[(...)]` directly and expect `KeyError` until GREEN lands.
**Why:** Module-level imports of missing symbols abort the whole test file and hide which scenarios are unlocked. Body-local imports keep the RED report granular — GREEN flips each test individually.
**Alternative:** Stub empty functions to satisfy imports. Rejected — adds implementation scaffolding to a RED change, blurring the contract.

### D4 — Test fixtures: reuse `db_client` + `{admin,barista,customer,courier}_headers` + `db_session`

**Decision:** Router tests SHALL use the existing `db_client` fixture (migrated Postgres + `TestClient`) together with the role-keyed header fixtures from `tests/conftest.py`. Service-level tests SHALL use the functional `db_session` fixture (savepoint-wrapped Postgres). Seeding SHALL happen through a new `tests/_factories/admin_users.py` helper that builds `User + UserProfile + LoyaltyAccount (+ optional orders)` in deterministic combinations.
**Why:** Matches the existing router/service test split (`test_admin_orders_*`, `test_admin_promocodes_*`). No new auth harness needed — admin JWTs from `admin_headers` hit the RBAC middleware correctly. The savepoint-wrapped `db_session` is required because several block/loyalty tests issue `session.commit()` mid-flow; without the savepoint wrap these commits leak into sibling tests (already seen in admin-orders tests).

### D5 — `search` is prefix match on `display_name` ONLY — never on `phone_hash` (INV-013)

**Decision:** The `search` query parameter SHALL resolve to a case-insensitive prefix match against `user_profiles.display_name` using `LOWER(display_name) LIKE LOWER(?) || '%'`. `phone_hash` SHALL NOT appear anywhere in the search predicate. RED tests assert both the positive (search finds user with display_name starting with term) and the negative (search MUST NOT find users by phone fragment).
**Why:** `phone_hash` is one-way (SHA-256 of canonicalized phone, INV-013). Even a full phone match requires hashing client-side — partial match is impossible and the DB column MUST NOT be exposed to prefix-match logic that could leak equality side-channels.
**Alternative:** Full-text search across profile fields. Rejected — MVP scope; `display_name` prefix covers the operator's use case (finding a specific customer by name).

### D6 — Sort order for list: `users.created_at DESC`

**Decision:** `GET /api/v1/admin/users` SHALL sort rows by `users.created_at DESC`.
**Why:** Admin operators typically look at recent signups first (fraud triage, onboarding issues). No secondary sort needed in MVP — ties on `created_at` are astronomically rare at single-location scale.

### D7 — `block` endpoint: delegate cascade to `cancel_order`, filter to admin-cancellable statuses

**Decision:** `POST /api/v1/admin/users/{user_id}/block` SHALL:
1. `SELECT … FOR UPDATE` on the user row;
2. gate on PDD §6.5: `{PENDING_VERIFICATION, DELETED}` → 409 "invalid_user_state"; `BLOCKED` → 200 idempotent `{user_id, status: "blocked", cancelled_orders_count: 0}`;
3. otherwise UPDATE `users.status = BLOCKED`, flush;
4. SELECT orders `WHERE user_id = ? AND status IN (CREATED, PAID, PREPARING, READY)` (note: `IN_DELIVERY` is EXCLUDED — see D8);
5. for each order, call `core_api.services.order_cancel.cancel_order(order_id=o.id, cancelled_by='admin', reason='user_blocked', db_session=db)`;
6. WARN-log if the cancelled count exceeds 10 (operational signal for Phase 6 ops review);
7. return `BlockUserResponse(user_id=..., status="blocked", cancelled_orders_count=N)`.

**Why:** `cancel_order` is the single source of truth for §7.6 (refund enqueue, loyalty REVERSAL, promocode decrement, order-status SMS). Duplicating any of that logic inside `block_user` would create two divergent cancel paths. INV-004's atomicity is per-order and already lives inside `cancel_order` (it commits per call). The block endpoint therefore accepts per-order atomicity instead of a single mega-transaction — this is an explicit user-confirmed design choice.
**Alternative:** Single mega-transaction over N cancels. Rejected — requires modifying `cancel_order` to accept `commit=False`, which the task explicitly forbids ("НЕ трогать services/order_cancel.py").

### D8 — IN_DELIVERY orders SHALL be skipped silently by block cascade

**Decision:** `block_user` SHALL filter the cascade set to `{CREATED, PAID, PREPARING, READY}` — `IN_DELIVERY` is NOT included. IN_DELIVERY orders remain in flight; the courier completes the delivery normally.
**Why:** (1) PDD §7.6 forbids admin cancellation of `{IN_DELIVERY, COMPLETED, CANCELLED}` — feeding IN_DELIVERY to `cancel_order` would raise `OrderCancelError`. (2) Operationally the goods are already on the way; cancelling mid-delivery has no recovery path in MVP. (3) The user's block takes effect immediately (no new orders); historical IN_DELIVERY completes without friction. User-confirmed decision.
**Alternative (A)** Include IN_DELIVERY in the cascade — rejected (see above).
**Alternative (B)** 409 the whole block if any IN_DELIVERY order exists — rejected (the admin's goal is to stop future activity, not to wait for couriers).

### D9 — `unblock` endpoint: flip BLOCKED→ACTIVE, idempotent on ACTIVE, 409 elsewhere, NO cascade

**Decision:** `POST /api/v1/admin/users/{user_id}/unblock` SHALL:
1. `SELECT … FOR UPDATE` on the user row;
2. `{PENDING_VERIFICATION, DELETED}` → 409 "invalid_user_state";
3. `ACTIVE` → 200 idempotent no-op (no state change);
4. `BLOCKED` → UPDATE `users.status = ACTIVE`, commit, 200.
No cascade — cancelled orders stay cancelled (unblocking is a user-state decision, not an order-state decision).
**Why:** Symmetric to D7's idempotency semantics; PDD §6.5 only lists BLOCKED→ACTIVE. Orders that were cancelled during block DO NOT resurrect — that would break §6.1 (COMPLETED/CANCELLED are terminal, INV-016).

### D10 — `loyalty/adjust`: single-transaction INV-004, allowed for BLOCKED users

**Decision:** `POST /api/v1/admin/users/{user_id}/loyalty/adjust` SHALL:
1. Validate body `{delta: int != 0, reason: str len ∈ [1, 500]}` at the Pydantic layer (422 on violation);
2. `SELECT … FOR UPDATE` on `loyalty_accounts` row;
3. gate on PDD §6.5: `{PENDING_VERIFICATION, DELETED}` → 409 "invalid_user_state"; `{ACTIVE, BLOCKED}` accepted;
4. `new_balance = current_balance + delta`; if `new_balance < 0` → 422 "insufficient_balance";
5. UPDATE `loyalty_accounts.balance = new_balance`;
6. INSERT `LoyaltyTransaction(user_id, order_id=NULL, type=ADMIN_ADJUSTMENT, amount=delta, balance_after=new_balance, description=reason)`;
7. `db.commit()`;
8. return `LoyaltyAdjustResponse(transaction_id=..., new_balance=..., delta=...)`.

BLOCKED users SHALL be accepted because a common admin workflow is "refund the customer their points and then unblock" — rejecting BLOCKED here would force the operator into an ugly unblock-adjust-reblock dance.

**Why:** Single `db.commit()` at the end with `SELECT … FOR UPDATE` is exactly the INV-004 atomicity pattern already used by `cancel_order._reverse_points`. The `LoyaltyTransaction` model already allows `order_id=NULL` (see `shared/models/loyalty_transaction.py:26` comment "Админские корректировки могут быть без order_id").

### D11 — New schemas in `core_api.schemas.admin_users`

**Decision:** Add `UserSummary`, `UserListResponse`, `UserDetailResponse`, `LoyaltyTransactionItem`, `BlockUserResponse`, `LoyaltyAdjustRequest`, `LoyaltyAdjustResponse` in a new file `core_api/schemas/admin_users.py`. Unlike `admin-orders-api` (which reused `schemas.order_history` DTOs), the admin-users response shapes do NOT overlap any existing schema — `UserDetailResponse` in particular composes loyalty + orders count, which no other DTO offers.
**Why:** New surface, new DTOs. Schema tests SHALL live in the router test modules (import inside test body, build instances from kwargs, assert field names).

### D12 — RBAC matrix: 5 new rows, all `{ADMIN}`

**Decision:** Add to `core_api/rbac_matrix.py::ROUTE_MATRIX`:

```python
("GET",  "/api/v1/admin/users"):                                  {ADMIN},
("GET",  "/api/v1/admin/users/{user_id}"):                        {ADMIN},
("POST", "/api/v1/admin/users/{user_id}/block"):                  {ADMIN},
("POST", "/api/v1/admin/users/{user_id}/unblock"):                {ADMIN},
("POST", "/api/v1/admin/users/{user_id}/loyalty/adjust"):         {ADMIN},
```

None of these SHALL appear in `PUBLIC_ROUTES`. Barista / courier SHALL NOT be added — admin-users is strictly admin scope per INV-010.

## Atomicity Analysis (INV-004)

Two write paths touch financial state:

1. **`block_user` cascade.** Per-order atomicity lives inside `cancel_order` (each call is its own DB transaction, committing points + promo + payment mutations together). The block endpoint invokes `cancel_order` sequentially for each of the N admin-cancellable orders. If call #k fails, call #1..k-1 have already committed; the user row's BLOCKED state is committed with call #1's transaction. **User-status and cascade DO NOT share a single transaction** — this is an explicit, user-confirmed design choice. INV-004's scope is per-order financial atomicity, which is preserved by delegation.

2. **`adjust_loyalty`.** Single DB transaction containing `SELECT ... FOR UPDATE` on `loyalty_accounts`, the balance UPDATE, the `LoyaltyTransaction` INSERT, and `db.commit()`. Matches the atomicity shape of `cancel_order._reverse_points`. Concurrent adjust calls on the same user are serialized by the row lock; the second call sees the first's committed balance.

RED tests SHALL NOT assert INV-004 compliance directly (the RED phase is pre-implementation). GREEN tests SHALL cover:
- Happy-path adjust: balance field updated, transaction row inserted, both visible post-commit.
- Insufficient balance: neither the UPDATE nor the INSERT lands (rollback).
- Concurrent adjust: RED adds a placeholder (skip-marked) test; GREEN unskips if time permits.

## State Machine References (PDD §6.5)

All user-state writes in this change reference PDD §6.5 User Account Lifecycle.

| Endpoint | Current State | New State | Condition | Status |
|----------|---------------|-----------|-----------|--------|
| `block`  | `ACTIVE`      | `BLOCKED` | always    | 200    |
| `block`  | `BLOCKED`     | `BLOCKED` | idempotent| 200    |
| `block`  | `PENDING_VERIFICATION` | — | forbidden | 409 "invalid_user_state" |
| `block`  | `DELETED`     | —         | forbidden | 409 "invalid_user_state" |
| `unblock`| `BLOCKED`     | `ACTIVE`  | always    | 200    |
| `unblock`| `ACTIVE`      | `ACTIVE`  | idempotent| 200    |
| `unblock`| `PENDING_VERIFICATION` | — | forbidden | 409 "invalid_user_state" |
| `unblock`| `DELETED`     | —         | forbidden | 409 "invalid_user_state" |

Per INV-016, any state not listed above is a forbidden transition — tests SHALL assert 409 on each.

`loyalty/adjust` is NOT a user-state transition (user.status unchanged); it is gated on the user-state precondition `∈ {ACTIVE, BLOCKED}`.

`block` also triggers §6.1 order transitions `{CREATED, PAID, PREPARING, READY} → CANCELLED` via delegation to `cancel_order`. Tests SHALL NOT re-verify §7.6 chain — the existing `test_order_cancel.py` suite covers that. Tests SHALL assert that cancels happen (count matches) and that COMPLETED/CANCELLED/IN_DELIVERY orders are untouched.

## 152-FZ Compliance (INV-013)

Admin access to user account data is a legitimate business purpose under 152-FZ (fraud triage, dispute resolution, customer support). Access is gated by the ADMIN role (INV-010) and logged at the transport layer via standard request logging.

- `phone` (encrypted column in `user_profiles`) SHALL NOT be returned in any response in this change. Admin can see `display_name` only.
- `phone_hash` (SHA-256 on the `users` row) SHALL NOT be returned and SHALL NOT be searchable — the `search` query parameter is strictly prefix-match over `display_name`.
- Tombstone users (`users.deleted_at IS NOT NULL`, INV-013 — PII anonymized on account deletion) SHALL return 404 from the detail endpoint, as their PII has been stripped.
- `user_id` is an opaque UUID and SHALL be used as the sole external identifier in responses.

## Risks / Trade-offs

- **[Risk]** Non-atomic block cascade: if `cancel_order` fails on order #k (e.g. Celery broker down for refund enqueue), orders #1..k-1 are cancelled and user is BLOCKED, but orders #k..N are not. → **Mitigation:** `cancel_order`'s own failure contract is "raise, do not partially commit". The block endpoint SHALL surface the first failure as HTTP 500 with a structured detail that includes `partial_cancel_count`. Operator re-runs the block → idempotent on the user row, cancel loop continues from where it stopped (other active orders still in cancellable statuses). Accepted trade-off; alternative (full rollback) requires modifying `cancel_order` which is out of scope.
- **[Risk]** RBAC middleware not seeing the new router at collection time could make 403 tests flaky. → **Mitigation:** main.py wiring goes through the same router-registration pattern as existing admin routers; RED tests assert route presence in `app.routes` (expect 0 in RED, 1 in GREEN).
- **[Risk]** Loyalty `adjust` on a user without a `LoyaltyAccount` row would `SELECT ... FOR UPDATE` a missing row. → **Mitigation:** All tests in this RED change SHALL seed the `LoyaltyAccount` explicitly via `_factories/loyalty.make_user_with_loyalty`. The "what happens when no loyalty_account row exists" behavior is deferred to an Open Question and left for GREEN to decide; no RED scenario exercises that path.
- **[Trade-off]** Locking `per_page ≤ 100` in RED forbids future expansion without a spec delta. Accepted — spec deltas are cheap; silent widening is not.
- **[Trade-off]** Accepting loyalty adjustments on BLOCKED users slightly expands the "what a blocked user's record can look like" surface. Accepted — explicitly required by the task ("заблокированному тоже можно корректировать").

## Migration Plan

No schema change, no data migration. All new columns used (`users.status`, `users.deleted_at`, `user_profiles.display_name`, `loyalty_accounts.balance`, `loyalty_transactions.*`, `orders.status`) already exist and are indexed per Phase 1–5 migrations.

Forward-only deployment; rollback is `git revert` of the GREEN change.

## Open Questions

- **Naming of the `search` parameter semantics in OpenAPI docs**: prefix vs. substring. RED tests pin **prefix** per D5. GREEN MAY propose a change-of-semantics only via a spec delta. Closed for RED.
- **Auto-creating `LoyaltyAccount` in `adjust_loyalty`**: behaviour when `loyalty_accounts` row is absent is UNDEFINED in RED. GREEN SHALL pick between auto-create-then-adjust, 404, or 409 and add a spec delta if needed. RED tests seed the row explicitly and do not exercise the absent path.
- **Pagination total_count sanity cap**: none in MVP. If the user base grows past ~100k, a COUNT(*) on `users` will become a hot spot. Post-MVP topic.
