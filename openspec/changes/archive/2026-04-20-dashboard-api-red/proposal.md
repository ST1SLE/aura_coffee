## Why

Phase 6 admin UI needs a dashboard — the whole panel (see `pages/DashboardPage.tsx` stub) is wired as the admin home route, and without real numbers the owner cannot see revenue, order throughput, or item popularity. PDD §4.5 calls out "статистика/аналитика" as an ADMIN-only capability and §7.1 Phase 6 item 1 pins the scope: revenue per range, order count, popular items. A single read-only endpoint (`GET /api/v1/admin/stats?range=…`) unblocks the `dashboard-ui` feature (merge_order 6) without touching customer flows, loyalty, or the order lifecycle.

This is the RED phase of the two-change model — failing tests lock the contract (query parameters, date-range math in `Europe/Moscow`, aggregation semantics, RBAC row) before any implementation code lands.

MVP phase: **Phase 6 — Admin Panel** (PDD §7.1).

## What Changes

- Introduce failing tests for a new `compute_range` helper in `core_api.services.admin_stats`:
  - `compute_range("today")` → `[Europe/Moscow start-of-today → UTC, now_utc)`.
  - `compute_range("week")` → `[now_utc - 7d, now_utc)`.
  - `compute_range("month")` → `[now_utc - 30d, now_utc)`.
  - `Europe/Moscow` local-midnight SHALL differ from UTC midnight — the RED test pins the +3h offset conversion.
- Introduce failing tests for two aggregation helpers on `core_api.services.admin_stats`:
  - `get_revenue_and_count(db, start, end) -> (revenue_kopecks, orders_count)` — `COALESCE(SUM(total), 0)` and `COUNT(*)` over `orders WHERE status = 'completed' AND start <= created_at < end`. Tests cover: zero matches → `(0, 0)`; three COMPLETED + one CANCELLED + one PAID → COMPLETED-only totals; out-of-range `created_at` → excluded.
  - `get_popular_items(db, start, end, limit=10) -> list[PopularItem]` — GROUP BY snapshot `(name_ru, name_en)` from `order_items`, ORDER BY `SUM(quantity) DESC`, `LIMIT 10`. Tests cover: two COMPLETED orders with the same snapshot name → one row (sum); two rows for the same menu item renamed mid-range → two rows (INV-014 snapshot fidelity); eleven distinct rows → eleven dropped to ten.
- Introduce failing router tests for `GET /api/v1/admin/stats`:
  - `barista` → 403, `courier` → 403, `customer` → 403, no token → 401, `range=bogus` → 422.
  - RED signal until GREEN registers the router.
- Introduce failing RBAC-matrix tests: `("GET", "/api/v1/admin/stats") ∈ ROUTE_MATRIX` with role set `{ADMIN}` (NOT `BARISTA`, NOT `COURIER`, NOT `CUSTOMER`), and NOT in `PUBLIC_ROUTES`.
- No service, router, schema, or `main.py` wiring lands in this change. Every new test MUST fail because the implementation is absent. Customer-facing and other admin routes remain untouched.

## Capabilities

### New Capabilities
- `dashboard-api`: ADMIN-only dashboard statistics endpoint — `GET /api/v1/admin/stats?range=today|week|month` returning revenue (kopecks), order count, and top-10 popular items aggregated from COMPLETED orders in the requested window (Europe/Moscow for "today").

### Modified Capabilities
<!-- None — RED phase only introduces a new failing-tests suite for a new capability. -->

## Non-Goals

- Implementing the router, service functions, schemas, `main.py` registration, or the RBAC row (GREEN phase).
- Redis caching, pre-aggregated `daily_stats`, materialized views, or any async worker — out of scope per prompt constraints.
- Revenue breakdowns excluding `delivery_fee` ("gross revenue without delivery") — the prompt pins `SUM(total)`; a separate flag would be its own feature.
- Aggregating orders in non-terminal statuses (PAID, PREPARING, READY, IN_DELIVERY) — only COMPLETED counts, matching the loyalty accrual boundary.
- Per-user, per-courier, per-type (pickup vs delivery) breakdowns — not in the Phase 6 item 1 spec; a future ticket.
- Shop-settings changes, Celery beat/worker changes, or any frontend work — dashboard-ui consumes this endpoint in merge_order 6 of the phase-6 plan.
- Customer-scoped order endpoints (`/api/v1/orders/*`) and staff order feed (`/api/v1/admin/orders/*`) — untouched.
- Courier endpoints — out of scope (INV-010: courier MUST NOT see aggregates).

## Impact

- **Code**: adds three new test modules `services/core-api/tests/test_admin_stats_range.py`, `test_admin_stats_revenue.py`, `test_admin_stats_popular.py`, `test_admin_stats_rbac.py`. All imports of the target symbols happen inside test bodies so missing implementation surfaces per-test (ImportError), not as a collection failure.
- **APIs**: locks the contract for `GET /api/v1/admin/stats` — query `range: Literal["today","week","month"]` default `"month"`; response shape `{range, range_start, range_end, revenue_kopecks, orders_count, popular_items[]}`.
- **Dependencies**: reuses `shared.models.order.Order`, `shared.models.order_item.OrderItem`, `shared.enums.OrderStatus`, `core_api.rbac_matrix`. No new third-party packages. SQLAlchemy 2.0 Core `select()` for the aggregations.
- **Inviolable rules touched**: INV-010 (role isolation — ADMIN only; BARISTA/COURIER denied in RBAC row and router tests), INV-014 (immutable order items — popular-items aggregation groups on snapshot `name_ru/name_en` from `order_items`, so menu renames produce two historical rows, not one).
- **Systems**: PostgreSQL read-only SELECTs over `orders` and `order_items` scoped to COMPLETED status and a bounded `created_at` window. No Redis, no migrations, no Celery.
