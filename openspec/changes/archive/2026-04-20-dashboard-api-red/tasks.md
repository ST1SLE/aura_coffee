## 1. RED — compute_range helper tests

- [x] 1.1 [core-api] RED: Create `services/core-api/tests/test_admin_stats_range.py::test_compute_range_symbol_absent` — imports `from core_api.services.admin_stats import compute_range` inside the test body; asserts callable. Expected RED: `ImportError`.
- [x] 1.2 [core-api] RED: Add `test_compute_range_today_starts_at_europe_moscow_midnight` — imports `compute_range` + `zoneinfo.ZoneInfo`; calls `compute_range("today")`; asserts returned `start` equals the UTC datetime of `date.today()` at 00:00 in `ZoneInfo("Europe/Moscow")` and that `start != datetime.combine(date.today(), time.min, tzinfo=UTC)` (proves TZ offset is applied, not UTC midnight).
- [x] 1.3 [core-api] RED: Add `test_compute_range_today_end_is_now_utc` — calls `compute_range("today")`; asserts `end` is within 2 seconds of a fresh `datetime.now(timezone.utc)` call and has `tzinfo == timezone.utc`.
- [x] 1.4 [core-api] RED: Add `test_compute_range_week_spans_seven_days` — calls `compute_range("week")`; asserts `abs((end - start) - timedelta(days=7)) < timedelta(seconds=2)` and `end` is within 2 seconds of `datetime.now(timezone.utc)`.
- [x] 1.5 [core-api] RED: Add `test_compute_range_month_spans_thirty_days` — calls `compute_range("month")`; asserts `abs((end - start) - timedelta(days=30)) < timedelta(seconds=2)`.
- [x] 1.6 [core-api] RED: Add `test_compute_range_returns_half_open_interval_with_start_lt_end` — calls `compute_range("today"|"week"|"month")` (parametrize); asserts `start < end` for every range.

## 2. RED — get_revenue_and_count aggregation tests

- [x] 2.1 [core-api] RED: Create `services/core-api/tests/test_admin_stats_revenue.py::test_get_revenue_and_count_symbol_absent` — imports `from core_api.services.admin_stats import get_revenue_and_count` inside the test body; asserts callable. Expected RED: `ImportError`.
- [x] 2.2 [core-api] RED: Add `test_get_revenue_and_count_empty_range_returns_zeros` — uses `migrated_db_session`; seeds zero orders in a chosen past window (e.g. `[2020-01-15 → 2020-01-16)` so no other seeds contaminate); asserts result `== (0, 0)`.
- [x] 2.3 [core-api] RED: Add `test_get_revenue_and_count_sums_only_completed` — uses `migrated_db_session`; via `tests._factories.orders.make_user` + direct `Order` inserts, seeds THREE COMPLETED orders with totals `(10000, 25000, 40000)`, ONE CANCELLED (`total=99999`), ONE PAID (`total=99999`) — all with `created_at` inside a tight window `[T0, T1)`; calls `get_revenue_and_count(db, T0, T1)`; asserts result `== (75000, 3)`.
- [x] 2.4 [core-api] RED: Add `test_get_revenue_and_count_excludes_out_of_range_orders` — seeds ONE COMPLETED order with `created_at = T0 - 1h` and ONE COMPLETED with `created_at = T1 + 1h`; calls `get_revenue_and_count(db, T0, T1)`; asserts result `== (0, 0)`.
- [x] 2.5 [core-api] RED: Add `test_get_revenue_and_count_respects_half_open_interval` — seeds ONE COMPLETED order at exactly `created_at = T1` (the `end` boundary); calls with `(T0, T1)`; asserts it is NOT counted (half-open `[start, end)`).

## 3. RED — get_popular_items aggregation tests

- [x] 3.1 [core-api] RED: Create `services/core-api/tests/test_admin_stats_popular.py::test_get_popular_items_symbol_absent` — imports `from core_api.services.admin_stats import get_popular_items` inside the test body; asserts callable. Expected RED: `ImportError`.
- [x] 3.2 [core-api] RED: Add `test_get_popular_items_same_snapshot_aggregates_to_one_row` — uses `migrated_db_session`; seeds TWO COMPLETED orders in window `[T0, T1)`, each with one `OrderItem` snapshot `(name_ru="Латте", name_en="Latte")`, quantities 2 and 3; calls `get_popular_items(db, T0, T1)`; asserts result has exactly one matching row with `name_ru="Латте", name_en="Latte", quantity=5`.
- [x] 3.3 [core-api] RED: Add `test_get_popular_items_different_snapshots_produce_two_rows` — seeds TWO COMPLETED orders in window; first has `OrderItem` with snapshot `("Латте", "Latte")`, second with snapshot `("Латте Ваниль", "Vanilla Latte")`. Each quantity 1. Both point at the same `menu_item_id`. Calls helper; asserts result has exactly two distinct rows (INV-014 snapshot fidelity), each `quantity=1`.
- [x] 3.4 [core-api] RED: Add `test_get_popular_items_cancelled_excluded` — seeds ONE CANCELLED order with `OrderItem("X","X",quantity=99)` and ONE COMPLETED order with `OrderItem("Y","Y",quantity=1)` — both in window; calls helper; asserts result contains only the `"Y"` row and the `"X"` row is absent.
- [x] 3.5 [core-api] RED: Add `test_get_popular_items_limits_to_ten_ordered_desc` — seeds eleven COMPLETED orders in window, each with one `OrderItem` having a unique `(name_ru_i, name_en_i)` pair and quantity `i ∈ 1..11`; calls helper with `limit=10`; asserts `len(result) == 10` and the result is ordered by `quantity DESC` (top row quantity == 11, tenth row quantity == 2, quantity=1 row excluded).
- [x] 3.6 [core-api] RED: Add `test_get_popular_items_out_of_range_excluded` — seeds TWO COMPLETED orders, one with `created_at = T0 - 1h` (snapshot `("A","A",qty=100)`) and one with `created_at` inside window (snapshot `("B","B",qty=1)`); calls helper; asserts result contains only the `"B"` row.

## 4. RED — RBAC + router contract tests

- [x] 4.1 [core-api] RED: Create `services/core-api/tests/test_admin_stats_rbac.py::test_admin_stats_matrix_row_is_admin_only` — imports `from core_api.rbac_matrix import ROUTE_MATRIX, ADMIN`; asserts `ROUTE_MATRIX[("GET", "/api/v1/admin/stats")] == {ADMIN}`. Expected RED: `KeyError` (row absent).
- [x] 4.2 [core-api] RED: Add `test_admin_stats_matrix_row_excludes_barista_courier_customer` — imports `ROUTE_MATRIX, BARISTA, COURIER, CUSTOMER`; asserts each role is NOT in `ROUTE_MATRIX[("GET", "/api/v1/admin/stats")]`. Expected RED: `KeyError`.
- [x] 4.3 [core-api] RED: Add `test_admin_stats_route_not_public` — imports `PUBLIC_ROUTES`; asserts `("GET", "/api/v1/admin/stats") not in PUBLIC_ROUTES`. This test MAY pass trivially in RED (desired GREEN invariant locked here).
- [x] 4.4 [core-api] RED: Add `test_admin_stats_requires_authorization` — uses `client` fixture; sends `GET /api/v1/admin/stats` with NO `Authorization` header; asserts status 401.
- [x] 4.5 [core-api] RED: Add `test_admin_stats_rejects_barista` — uses `client` + `barista_headers`; sends `GET /api/v1/admin/stats`; asserts status 403.
- [x] 4.6 [core-api] RED: Add `test_admin_stats_rejects_courier` — uses `client` + `courier_headers`; asserts status 403.
- [x] 4.7 [core-api] RED: Add `test_admin_stats_rejects_customer` — uses `client` + `customer_headers`; asserts status 403.
- [x] 4.8 [core-api] RED: Add `test_admin_stats_rejects_unknown_range` — uses `client` + `admin_headers`; sends `GET /api/v1/admin/stats?range=bogus`; asserts status 422. Expected RED: route not registered so middleware returns 403 (admin path, RBAC may still reject before parameter parsing) — if RED returns something other than 422 it still satisfies "test fails"; GREEN must flip to 422.

## 5. VERIFY — RED suite is RED

- [x] 5.1 [core-api] VERIFY: Run `docker compose exec core-api pytest services/core-api/tests/test_admin_stats_range.py services/core-api/tests/test_admin_stats_revenue.py services/core-api/tests/test_admin_stats_popular.py services/core-api/tests/test_admin_stats_rbac.py -v` and confirm every new test fails (mix of `ImportError`, `KeyError`, assertion, or wrong-status). Confirm that pre-existing tests in the suite still pass (sanity check: `docker compose exec core-api pytest services/core-api/tests/ -q --ignore=services/core-api/tests/test_admin_stats_range.py --ignore=services/core-api/tests/test_admin_stats_revenue.py --ignore=services/core-api/tests/test_admin_stats_popular.py --ignore=services/core-api/tests/test_admin_stats_rbac.py`). Record the failing test count in the apply log.
