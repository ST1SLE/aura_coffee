## Why

Phase 6 admin UI needs the dashboard endpoint implemented — the RED change locked the contract (four failing test modules covering the service helpers, RBAC row and router). GREEN adds the minimal production code to flip those tests green: a `services/admin_stats.py` module with three helpers, a Pydantic response schema, an ADMIN-only router, and the RBAC matrix entry. Once merged, `web-admin`'s `DashboardPage` (merge_order 6 of the phase-6 plan) can consume real revenue / order-count / popular-items numbers.

MVP phase: **Phase 6 — Admin Panel** (PDD §7.1 item 1 "Dashboard со статистикой").

## What Changes

- Add `core_api.services.admin_stats` with three helpers:
  - `TIMEZONE = "Europe/Moscow"` module constant (single-shop hardcode — `shop_settings` does not carry a TZ column).
  - `compute_range(range_param)` → half-open `[start, end)` UTC interval per PDD §6.1 semantics (`today` → local-Moscow-midnight → UTC; `week` → `now-7d`; `month` → `now-30d`).
  - `get_revenue_and_count(db, start, end)` → `(COALESCE(SUM(orders.total), 0), COUNT(*))` filtered by `status = OrderStatus.COMPLETED` AND `start <= created_at < end`. `orders.total` already includes `delivery_fee` — no arithmetic.
  - `get_popular_items(db, start, end, limit=10)` → `SELECT order_items.name_ru, order_items.name_en, SUM(quantity)` joined to `orders`, filtered the same way, `GROUP BY (name_ru, name_en)` (INV-014 snapshot fidelity — NOT `menu_item_id`), `ORDER BY quantity DESC`, `LIMIT :limit`. Returns a list of dataclass-like rows (`PopularItem`) so tests can read attributes.
- Add `core_api.schemas.admin_stats` with Pydantic v2 models:
  - `PopularItemOut { name_ru, name_en, quantity }`.
  - `AdminStatsResponse { range, range_start, range_end, revenue_kopecks, orders_count, popular_items[] }`.
- Add `core_api.routers.admin_stats` exposing `GET /api/v1/admin/stats?range=today|week|month` (default `month`). Router composes the three helpers and returns `AdminStatsResponse`.
- Register the router in `core_api.main` (`app.include_router(admin_stats_router)`).
- Extend `core_api.rbac_matrix.ROUTE_MATRIX` with a single row: `("GET", "/api/v1/admin/stats") -> {ADMIN}`. Route SHALL NOT appear in `PUBLIC_ROUTES`; BARISTA, COURIER, CUSTOMER SHALL NOT appear in the role set.
- Confirm no migration, no new dependency, no frontend change, no Celery/Redis wiring.

## Capabilities

### New Capabilities
<!-- The `dashboard-api` spec was created in the RED archive with RED-only scenarios. -->

### Modified Capabilities
- `dashboard-api`: replace RED-phase "symbol absent / route not registered / matrix row missing" scenarios with the GREEN behavioral scenarios (helpers return the documented results; router returns 200 / 422; matrix row equals `{ADMIN}` / absent from PUBLIC_ROUTES).

## Non-Goals

- Redis/in-memory caching, materialized views, pre-aggregated `daily_stats` tables, Celery beat pre-computation — out of scope per prompt.
- Revenue breakdown excluding `delivery_fee` (a "gross-without-delivery" toggle would be a separate feature).
- Counting non-terminal statuses (PAID, PREPARING, READY, IN_DELIVERY) in revenue — COMPLETED-only, matching the loyalty accrual boundary.
- Per-user / per-courier / per-type (pickup vs delivery) breakdowns — Phase 6 item 1 does not ask for them.
- `shop_settings` changes (no timezone column) — the `Europe/Moscow` constant is module-local.
- Frontend `DashboardPage` wiring — shipped under `dashboard-ui` (merge_order 6 of phase 6).
- Courier-facing variant — INV-010 forbids courier access to aggregates.
- Customer or staff order endpoints — untouched.

## Impact

- **Code**: adds `services/core-api/src/core_api/services/admin_stats.py`, `services/core-api/src/core_api/schemas/admin_stats.py`, `services/core-api/src/core_api/routers/admin_stats.py`; edits `services/core-api/src/core_api/main.py` and `services/core-api/src/core_api/rbac_matrix.py`. No new test files (RED already added four).
- **APIs**: activates `GET /api/v1/admin/stats` with `range: Literal["today","week","month"]` default `month`; response shape `{range, range_start, range_end, revenue_kopecks, orders_count, popular_items[]}`.
- **Dependencies**: SQLAlchemy 2.0 Core `select()` / `func.sum` / `func.count`, `zoneinfo.ZoneInfo` (stdlib). No new third-party packages.
- **Inviolable rules**: upholds INV-010 (ADMIN-only — BARISTA/COURIER/CUSTOMER denied by RBAC), INV-014 (popular-items groups on `order_items` snapshot, so mid-range menu renames produce two historical rows).
- **Systems**: PostgreSQL read-only SELECTs over `orders` and `order_items` with a `status + created_at` predicate. No Redis, no migrations, no Celery.
