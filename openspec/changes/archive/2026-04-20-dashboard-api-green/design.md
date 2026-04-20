## Context

Affected modules: **[core-api]**.

RED (archive `2026-04-20-dashboard-api-red`) pinned four test modules against non-existing symbols (`compute_range`, `get_revenue_and_count`, `get_popular_items`), an unregistered router (`GET /api/v1/admin/stats`), and a missing RBAC matrix row. GREEN implements the production code that makes those tests pass without touching anything outside `services/core-api/src/core_api/`.

The endpoint feeds the admin dashboard (PDD §4.5, §7.1 Phase 6 item 1). It is strictly read-only — no state transitions, no financial mutations, no PII touched beyond what already lives in `orders` (user_id FK only, no phone/name).

Architecture is intentionally plain: one SQLAlchemy Core aggregation per metric, composed in the router. No caching, no pre-aggregation, no Celery — the data volume at a single-shop scale (hundreds of orders/day) makes `SELECT ... WHERE status = 'completed' AND created_at BETWEEN ...` cheap enough to satisfy P95 < 500 ms on the COMPLETED-restricted partial index that already exists for staff order feeds.

## Goals / Non-Goals

**Goals:**
- GREEN-flip every failing test from the RED suite while keeping the RED-phase "desired" passes intact (401/403 for unauth/barista/courier/customer, `PUBLIC_ROUTES` exclusion).
- Keep the implementation in three new files + two two-line edits; no cross-cutting refactors.
- Uphold INV-010 (ADMIN-only — rejected by RBAC middleware before the route is reached) and INV-014 (popular-items groups on `order_items.name_ru/name_en` snapshots).
- Match the Pydantic v2 response shape frozen in `specs/dashboard-api/spec.md` so the admin frontend's OpenAPI client types are stable downstream.

**Non-Goals:**
- Pre-aggregated tables / Celery workers / Redis caching — out of scope.
- Permissioning knobs other than `{ADMIN}` — no per-shop, per-courier, per-type breakdowns.
- Frontend / OpenAPI client regeneration — `dashboard-ui` owns that (merge_order 6 of phase-6 plan).
- Alembic migration — schema is unchanged.
- Revenue-without-delivery variant — `orders.total` is the single source column per prompt.

## Decisions

### D1 — Single module for helpers + endpoint composition [core-api]

The three helpers (`compute_range`, `get_revenue_and_count`, `get_popular_items`) SHALL live in `core_api.services.admin_stats`. The router (`core_api.routers.admin_stats`) composes them sequentially — no helper calls another helper, no hidden side effects. The router does NOT construct SQL directly.

**Rationale:** RED tests import each helper independently inside their test bodies (`from core_api.services.admin_stats import <name>`) — each needs to be a top-level callable. Grouping them in one module keeps the "admin stats" surface area coherent and greppable.

**Alternative considered:** one helper per module (`admin_stats/range.py`, `admin_stats/revenue.py`, ...). Rejected — splits a ~80-line cohesive unit and forces deeper import paths.

### D2 — `Europe/Moscow` hardcoded as module constant [core-api]

`TIMEZONE = "Europe/Moscow"` SHALL be a module-level string in `admin_stats.py`. `compute_range` SHALL pass it to `ZoneInfo(TIMEZONE)`.

**Rationale:** Aura Coffee is single-shop. `shop_settings` does not carry a TZ column. Reading settings on every stats request would be gratuitous I/O and coupling.

**Alternative considered:** add `timezone` to `shop_settings` via migration. Rejected — out of scope and would bloat GREEN.

### D3 — Half-open `[start, end)` UTC interval with `end = datetime.now(timezone.utc)` at call time [core-api]

`compute_range` SHALL call `datetime.now(timezone.utc)` exactly once per invocation and use the captured value as `end` for every range. `today` anchors `start` to `ZoneInfo("Europe/Moscow")` local midnight of `date.today()` converted to UTC; `week` and `month` subtract 7 and 30 days from `end` respectively.

**Rationale:** RED tests assert `abs(now - end) < 2s` — capturing `end` once ensures the returned value and the body-local `now` in the test align within clock drift. Half-open `[start, end)` matches the SQL aggregation predicate `start <= created_at < end` and the scenario `test_get_revenue_and_count_respects_half_open_interval`.

### D4 — Revenue = `COALESCE(SUM(orders.total), 0)` with no post-processing [core-api]

`get_revenue_and_count` SHALL issue one SQL `SELECT COALESCE(SUM(orders.total), 0), COUNT(*) FROM orders WHERE status = :completed AND created_at >= :start AND created_at < :end`. `orders.total` is already in kopecks and already includes `delivery_fee`. The helper SHALL NOT subtract `delivery_fee`, apply tax, or convert units.

**Rationale:** PDD §7.2 loyalty accrual uses a different formula (`subtotal - discount - points_used`) because loyalty accrues on pre-tip pre-delivery revenue. Dashboard revenue per prompt is the realised money figure — one SQL column, one semantic. Mixing the two would invite divergence and double-counting bugs.

### D5 — Popular-items grouping key = snapshot `(name_ru, name_en)`, NOT `menu_item_id` [core-api]

`get_popular_items` SHALL `GROUP BY order_items.name_ru, order_items.name_en` and return a list of lightweight rows with `name_ru`, `name_en`, and `quantity` attributes. The helper SHALL NOT join to the `menu_items` table.

**Rationale:** INV-014 — `order_items` is an immutable snapshot. If a menu item is renamed mid-range, the snapshot preserves both historical names; the dashboard MUST show both as distinct rows because they represent distinct customer experiences. Joining on `menu_items` would either drop archived items (inner join) or coalesce renames (fetch the current name) — both break INV-014 fidelity.

### D6 — `LIMIT :limit` is a hard SQL cap, default 10 [core-api]

`get_popular_items(db, start, end, limit=10)` applies `LIMIT :limit` at the SQL level — the server never materialises more than ten rows. `ORDER BY quantity DESC` is applied before the limit.

**Rationale:** RED test seeds eleven distinct snapshots with quantities 1..11 and asserts the result excludes the `quantity=1` row. This is a SQL-level guarantee, not a Python slice.

### D7 — `AdminStatsResponse` Pydantic v2 schema, no datetime coercion bugs [core-api]

`core_api.schemas.admin_stats.AdminStatsResponse` SHALL type `range` as `Literal["today","week","month"]`, `range_start` and `range_end` as `datetime`, `revenue_kopecks` and `orders_count` as `int`, `popular_items` as `list[PopularItemOut]`. FastAPI serialises TZ-aware `datetime` to ISO-8601 with `+00:00`; no custom serialiser needed because `compute_range` always returns UTC-aware datetimes.

### D8 — Router accepts `range: Literal["today","week","month"] = "month"` via `Query` [core-api]

`GET /api/v1/admin/stats` SHALL declare `range: Literal["today","week","month"] = Query("month")`. FastAPI auto-generates a 422 for `range=bogus` before the handler body runs — satisfying RED task 4.8's GREEN assertion.

### D9 — RBAC matrix row is the ONLY authorisation surface [core-api]

`ROUTE_MATRIX[("GET", "/api/v1/admin/stats")] = {ADMIN}`. The route handler SHALL NOT take an auth dependency — `RBACMiddleware` rejects non-ADMIN and no-Bearer requests before the handler is called.

**Rationale:** Every existing admin-scoped router (`admin_orders.py`, `admin_promocodes.py`) follows this pattern. Adding a redundant `Depends(require_admin)` would couple the handler to a second source of truth.

### D10 — Router prefix `/api/v1/admin`, tags `["admin", "stats"]` [core-api]

Follow existing admin router conventions. Registered in `core_api.main` via `app.include_router(admin_stats_router)`.

## Risks / Trade-offs

- **[Risk]** `get_popular_items` returns a list of tuples/Row objects — tests expect attribute access (`row.name_ru`, `row.quantity`). → **Mitigation:** helper SHALL wrap the SQL result in a small `PopularItem` dataclass (or return SQLAlchemy Core `Row` objects which already support attribute access via column names). Return type annotated as `list[PopularItem]` with `PopularItem` as a `@dataclass` for clarity.
- **[Risk]** `datetime.now(timezone.utc)` drift causes RED tolerance test to flake if the test container is under heavy load. → **Mitigation:** RED uses `< 2s` tolerance — generous for CI. No time-freezing needed.
- **[Risk]** `"today"` at UTC+3 midnight boundary returns a window shorter than 3 hours if the admin loads the dashboard at 02:00 Moscow time. → **Mitigation:** desired product behaviour — "today" means Moscow-local today, not rolling 24h. Scenario explicitly asserts the Moscow-midnight anchor.
- **[Trade-off]** Running three separate SQL queries (range math is Python-side) per request instead of one composite query. Two queries to Postgres (count+sum is one; popular items is the second; range math is Python). Cost is negligible at single-shop volumes; clarity/maintainability wins.
- **[Trade-off]** No caching. Every ADMIN page load hits Postgres. Single-shop traffic + low-cardinality admin pool (< 10 users) makes this fine; a `@lru_cache(ttl=60s)` would complicate invariant testing.

## Migration Plan

Forward-only code addition. No DB migration. Rollback = revert the PR. The RBAC row addition is append-only to the matrix dict; removing it later would default-deny the route (middleware rejects unknown routes as 403), which matches pre-change behaviour exactly.
