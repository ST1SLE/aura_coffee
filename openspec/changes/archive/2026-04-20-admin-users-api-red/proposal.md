## Why

The Phase 6 admin panel (PDD §7.1 item 2) needs a staff-scoped HTTP surface to list, inspect, block, unblock, and adjust loyalty for customer accounts. Today the admin has no read path into `users` / `loyalty_accounts` and no sanctioned write path for the PDD §6.5 User Account Lifecycle transitions (ACTIVE↔BLOCKED), so operators cannot respond to fraud, abuse, or customer-support credit requests. Reusing `/api/v1/profile/*` for this would leak INV-010 (role isolation) — profile routes are scoped to `sub` of the calling customer. A dedicated `/api/v1/admin/users/*` prefix gives the admin UI a stable contract and keeps role boundaries clean.

This is the RED phase of the two-change model — the failing tests lock the contract before any implementation lands.

MVP phase: **Phase 6 — Admin Panel** (PDD §7.1 item 2).

## What Changes

- Introduce failing tests for a new staff-scoped service API in `core_api.services.admin_users`:
  - `list_users(db, *, status, search, page, per_page) -> UserListResponse`
  - `get_user_detail(db, user_id) -> UserDetailResponse`
  - `block_user(db, user_id) -> BlockUserResponse` — cascades to active orders via existing `services.order_cancel.cancel_order`; IN_DELIVERY is skipped silently (courier finishes delivery)
  - `unblock_user(db, user_id) -> BlockUserResponse`-like
  - `adjust_loyalty(db, user_id, delta, reason) -> LoyaltyAdjustResponse`
- Introduce failing router tests for the 5 new endpoints under `/api/v1/admin/users/*` covering: ADMIN-only access (INV-010); {CUSTOMER, BARISTA, COURIER} → 403; missing/invalid token → 401; response shape; state-machine gates from PDD §6.5.
- Introduce failing schema tests for new Pydantic DTOs: `UserSummary`, `UserListResponse`, `UserDetailResponse`, `LoyaltyTransactionItem`, `BlockUserResponse`, `LoyaltyAdjustRequest`, `LoyaltyAdjustResponse`.
- Introduce failing rbac_matrix tests asserting 5 new rows are wired for `{ADMIN}` only and NOT in `PUBLIC_ROUTES`.
- No service, router, schema, or `main.py` wiring lands in this change. Every new test MUST fail because the implementation is absent. Customer-scoped `/api/v1/profile/*` is NOT modified.

## Capabilities

### New Capabilities
- `admin-users-api`: Admin-scoped HTTP surface to list users, read details + loyalty history, block/unblock with cascading order cancellation (PDD §6.5 ACTIVE↔BLOCKED row), and make loyalty balance adjustments (LoyaltyTransactionType.ADMIN_ADJUSTMENT).

### Modified Capabilities
<!-- None — RED phase only introduces new failing tests for a new capability. -->

## Impact

- **Code**: adds new test modules `services/core-api/tests/test_admin_users_list.py`, `test_admin_users_detail.py`, `test_admin_users_block.py`, `test_admin_users_unblock.py`, `test_admin_users_loyalty_adjust.py`, `test_admin_users_rbac.py`. May extend `services/core-api/tests/_factories/` with a helper for seeding `User` + `UserProfile` + `LoyaltyAccount` + orders in deterministic combinations.
- **APIs**: locks the contract for `GET /api/v1/admin/users`, `GET /api/v1/admin/users/{user_id}`, `POST /api/v1/admin/users/{user_id}/block`, `POST /api/v1/admin/users/{user_id}/unblock`, `POST /api/v1/admin/users/{user_id}/loyalty/adjust` (no implementation yet).
- **Dependencies**: reuses `shared.models.user.User`, `shared.models.user_profile.UserProfile`, `shared.models.loyalty_account.LoyaltyAccount`, `shared.models.loyalty_transaction.LoyaltyTransaction`, `shared.models.order.Order`, `shared.enums.{UserStatus, OrderStatus, LoyaltyTransactionType}`, and `core_api.services.order_cancel.cancel_order`. No new third-party packages.
- **Inviolable rules touched**:
  - **INV-010** (role isolation — staff endpoint explicitly forbidden to customer/barista/courier)
  - **INV-013** (PII isolation — `phone_hash` is NEVER exposed in responses and NEVER searched; prefix search is over `user_profiles.display_name` only)
  - **INV-004** (atomic financials — `adjust_loyalty` wraps balance UPDATE + LoyaltyTransaction INSERT in a single transaction with `SELECT … FOR UPDATE`; per-order financial atomicity of block's cascade is delegated to existing `cancel_order`)
- **Systems**: PostgreSQL (read over `users`/`user_profiles`/`loyalty_accounts`/`loyalty_transactions` and SELECT…FOR UPDATE on write paths). No Redis, no migrations, no new external services.

## Non-Goals

- Implementing the routers, services, schemas, RBAC entries, or `main.py` wiring (GREEN phase).
- DELETE user (§6.5 ACTIVE→DELETED) — that is the customer self-delete path via `/api/v1/profile` account-deletion flow, not Phase 6 admin scope.
- Duplicating §7.6 Order Cancellation Chain logic (refund enqueue, loyalty REVERSAL, promocode decrement) — the block-cascade delegates strictly to `services.order_cancel.cancel_order`.
- Modifying `services/order_cancel.py` or any `shared/models/*` file.
- Exposing phone / `phone_hash` in any response body (INV-013 — `phone_hash` is one-way).
- Admin UI (web-admin) — lands in a separate frontend change.
- Forbidden §6.5 transitions (BLOCKED→PENDING_VERIFICATION, ACTIVE→PENDING_VERIFICATION, DELETED→anything) — the tests explicitly assert these are rejected with 409.
- Phone-based search — phone_hash is not reversible (INV-013), so there is no admin lookup by phone in this scope.
