## Why

The RED change `admin-users-api-red` (archived 2026-04-20) locked the contract for 5 staff-scoped endpoints under `/api/v1/admin/users/*` with 87 failing tests, but left implementation absent. The Phase 6 admin panel (PDD §7.1 item 2) still cannot list users, read loyalty history, block/unblock accounts, or make ADMIN_ADJUSTMENT loyalty corrections. Green-phasing this change unblocks the admin UI work (separate frontend change) and gives operators a sanctioned tool for the PDD §6.5 User Account Lifecycle ACTIVE↔BLOCKED transitions.

MVP phase: **Phase 6 — Admin Panel** (PDD §7.1 item 2).

## What Changes

- Implement `core_api.services.admin_users` with 5 service functions:
  - `list_users(db, *, status, search, page, per_page) -> UserListResponse` — filters by status, prefix-searches `user_profiles.display_name` (case-insensitive), excludes tombstones unless `status in {"all", "deleted"}`, orders by `users.created_at DESC`.
  - `get_user_detail(db, user_id) -> UserDetailResponse` — joins User + UserProfile + LoyaltyAccount + last-20 LoyaltyTransaction + active_orders_count; raises `UserNotFoundError` for missing / tombstoned users (INV-013).
  - `block_user(db, user_id) -> BlockUserResponse` — SELECT … FOR UPDATE user; flips ACTIVE→BLOCKED; cascades `cancel_order(cancelled_by="admin", reason="user_blocked")` for orders in `{CREATED, PAID, PREPARING, READY}`; idempotent on BLOCKED; 409 on `{PENDING_VERIFICATION, DELETED}` and tombstones.
  - `unblock_user(db, user_id) -> BlockUserResponse` — BLOCKED→ACTIVE, no cascade; idempotent on ACTIVE; 409 otherwise.
  - `adjust_loyalty(db, user_id, delta, reason) -> LoyaltyAdjustResponse` — one tx, `SELECT … FOR UPDATE` on LoyaltyAccount; accepts ACTIVE + BLOCKED; 409 on PENDING/DELETED/tombstone; 422 on `new_balance < 0` (`InsufficientBalanceError`).
- Add Pydantic v2 DTOs in `core_api.schemas.admin_users`: `UserSummary`, `UserListResponse`, `UserDetailResponse`, `LoyaltyTransactionItem`, `BlockUserResponse`, `LoyaltyAdjustRequest`, `LoyaltyAdjustResponse`. No `phone` / `phone_hash` / `deleted_at` in any response (INV-013).
- Add 5 FastAPI routes in `core_api.routers.admin_users` mounted at `/api/v1/admin/users` and wired into `core_api.main`.
- Add 5 rows to `ROUTE_MATRIX` in `core_api.rbac_matrix` (all `{ADMIN}`), NOT in `PUBLIC_ROUTES`.
- Error-to-HTTP mapping: `UserNotFoundError → 404`, `InvalidUserStateError → 409 ("invalid_user_state")`, `InsufficientBalanceError → 422 ("insufficient_balance")`.

## Capabilities

### New Capabilities
<!-- None — admin-users-api spec was created in RED; GREEN satisfies it. -->

### Modified Capabilities
- `admin-users-api`: adds implementation that makes the RED-locked contract pass (service, schemas, router, RBAC rows, main wiring). Requirements themselves are not being rewritten — behavior remains what the RED spec already requires. (Listed here because GREEN implementation MAY need to clarify any requirement whose wording turns out ambiguous during implementation; no such change expected.)

## Impact

- **Code** (new, under `services/core-api/src/core_api/`):
  - `services/admin_users.py` — 5 service functions + 3 domain errors (`UserNotFoundError`, `InvalidUserStateError`, `InsufficientBalanceError`).
  - `schemas/admin_users.py` — 7 Pydantic v2 DTOs.
  - `routers/admin_users.py` — 5 endpoints wired to the service module.
- **Code** (modified):
  - `rbac_matrix.py` — 5 new rows, no deletions.
  - `main.py` — `include_router(admin_users.router)`.
- **APIs**: implements `GET /api/v1/admin/users`, `GET /api/v1/admin/users/{user_id}`, `POST /api/v1/admin/users/{user_id}/block`, `POST /api/v1/admin/users/{user_id}/unblock`, `POST /api/v1/admin/users/{user_id}/loyalty/adjust`.
- **Tests**: `services/core-api/tests/test_admin_users_*.py` (6 modules, 87 tests authored in RED) should flip from FAIL → PASS without any test edits. No test file in this change is modified to "make it pass".
- **Dependencies**: reuses `shared.models.{user, user_profile, loyalty_account, loyalty_transaction, order}`, `shared.enums.{UserStatus, OrderStatus, LoyaltyTransactionType}`, `core_api.services.order_cancel.cancel_order`. No new third-party packages.
- **Inviolable rules touched**:
  - **INV-010** (role isolation — 5 rows `{ADMIN}` in `ROUTE_MATRIX`)
  - **INV-013** (PII isolation — `phone_hash` NEVER exposed, NEVER searched; `display_name` is the only searchable field; tombstoned users → 404 on detail)
  - **INV-004** (atomic financials — `adjust_loyalty` wraps balance UPDATE + LoyaltyTransaction INSERT in a single tx with `SELECT … FOR UPDATE`; block-cascade delegates per-order atomicity to existing `cancel_order`)
  - **INV-016** (state machine — forbidden transitions from PDD §6.5 rejected with 409)
- **Systems**: PostgreSQL (read `users`/`user_profiles`/`loyalty_accounts`/`loyalty_transactions`/`orders`; write `SELECT … FOR UPDATE` + UPDATE/INSERT). No Redis, no migrations, no new external services. No celery task authored — block-cascade reuses the existing `payment_worker.initiate_refund` path inside `cancel_order`.

## Non-Goals

- Admin UI (web-admin) — lands in a separate frontend change.
- Auto-creating a `LoyaltyAccount` on first `adjust_loyalty`. Users created in Phase 5 already have an account from registration; the GREEN implementation raises `UserNotFoundError` (or a similar domain error mapped to 404) if the account is somehow missing, to prevent silent state repair.
- Modifying `services/order_cancel.py` or any `shared/models/*` file — the RED tests never touched them and GREEN must not either.
- DELETE user (§6.5 ACTIVE→DELETED) — this is the customer self-delete path via `/api/v1/profile` account deletion flow, not Phase 6 admin scope.
- Phone-based search — `phone_hash` is not reversible (INV-013).
- Exposing `phone`, `phone_hash`, or `deleted_at` in any response body.
- Forbidden §6.5 transitions (BLOCKED→PENDING_VERIFICATION, ACTIVE→PENDING_VERIFICATION, DELETED→anything) — the RED suite already asserts 409 and the GREEN implementation must preserve that.
- Re-implementing §7.6 Order Cancellation Chain (refund enqueue, loyalty REVERSAL, promocode decrement, status SMS) — the block-cascade delegates strictly to `services.order_cancel.cancel_order`.
