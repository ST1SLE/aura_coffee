# dashboard-api Specification

## Purpose
TBD - created by archiving change dashboard-api-red. Update Purpose after archive.
## Requirements
### Requirement: Range computation helper

Previously: "In the RED change this symbol MUST NOT exist. Every scenario below MUST fail with `ImportError`…" — and included an `RED — compute_range symbol is absent` scenario.

Now: the symbol exists and the scenarios assert behavior, not absence.

The system SHALL expose a helper `compute_range(range_param: Literal["today","week","month"]) -> tuple[datetime, datetime]` at `core_api.services.admin_stats`. The helper SHALL return a half-open `[start, end)` UTC interval such that:

- `end` SHALL equal `datetime.now(timezone.utc)` (the helper's own current clock read).
- `range_param == "today"` SHALL set `start` to **local midnight of today in `Europe/Moscow`** converted to UTC. The shop timezone SHALL be hardcoded as the module-level constant `TIMEZONE = "Europe/Moscow"`; `shop_settings` does NOT carry a timezone column.
- `range_param == "week"` SHALL set `start = end - timedelta(days=7)`.
- `range_param == "month"` SHALL set `start = end - timedelta(days=30)`.

#### Scenario: today range starts at local midnight in Europe/Moscow
- **WHEN** a test calls `compute_range("today")`
- **THEN** the returned `start` SHALL equal the UTC datetime corresponding to `date.today()` at 00:00 in `zoneinfo.ZoneInfo("Europe/Moscow")`
- **AND** `start` SHALL NOT equal UTC midnight of the same calendar date (enforcing the +3h Moscow offset)

#### Scenario: today range end is current UTC time
- **WHEN** a test calls `compute_range("today")`
- **THEN** the returned `end` SHALL have `tzinfo == timezone.utc`
- **AND** `end` SHALL be within 2 seconds of `datetime.now(timezone.utc)`

#### Scenario: week range spans the preceding 7 days
- **WHEN** a test calls `compute_range("week")`
- **THEN** `end - start` SHALL equal `timedelta(days=7)` (±2 second tolerance for wall-clock drift)
- **AND** `end` SHALL be within 2 seconds of `datetime.now(timezone.utc)`

#### Scenario: month range spans the preceding 30 days
- **WHEN** a test calls `compute_range("month")`
- **THEN** `end - start` SHALL equal `timedelta(days=30)` (±2 second tolerance)

#### Scenario: every range is half-open with start strictly less than end
- **WHEN** a test calls `compute_range(r)` for `r ∈ {"today","week","month"}`
- **THEN** `start < end` SHALL hold for every result

### Requirement: Revenue and order-count aggregation helper

Previously: "In the RED change this symbol MUST NOT exist" plus `RED — symbol is absent` scenario.

Now: the helper exists and the scenarios describe its SQL aggregation behavior.

The system SHALL expose a helper `get_revenue_and_count(db: Session, start: datetime, end: datetime) -> tuple[int, int]` at `core_api.services.admin_stats`. The helper SHALL execute a single SQL aggregation that returns `(COALESCE(SUM(orders.total), 0), COUNT(*))` filtered by `orders.status = OrderStatus.COMPLETED` AND `start <= orders.created_at < end`. `orders.total` is already in kopecks and already includes `delivery_fee` — no further arithmetic SHALL be applied.

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

#### Scenario: Half-open interval excludes orders at end boundary
- **GIVEN** one COMPLETED order with `created_at == end`
- **WHEN** the helper runs
- **THEN** that order SHALL NOT be counted — the result SHALL equal `(0, 0)`

### Requirement: Popular-items aggregation helper (INV-014 snapshot fidelity)

Previously: "In the RED change this symbol MUST NOT exist" plus `RED — symbol is absent` scenario.

Now: the helper exists and returns aggregated snapshot rows.

The system SHALL expose a helper `get_popular_items(db: Session, start: datetime, end: datetime, limit: int = 10) -> list[PopularItem]` at `core_api.services.admin_stats`. The helper SHALL `SELECT order_items.name_ru, order_items.name_en, SUM(order_items.quantity) AS quantity` joined to `orders` filtered by `orders.status = OrderStatus.COMPLETED` AND `start <= orders.created_at < end`, `GROUP BY order_items.name_ru, order_items.name_en`, `ORDER BY quantity DESC`, `LIMIT :limit`.

The grouping key SHALL be the **snapshot** `(name_ru, name_en)` from `order_items` (INV-014), NOT `menu_item_id` — a rename of a menu item mid-range SHALL produce two distinct rows in the output.

Each row of the return value SHALL expose attributes `name_ru: str`, `name_en: str`, `quantity: int`.

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

#### Scenario: Out-of-range orders excluded
- **GIVEN** one COMPLETED order with `created_at < start` (`quantity=100`) and one COMPLETED order with `created_at` inside `[start, end)` (`quantity=1`)
- **WHEN** the helper runs
- **THEN** only the in-range row SHALL appear in the result

### Requirement: GET /api/v1/admin/stats endpoint contract

Previously: "In the RED change this route MUST NOT be registered. Requests hitting the path SHALL fail via the RBAC middleware default-deny." RED-only scenarios named the 403/401 behavior as side-effects of the default-deny.

Now: the route is registered. 401 (missing Bearer) and 403 (non-ADMIN role) remain enforced via `RBACMiddleware`, but they now refer to the registered route, not a default-deny fallback. 422 for unknown `range` and 200 for the happy path are live.

The system SHALL expose `GET /api/v1/admin/stats` at `core_api.routers.admin_stats` and register it on the FastAPI app. The route SHALL be open to `{ADMIN}` only via `core_api.rbac_matrix.ROUTE_MATRIX`; BARISTA, COURIER, CUSTOMER SHALL receive 403; requests without a valid Bearer token SHALL receive 401. Query parameters:

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

#### Scenario: Barista is denied
- **WHEN** a client sends `GET /api/v1/admin/stats` with a barista JWT
- **THEN** the response status SHALL be 403

#### Scenario: Courier is denied
- **WHEN** a client sends `GET /api/v1/admin/stats` with a courier JWT
- **THEN** the response status SHALL be 403

#### Scenario: Customer is denied
- **WHEN** a client sends `GET /api/v1/admin/stats` with a customer JWT
- **THEN** the response status SHALL be 403

#### Scenario: Missing Authorization header yields 401
- **WHEN** a client sends `GET /api/v1/admin/stats` with no `Authorization` header
- **THEN** the response status SHALL be 401

#### Scenario: Unknown range yields 422
- **WHEN** an admin sends `GET /api/v1/admin/stats?range=bogus`
- **THEN** the response status SHALL be 422 (FastAPI `Literal` rejection)

#### Scenario: Admin default range returns a month window with a well-formed body
- **WHEN** an admin sends `GET /api/v1/admin/stats` (no query param)
- **THEN** the response status SHALL be 200
- **AND** `body["range"] == "month"`
- **AND** `body["range_end"] - body["range_start"]` SHALL equal 30 days (±2 s)
- **AND** `body["revenue_kopecks"]` SHALL be an integer ≥ 0
- **AND** `body["orders_count"]` SHALL be an integer ≥ 0
- **AND** `body["popular_items"]` SHALL be a list of length ≤ 10 whose items have `name_ru`, `name_en`, `quantity`

#### Scenario: Admin today range returns a today window anchored at Moscow midnight
- **WHEN** an admin sends `GET /api/v1/admin/stats?range=today`
- **THEN** the response status SHALL be 200
- **AND** `body["range"] == "today"`
- **AND** `body["range_start"]` SHALL equal local Moscow midnight of `date.today()` expressed as UTC ISO-8601

### Requirement: RBAC matrix registers admin-only stats route

Previously: "In the RED change this row MUST NOT exist" plus `RED — rbac matrix row is missing` scenario.

Now: the row exists.

`core_api.rbac_matrix.ROUTE_MATRIX` SHALL contain a row for `("GET", "/api/v1/admin/stats")` with role set `{ADMIN}`. The same route SHALL NOT appear in `PUBLIC_ROUTES`. BARISTA, COURIER, and CUSTOMER SHALL NOT appear in the route's role set.

#### Scenario: admin-stats route maps to ADMIN only
- **WHEN** a test reads `ROUTE_MATRIX[("GET", "/api/v1/admin/stats")]`
- **THEN** the value SHALL equal `{ADMIN}`

#### Scenario: admin-stats route excludes other roles
- **WHEN** a test reads `ROUTE_MATRIX[("GET", "/api/v1/admin/stats")]`
- **THEN** BARISTA, COURIER, and CUSTOMER SHALL NOT be members of the set

#### Scenario: admin-stats route is not public
- **WHEN** a test reads `PUBLIC_ROUTES`
- **THEN** `("GET", "/api/v1/admin/stats")` SHALL NOT be present

