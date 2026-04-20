## Why

The RED cycle (archived as `admin-orders-api-red`) locked the contract for staff-scoped
order endpoints via 33 failing tests, but shipped no implementation — so barista/admin
staff still have **no** way to read the order feed required by MVP Phase 6 (PDD §4.5,
§7.1). This change delivers the implementation so those tests flip from red to green,
unblocking the admin panel UI and closing the compliance gap around INV-010 (role
isolation) for the order-read surface.

## What Changes

- Add staff service helpers in `core_api.services.order_history`:
  - `list_orders_for_staff(*, status_filter, type_filter, page, per_page, db_session) -> OrderListResponse`
  - `get_order_for_staff(*, order_id, db_session) -> OrderResponse`
  - `OrderNotFoundForStaffError` domain exception
- Register new router `core_api.routers.admin_orders` exposing:
  - `GET /api/v1/admin/orders` (paginated, filtered feed)
  - `GET /api/v1/admin/orders/{order_id}` (single order detail)
- Wire router into `core_api.main.app` exactly once.
- Extend `core_api.rbac_matrix.ROUTE_MATRIX` with two rows mapping the new routes to
  `{ADMIN, BARISTA}`. Do NOT add them to `PUBLIC_ROUTES`.
- Preserve `list_orders` (customer-scoped) and `("GET", "/api/v1/orders/{order_id}")`
  matrix row exactly as-is.

Not breaking — all additions are new surface. Customer-scoped `/api/v1/orders/*`
is untouched.

## Capabilities

### New Capabilities

- `admin-orders-api`: staff-scoped, read-only HTTP surface for admin+barista to page
  through and inspect orders across all customers. Implements PDD §4.5 scenarios
  S-ADMIN-003 (order feed) and INV-010 (role-based isolation).

### Modified Capabilities

_None — existing `order-history` capability stays customer-scoped and is not touched
by this change._

## Impact

- **Code**: `services/core-api/src/core_api/services/order_history.py`,
  `services/core-api/src/core_api/routers/admin_orders.py` (new),
  `services/core-api/src/core_api/main.py`,
  `services/core-api/src/core_api/rbac_matrix.py`.
- **API contract**: two new `GET` endpoints; OpenAPI spec regenerates. No DB migration
  (reuses `orders` table and the partial index
  `orders (status) WHERE status NOT IN ('completed', 'cancelled')` from migration 0005).
- **Tests**: 33 tests authored in RED now turn green; no test renames.
- **Dependencies**: none added. Reuses existing JWT middleware, RBAC middleware,
  `schemas.order_history.OrderListResponse` / `OrderResponse`.
- **MVP Phase**: 6 (Admin Panel). Directly consumed by `web-admin` order feed screens.

## Non-Goals

- **No PATCH/POST/DELETE**. Read-only feed. Status transitions stay in their
  existing dedicated endpoints (order-actions-api).
- **No changes to customer-scoped routes.** `/api/v1/orders/*` and the customer
  `list_orders` helper keep their `user_id` parameter and behavior exactly as-is.
- **No new schemas.** Reuse `schemas.order_history.OrderListResponse` and
  `OrderResponse` — admin variant already carries `user_id`.
- **No extra filters** (no date range, no text search, no user filter in MVP).
