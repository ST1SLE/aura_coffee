## Context

Phase 6 item 1 adds a dashboard to the admin SPA. The admin home route (`pages/DashboardPage.tsx`) is a 12-line stub today; it cannot ship until a server endpoint emits the aggregates called for in PDD §4.5 — revenue per window, order count, popular items. There is no existing admin-stats endpoint; the closest neighbours are `admin_orders` (read-only feed, `{ADMIN, BARISTA}`) and `admin_promocodes` (CRUD, `{ADMIN}`). Both sit under `/api/v1/admin/*` and are wired through `core_api.rbac_matrix.ROUTE_MATRIX` + `RBACMiddleware`. This change reuses that pattern.

The hard choices are around semantics rather than machinery:
- **Time-window math** — "today" must start at local midnight in the shop's timezone, not UTC midnight, so a Moscow-morning admin sees coherent numbers. All other DB timestamps are `TIMESTAMPTZ` stored in UTC; the boundary conversion happens in Python before the query.
- **Revenue scope** — `orders.total` is a kopeck integer that includes `delivery_fee`. The prompt is explicit: dashboard revenue SHALL be gross money-paid (with `delivery_fee`), while loyalty accrual (§7.2 step 6) continues to exclude it. Two aggregation cuts, one source column, one rule-per-consumer.
- **Popular-items grouping** — INV-014 pins `order_items.menu_item_name_ru/en` as immutable snapshots. Aggregating by `menu_item_id` would merge "Латте" before and after a rename into a single row; aggregating by snapshot `(name_ru, name_en)` preserves historical fidelity at the cost of two rows for renamed items. The snapshot rule wins — it is the only interpretation consistent with INV-014.

This is the RED half of the two-change model: failing tests lock the contract. No service, router, schema, or `main.py` wiring lands here.

**Affected modules:** `[core-api]`.

## Goals / Non-Goals

**Goals:**
- Author failing tests that pin every bullet of the `dashboard-api` capability against PDD §4.5, §5.2 (orders / order_items), §6.1 (COMPLETED is terminal), §7.1 Phase 6 item 1, INV-010 (role isolation), and INV-014 (order-item snapshot immutability).
- Lock `compute_range(range_param) -> (start, end)` semantics:
  - `"today"` SHALL open at `start_of_today_local` in `Europe/Moscow` converted to UTC, closing at `now_utc`.
  - `"week"` SHALL open at `now_utc - timedelta(days=7)`, closing at `now_utc`.
  - `"month"` SHALL open at `now_utc - timedelta(days=30)`, closing at `now_utc`.
  - Invalid range strings SHALL raise at the router edge (FastAPI `Literal` → 422), proven via the router-layer test.
- Lock aggregation semantics at the service-function layer:
  - `get_revenue_and_count` SHALL return `(SUM(total), COUNT(*))` over `orders WHERE status = 'completed' AND start <= created_at < end`.
  - `get_popular_items` SHALL `SELECT name_ru, name_en, SUM(quantity) AS qty FROM order_items oi JOIN orders o ON o.id = oi.order_id WHERE o.status = 'completed' AND o.created_at IN [start, end) GROUP BY name_ru, name_en ORDER BY qty DESC LIMIT 10`.
- Lock the RBAC matrix: `("GET", "/api/v1/admin/stats") → {ADMIN}`; NOT in `PUBLIC_ROUTES`; BARISTA, COURIER, CUSTOMER SHALL each receive 403; requests without a Bearer token SHALL receive 401.
- Keep the RED signal clean — target-module imports SHALL live inside test bodies so missing symbols fail per-test (`ImportError`) rather than at collection.

**Non-Goals:**
- Writing the router (`routers/admin_stats.py`), service functions (`services/admin_stats.py`), schemas (`schemas/admin_stats.py`), `main.py` registration, or the RBAC row — all reserved for GREEN.
- Redis caching, materialized views, a pre-aggregated `daily_stats` table, or any Celery/async worker.
- Breakdown variants (pickup vs delivery, per-user, per-courier) or additional ranges.
- Revenue *excluding* `delivery_fee` — a separate feature if ever requested.
- Courier-facing or barista-facing aggregates — INV-010 keeps aggregates admin-only.
- Any change to customer-scoped order endpoints, `admin_orders`, `admin_promocodes`, `shop_settings`, or the `order_lifecycle` service.
- Frontend work (DashboardPage wiring is merge_order 6 of the phase-6 plan, behind its own change).

## Decisions

### D1 — New capability `dashboard-api`, not a delta to `admin-orders-api`

**Decision:** Introduce `dashboard-api` as a NEW capability rooted at `GET /api/v1/admin/stats`.
**Why:** `admin-orders-api` is a row-level feed; `dashboard-api` returns aggregates with different query semantics, a different RBAC row (`{ADMIN}` vs `{ADMIN, BARISTA}`), and a different response shape. Folding them together would require MODIFIED markers over every existing requirement. A fresh capability keeps the two surfaces independently reviewable.
**Alternative:** Extend `admin-orders-api` with an `/stats` sub-path. Rejected — router module, RBAC row, and schema module all split naturally; no shared helpers to deduplicate.

### D2 — Business logic lives in `core_api.services.admin_stats`, not `core_api.services.order_history`

**Decision:** Create a new service module `core_api.services.admin_stats` exposing `compute_range`, `get_revenue_and_count`, `get_popular_items`. RED tests SHALL import these symbols from that module inside the test body.
**Why:** `order_history` is per-order (list + detail). The stats helpers are pure aggregations with no row-level contract. Colocation would force the module to carry both row-fetch and reduce-over-rows concerns. A sibling module keeps the blast radius local.
**Alternative:** Inline SQL in the router. Rejected — router tests would need a live DB to pin the SQL contract; a service layer gives the unit-test seam for the three RED suites (`test_admin_stats_range.py`, `test_admin_stats_revenue.py`, `test_admin_stats_popular.py`).

### D3 — Tests MUST fail via `ImportError`, not collection failure

**Decision:** Every RED test SHALL import the target symbols (`compute_range`, `get_revenue_and_count`, `get_popular_items`, `AdminStatsResponse`, `PopularItem`) inside the test body. Router tests SHALL hit the path via `TestClient` and assert the middleware-produced 403/401 or the 422 Literal violation — NOT the `app.routes` registration (which would couple RED semantics to GREEN route-ordering details).
**Why:** Module-level imports of absent symbols abort collection and hide which scenarios are unlocked. Body-local imports keep the RED report granular — GREEN flips each test individually. Router tests for missing paths naturally return 403 (RBAC default-deny treats unknown admin paths as staff-protected) or 404; we assert the role-split outcomes.
**Alternative:** Stub empty callables. Rejected — that adds implementation scaffolding to a pure-RED change, muddying the contract.

### D4 — `Europe/Moscow` hardcoded for "today" boundary

**Decision:** The RED contract hardcodes `TIMEZONE = "Europe/Moscow"` for the `compute_range("today")` boundary. `shop_settings` does NOT carry a `timezone` column and the business is a single Moscow shop — there is no configuration pressure.
**Why:** Matches the prompt and the single-shop scope of the product. Moving to `shop_settings.timezone` would require a migration and broader service reach; deferred to the day we open a second location.
**Alternative:** UTC-only. Rejected — "today" at 10:00 Moscow time would include yesterday's 21:00–24:00 MSK orders (since UTC-midnight is 03:00 MSK), contradicting operator intuition.

### D5 — Half-open `[start, end)` interval with UTC `now_utc`

**Decision:** All three ranges SHALL be half-open `start <= created_at < end`, with `end = now_utc = datetime.now(timezone.utc)`. `"today"` SHALL set `start` to Europe/Moscow local-midnight-of-today converted to UTC; `"week"` and `"month"` SHALL set `start = now_utc - timedelta(days=7|30)`.
**Why:** Half-open intervals avoid double-counting orders at the boundary if the endpoint is re-hit rapidly (a closed interval would include any order created exactly at `end`, which is rare but tests should not be flaky). Using `now_utc` as the right edge prevents the "an order just hit COMPLETED at 11:59:59.999" confusion across time zones.
**Alternative:** `[start, end]` closed interval. Rejected — convention and idempotency favour `[start, end)`.

### D6 — Revenue formula: `SUM(total)` with `delivery_fee` included

**Decision:** `get_revenue_and_count` SHALL return `COALESCE(SUM(orders.total), 0)` over COMPLETED orders in range. `orders.total` is pre-computed at checkout (PDD §7.2 step 7) and includes `delivery_fee`; this matches money-in-bank.
**Why:** Loyalty accrual (§7.2 step 6) excludes `delivery_fee` to avoid inflating points, but the dashboard shows gross money paid through ЮKassa — the operator-facing revenue number. Mixing the two semantics inside one endpoint would mask which one is being shown; the prompt explicitly pins `SUM(total)`.
**Alternative:** `SUM(subtotal - discount_amount - points_used)` (loyalty-accrual math). Rejected — that is an internal accounting quantity, not the gross revenue the owner expects to see.

### D7 — Only COMPLETED counts

**Decision:** Both aggregates SHALL filter `status = OrderStatus.COMPLETED`. PAID, PREPARING, READY, IN_DELIVERY, CANCELLED SHALL NOT contribute.
**Why:** COMPLETED is the terminal "money realised" state per PDD §6.1 — it coincides with the loyalty accrual trigger, so the dashboard and loyalty books see the same set of orders. Including PAID inflates revenue with in-flight orders that may still cancel; including CANCELLED subtracts nothing useful.
**Alternative:** Include PAID+PREPARING+READY+IN_DELIVERY as "earned". Rejected — they are reversible via cancellation.

### D8 — Popular items group on snapshot `(name_ru, name_en)`, NOT `menu_item_id`

**Decision:** `get_popular_items` SHALL `GROUP BY order_items.name_ru, order_items.name_en`. RED tests pin both behaviours:
- Same snapshot name across orders → one row (sum quantity).
- Same `menu_item_id` but different snapshot names (mid-range rename) → two rows.
**Why:** INV-014 makes `order_items` an immutable snapshot. Grouping on `menu_item_id` would collapse historically distinct sales into a single row keyed by the current menu row, violating the snapshot-fidelity invariant. The operator-facing read of "popular items during this range" is "what customers actually bought by the name shown to them", which is the snapshot.
**Alternative:** Group on `menu_item_id` with a `COALESCE(current_name, snapshot_name)` projection. Rejected — breaks INV-014 at the aggregate layer.

### D9 — `top 10` as a hard LIMIT, `DESC` by total quantity

**Decision:** `get_popular_items` SHALL `ORDER BY SUM(quantity) DESC` and `LIMIT 10`. Ties MAY resolve in any order (tests assert membership + ordering on quantity, not on name).
**Why:** Matches the prompt. Ten rows fit a dashboard card; ties on quantity are rare in a single shop and not worth a secondary-sort contract.
**Alternative:** Configurable limit. Rejected — premature flexibility; add a query param only when dashboard-ui asks.

### D10 — RBAC row is part of the RED contract

**Decision:** RED tests SHALL assert `ROUTE_MATRIX[("GET", "/api/v1/admin/stats")] == {ADMIN}` and `("GET", "/api/v1/admin/stats")` NOT in `PUBLIC_ROUTES`. Router tests SHALL assert `barista_headers` → 403, `courier_headers` → 403, `customer_headers` → 403, missing Authorization → 401.
**Why:** INV-010 lives in the matrix; locking the row at the RED layer catches accidental role widening (e.g. allowing BARISTA "just in case") during GREEN. Admin aggregates of all users' orders are explicitly admin-only per PDD §4.5 (staff lists of items are allowed for BARISTA via `admin_orders`; aggregates of revenue are not).
**Alternative:** Loosen to `{ADMIN, BARISTA}` to match `admin_orders`. Rejected — §4.5 says "статистика/аналитика" for Админ, the barista bullet does not include it.

### D11 — RED router tests use `TestClient` without a DB seed

**Decision:** Router-layer RED tests (`test_admin_stats_rbac.py`) SHALL use the plain `client` fixture (in-memory SQLite) + role-keyed header fixtures from `tests/conftest.py`. They SHALL assert only status codes (401/403/422); no body shape and no DB seeding.
**Why:** RBAC is a transport-layer property; it SHALL fail even before the router is registered (the middleware default-denies unknown admin paths). Service-layer aggregation tests (revenue, popular items) use `migrated_db_session` (Postgres) per the prompt — that covers the aggregation SQL.
**Alternative:** Seed orders in the RBAC tests. Rejected — expands blast radius without strengthening the RBAC contract.

### D12 — DB-touching tests use `migrated_db_session` (module-scoped Postgres session)

**Decision:** `test_admin_stats_revenue.py` and `test_admin_stats_popular.py` SHALL use the module-scoped `migrated_db_session` fixture (PostgreSQL + Alembic upgrade head). Each test SHALL seed its own orders via `tests._factories.orders` helpers and SHALL clean up its rows (or rely on rollback via the module-scope + `session.rollback()` teardown).
**Why:** The prompt pins `migrated_db_session`. The SQL under test touches `orders.total`, `orders.status`, `order_items.name_ru/en`, `order_items.quantity` — all Postgres-typed; sqlite would hide type-casts and partial-index behaviour.
**Caveat:** `migrated_db_session` is module-scoped and uses rollback in teardown. Tests within one module SHALL avoid cross-contamination either by querying scoped to a specific seeded user/order or by crafting disjoint time windows with `created_at` far in the past (e.g. 2020-01-01) so other tests' default "now" seeds don't bleed in.

### D13 — RED `compute_range` tests do not call `datetime.now` at module import

**Decision:** Each `compute_range` RED test SHALL freeze `datetime.now` via either `freezegun` (already a dev dep if present; otherwise a `monkeypatch` + `callable` fake) OR SHALL compute the expected bounds relative to the same clock call used inside the service. Tests SHALL assert bound-correctness with ±2 second tolerance to absorb wall-clock drift between the two calls.
**Why:** A naive test that hard-codes the expected `start` based on `datetime.now()` run at test time will fail intermittently if the service's internal `datetime.now()` happens microseconds later. Tolerance OR freeze eliminates the flake.
**Alternative:** Inject a clock into the service. Rejected — introduces design scaffolding (clock port) that GREEN may not want; RED keeps it as a tolerance.

## Risks / Trade-offs

- **[Risk]** Test for `compute_range("today")` is TZ-dependent; running the test during a DST transition in another zone (`UTC+X ≠ +3`) could mask the +3h offset assertion. → **Mitigation:** The assertion SHALL compute the expected `start` via `zoneinfo.ZoneInfo("Europe/Moscow")` rather than hardcoding `+3h`, so the test is correct year-round (Moscow does not observe DST since 2014, so `+3h` is stable — but the assertion pins the semantic "local midnight in Europe/Moscow" rather than a literal `+3h`).
- **[Risk]** Popular-items D8 grouping on snapshot text columns could collapse duplicates if whitespace or case differs in renames. → **Mitigation:** The RED test uses exact equality rather than trimmed/lowered comparison, exposing any future normalization choice as a contract delta.
- **[Risk]** `migrated_db_session` is module-scoped; tests leak rows across module imports if one forgets to rollback. → **Mitigation:** Each DB-touching test SHALL filter its assertions by a unique user-id or `created_at` window at least a year in the past (e.g. 2020-01-15) so seeds from neighbouring tests cannot contaminate.
- **[Risk]** RBAC widening in GREEN (e.g. `{ADMIN, BARISTA}`) would silently pass the 401 / customer / courier tests. → **Mitigation:** D10 adds an explicit assertion that `ROUTE_MATRIX[("GET", "/api/v1/admin/stats")] == {ADMIN}`, and a barista-403 router test. Both MUST fail independently if the role set widens.
- **[Trade-off]** Hard-coding `Europe/Moscow` forbids multi-region operation without a follow-up spec. Accepted — a second shop is not in scope; a spec delta is cheap.
- **[Trade-off]** `top 10` is a hard cap; dashboard-ui cannot request a larger list. Accepted — a query-param expansion is cheap when the UI asks.

## 152-FZ Compliance

Aggregates do NOT surface PII. `revenue_kopecks` and `orders_count` are scalars. `popular_items` exposes only `(name_ru, name_en, quantity)` — all menu-derived values, no `user_id`, phone, address, or name. Access is gated to ADMIN only (INV-010) via `ROUTE_MATRIX`. No change to `users`, `user_profiles`, `delivery_addresses`, or any other PII-bearing table. INV-013 is preserved trivially because the endpoint reads aggregates of immutable snapshots.

## Migration Plan

No schema change, no data migration, no seed change. The feature runs on the existing `orders (status, created_at)` and `order_items (name_ru, name_en, quantity)` columns. Rollback is code-only (revert RED + GREEN changes) — no DB state to undo.

## Open Questions

- **None for RED.** GREEN may choose to cache the aggregation if measured latency exceeds its budget; RED does not pin a latency contract.
- **DST stability in Europe/Moscow** is settled: Russia removed DST in 2011 and has run permanent MSK (UTC+3) since; the conversion is stable. RED tests SHALL still use `zoneinfo` rather than a literal `+3h` to avoid a future-dated timezone rule change forcing a test rewrite.
