## ADDED Requirements

_References: PDD §4.5 (Admin Panel — аналитика/статистика, ADMIN-only), §5.2 (orders, order_items tables), §6.1 (COMPLETED terminal, money realised), §7.1 Phase 6 item 1 (Dashboard со статистикой: выручка, кол-во заказов, популярные позиции), INV-010 (role isolation — aggregates are ADMIN-only), INV-014 (immutable order_items — popular items group on the snapshot)._

### Requirement: Range computation helper

The system SHALL expose a helper `compute_range(range_param: Literal["today","week","month"]) -> tuple[datetime, datetime]` at `core_api.services.admin_stats`. The helper SHALL return a half-open `[start, end)` UTC interval such that:

- `end` SHALL equal `datetime.now(timezone.utc)` (the helper's own current clock read).
- `range_param == "today"` SHALL set `start` to **local midnight of today in `Europe/Moscow`** converted to UTC. The shop timezone SHALL be hardcoded as `TIMEZONE = "Europe/Moscow"` in the module; `shop_settings` does NOT carry a timezone column.
- `range_param == "week"` SHALL set `start = end - timedelta(days=7)`.
- `range_param == "month"` SHALL set `start = end - timedelta(days=30)`.

In the RED change this symbol MUST NOT exist. Every scenario below MUST fail with `ImportError` / `ModuleNotFoundError` when the test imports the target symbol inside the test body.

#### Scenario: RED — compute_range symbol is absent
- **WHEN** a test body executes `from core_api.services.admin_stats import compute_range`
- **THEN** the import SHALL raise `ImportError` / `ModuleNotFoundError`, failing the test

#### Scenario: today range starts at local midnight in Europe/Moscow
- **GIVEN** the helper exists (GREEN phase)
- **WHEN** a test calls `compute_range("today")`
- **THEN** the returned `start` SHALL equal the UTC datetime corresponding to `date.today()` at 00:00 in `zoneinfo.ZoneInfo("Europe/Moscow")`
- **AND** `start` SHALL NOT equal UTC midnight of the same calendar date (enforcing the +3h Moscow offset)

#### Scenario: week range spans the preceding 7 days
- **GIVEN** the helper exists
- **WHEN** a test calls `compute_range("week")`
- **THEN** `end - start` SHALL equal `timedelta(days=7)` (±2 second tolerance for wall-clock drift)
- **AND** `end` SHALL be within 2 seconds of `datetime.now(timezone.utc)`

#### Scenario: month range spans the preceding 30 days
- **GIVEN** the helper exists
- **WHEN** a test calls `compute_range("month")`
- **THEN** `end - start` SHALL equal `timedelta(days=30)` (±2 second tolerance)

### Requirement: Revenue and order-count aggregation helper

The system SHALL expose a helper `get_revenue_and_count(db: Session, start: datetime, end: datetime) -> tuple[int, int]` at `core_api.services.admin_stats`. The helper SHALL execute a single SQL aggregation that returns `(COALESCE(SUM(orders.total), 0), COUNT(*))` filtered by `status = OrderStatus.COMPLETED` AND `start <= created_at < end`. `orders.total` is already in kopecks and already includes `delivery_fee` — no further arithmetic SHALL be applied.

In the RED change this symbol MUST NOT exist.

#### Scenario: RED — symbol is absent
- **WHEN** a test body executes `from core_api.services.admin_stats import get_revenue_and_count`
- **THEN** the import SHALL raise `ImportError` / `ModuleNotFoundError`

#### Scenario: Empty range returns (0, 0)
- **GIVEN** no COMPLETED orders exist in `[start, end)`
- **WHEN** the helper runs
- **THEN** the result SHALL equal `(0, 0)`

#### Scenario: Only COMPLETED orders contribute
- **GIVEN** three COMPLETED orders with totals `t1, t2, t3`, one CANCELLED order, and one PAID order all within `[start, end)`
- **WHEN** the helper runs
- **THEN** the result SHALL equal `(t1 + t2 + t3, 3)` (neither CANCELLED nor PAID counts)

#### Scenario: Out-of-range orders excluded
- **GIVEN** one COMPLETED order with `created_at < start` and one COMPLETED order with `created_at >= end`
- **WHEN** the helper runs
- **THEN** the result SHALL equal `(0, 0)` for that pair

### Requirement: Popular-items aggregation helper (INV-014 snapshot fidelity)

The system SHALL expose a helper `get_popular_items(db: Session, start: datetime, end: datetime, limit: int = 10) -> list[PopularItem]` at `core_api.services.admin_stats`. The helper SHALL `SELECT order_items.name_ru, order_items.name_en, SUM(order_items.quantity) AS quantity` joined to `orders` filtered by `orders.status = OrderStatus.COMPLETED` AND `start <= orders.created_at < end`, `GROUP BY order_items.name_ru, order_items.name_en`, `ORDER BY quantity DESC`, `LIMIT :limit`.

The grouping key SHALL be the **snapshot** `(name_ru, name_en)` from `order_items` (INV-014), NOT `menu_item_id` — a rename of a menu item mid-range SHALL produce two distinct rows in the output.

In the RED change this symbol MUST NOT exist.

#### Scenario: RED — symbol is absent
- **WHEN** a test body executes `from core_api.services.admin_stats import get_popular_items`
- **THEN** the import SHALL raise `ImportError` / `ModuleNotFoundError`

#### Scenario: Same snapshot name aggregates to one row
- **GIVEN** two COMPLETED orders within `[start, end)`, each with one line item whose `(name_ru, name_en) = ("Латте", "Latte")` and quantity 2 and 3 respectively
- **WHEN** the helper runs
- **THEN** the result SHALL contain exactly one row with `name_ru="Латте", name_en="Latte", quantity=5`

#### Scenario: Renamed menu item produces two rows (INV-014 snapshot fidelity)
- **GIVEN** two COMPLETED orders within `[start, end)` where both line items share `menu_item_id` but one has snapshot `("Латте", "Latte")` and the other has snapshot `("Латте Ваниль", "Vanilla Latte")`, each quantity 1
- **WHEN** the helper runs
- **THEN** the result SHALL contain exactly two distinct rows, each with `quantity=1`, preserving the original snapshot names

#### Scenario: Limit caps the list at ten
- **GIVEN** eleven distinct snapshot `(name_ru, name_en)` keys within `[start, end)`, each with a unique quantity across COMPLETED orders
- **WHEN** the helper runs with `limit=10`
- **THEN** the result SHALL contain exactly ten rows
- **AND** rows SHALL be ordered by `quantity DESC`

#### Scenario: Cancelled orders excluded from popularity
- **GIVEN** one CANCELLED order with a line item `("X", "X", quantity=99)` and one COMPLETED order with a line item `("Y", "Y", quantity=1)`
- **WHEN** the helper runs
- **THEN** the result SHALL contain only the `"Y"` row — the cancelled order's line item SHALL NOT appear

### Requirement: GET /api/v1/admin/stats endpoint contract

The system SHALL expose `GET /api/v1/admin/stats` at `core_api.routers.admin_stats`. The route SHALL be open to `{ADMIN}` only via RBAC; BARISTA, COURIER, CUSTOMER SHALL receive 403; requests without a valid Bearer token SHALL receive 401. Query parameters:

- `range: Literal["today","week","month"]` — default `"month"`.

Response body `AdminStatsResponse` (Pydantic v2 schema at `core_api.schemas.admin_stats`):

```
{
  "range": "month",
  "range_start": "<iso8601 UTC>",
  "range_end":   "<iso8601 UTC>",
  "revenue_kopecks": 1234500,
  "orders_count": 42,
  "popular_items": [
    {"name_ru": "Латте", "name_en": "Latte", "quantity": 28},
    ...
  ]
}
```

In the RED change this route MUST NOT be registered. Requests hitting the path SHALL fail via the RBAC middleware default-deny (role-rejection or unknown-route rejection).

#### Scenario: RED — route not registered, barista denied
- **WHEN** a client sends `GET /api/v1/admin/stats` with a barista JWT
- **THEN** the response status SHALL be 403

#### Scenario: RED — route not registered, courier denied
- **WHEN** a client sends `GET /api/v1/admin/stats` with a courier JWT
- **THEN** the response status SHALL be 403

#### Scenario: RED — route not registered, customer denied
- **WHEN** a client sends `GET /api/v1/admin/stats` with a customer JWT
- **THEN** the response status SHALL be 403

#### Scenario: RED — no Authorization header yields 401
- **WHEN** a client sends `GET /api/v1/admin/stats` with no `Authorization` header
- **THEN** the response status SHALL be 401

#### Scenario: GREEN — unknown range yields 422
- **GIVEN** the route is registered (GREEN phase)
- **WHEN** an admin sends `GET /api/v1/admin/stats?range=bogus`
- **THEN** the response status SHALL be 422 (FastAPI `Literal` rejection)

#### Scenario: GREEN — admin default-range returns month window
- **GIVEN** the route is registered
- **WHEN** an admin sends `GET /api/v1/admin/stats` (no query param)
- **THEN** the response status SHALL be 200
- **AND** `body["range"] == "month"`
- **AND** `body["range_end"] - body["range_start"]` SHALL equal 30 days

### Requirement: RBAC matrix registers admin-only stats route

`core_api.rbac_matrix.ROUTE_MATRIX` SHALL contain a row for `("GET", "/api/v1/admin/stats")` with role set `{ADMIN}`. The same route SHALL NOT appear in `PUBLIC_ROUTES`. BARISTA, COURIER, and CUSTOMER SHALL NOT appear in the route's role set.

In the RED change this row MUST NOT exist.

#### Scenario: RED — rbac matrix row is missing
- **WHEN** a test asserts `("GET", "/api/v1/admin/stats") in ROUTE_MATRIX`
- **THEN** the assertion SHALL fail

#### Scenario: GREEN — admin-stats route maps to ADMIN only
- **GIVEN** GREEN has landed
- **WHEN** a test reads `ROUTE_MATRIX[("GET", "/api/v1/admin/stats")]`
- **THEN** the value SHALL equal `{ADMIN}`

#### Scenario: GREEN — admin-stats route is not public
- **GIVEN** GREEN has landed
- **WHEN** a test reads `PUBLIC_ROUTES`
- **THEN** `("GET", "/api/v1/admin/stats")` SHALL NOT be present
