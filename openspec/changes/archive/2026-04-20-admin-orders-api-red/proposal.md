## Why

Staff (admin + barista) need a read-only feed of every order to run the kitchen and follow up on disputes. PDD §4.5 and INV-010 isolate staff from customer data flows: they MUST query their own endpoints, not walk over `/api/v1/orders/{id}` with a forged `user_id`. The existing customer routes enforce ownership via `user_id`, so reusing them for staff would either leak the isolation rule or add role-specific branches inside customer code. A dedicated `/api/v1/admin/orders/*` prefix preserves the split while giving the Phase 6 admin UI a stable contract to code against.

This is the RED phase of the two-change model — the failing tests lock the contract before any implementation lands.

MVP phase: **Phase 6 — Admin Panel** (PDD §7.1).

## What Changes

- Introduce failing tests for a new staff-scoped service API in `core_api.services.order_history`:
  - `list_orders_for_staff(status_filter, type_filter, page, per_page, db_session)` — lists every order (no `user_id` filter), honours the `"active"` meta-status (NOT IN COMPLETED/CANCELLED, matching the partial index from PDD §5.4), filters by `type` (OrderType), paginates with `per_page ≤ 100`, sorts `created_at DESC` for active statuses and `updated_at DESC` for finalized statuses.
  - `get_order_for_staff(order_id, db_session)` — returns the order without an ownership check.
- Introduce failing router tests for `GET /api/v1/admin/orders` and `GET /api/v1/admin/orders/{order_id}` covering: ADMIN + BARISTA allowed (INV-010), CUSTOMER → 403, COURIER → 403, missing/invalid token → 401, query validation (`per_page > 100` → 422), `OrderListResponse` contract, staff visibility into other users' orders.
- Introduce failing rbac_matrix tests asserting the new prefix is wired for ADMIN + BARISTA and NOT in `PUBLIC_ROUTES`.
- No service, router, schema, or main.py wiring lands in this change. Every new test MUST fail because the implementation is absent. Customer-scoped `/api/v1/orders/*` is NOT modified.

## Capabilities

### New Capabilities
- `admin-orders-api`: Staff-scoped (admin + barista) read-only order feed — paginated listing with status/type filters and per-order detail, without customer-side ownership checks.

### Modified Capabilities
<!-- None — RED phase only introduces new failing tests for a new capability. -->

## Non-Goals

- Implementing the routers, services, RBAC entries, or `main.py` wiring (GREEN phase).
- PATCH/POST actions from the admin feed (cancel, status transitions): already owned by `order_actions`, out of scope.
- Changing, extending, or wrapping the existing customer-scoped `/api/v1/orders/*` routes — they stay as-is for the customer-orders-ui group.
- New schemas: tests assert against the existing `OrderListResponse` / `OrderResponse` from `schemas.order_history`.
- New indexes or migrations — the active-orders partial index already exists (PDD §5.4).
- Courier-facing endpoints — couriers use `/api/v1/courier/*`.
- Frontend (admin-orders UI lands in a separate web-admin change).

## Impact

- **Code**: adds new test modules `services/core-api/tests/test_admin_orders_list.py`, `test_admin_orders_detail.py`, `test_admin_orders_rbac.py`. May extend `tests/_factories/orders.py` with a helper to seed finalized (COMPLETED/CANCELLED) orders with a controllable `updated_at`.
- **APIs**: locks the contract for `GET /api/v1/admin/orders` and `GET /api/v1/admin/orders/{order_id}` (no implementation yet).
- **Dependencies**: reuses `shared.models.order.Order`, `shared.enums.OrderStatus`, `shared.enums.OrderType`, and `schemas.order_history.OrderListResponse`/`OrderResponse`. No new third-party packages.
- **Inviolable rules touched**: INV-010 (role isolation — staff endpoint explicitly forbidden to customers), INV-013 (PII isolation — staff access is legitimate purpose; no new PII fields beyond what `OrderResponse` already exposes).
- **Systems**: PostgreSQL (read-only SELECT over `orders` with the existing `(status) WHERE status NOT IN (COMPLETED, CANCELLED)` partial index). No Redis, no migrations.
