# order-history Specification

## Purpose
TBD - created by archiving change order-history-repeat-green. Update Purpose after archive.
## Requirements
### Requirement: Paginated order history service lists only caller's orders

The system SHALL expose `list_orders(user_id: UUID, page: int = 1, per_page: int = 20, db_session: Session) -> OrderListResponse` at `core_api.services.order_history`. It SHALL query the `orders` table filtered by `user_id`, sort by `created_at DESC`, paginate with `OFFSET (page - 1) * per_page LIMIT per_page`, and return `OrderListResponse(orders=[OrderResponse, ...], total_count, page, per_page)`. `order_items` SHALL be eagerly loaded via `selectinload(Order.items)` so that traversing `order.items` emits no further SQL. `total_count` SHALL be the full count of that user's orders (unaffected by page/per_page).

#### Scenario: Returns empty response for user with no orders
- **WHEN** `list_orders` is called with a user_id that has no rows in `orders`
- **THEN** it SHALL return `OrderListResponse(orders=[], total_count=0, page=1, per_page=20)`

#### Scenario: Sort order is created_at DESC
- **GIVEN** three orders for a user created at times T1 < T2 < T3
- **WHEN** `list_orders` is called with `page=1, per_page=20`
- **THEN** `result.orders` SHALL be ordered `[T3, T2, T1]`

#### Scenario: Pagination yields exact slice and stable total
- **GIVEN** 25 orders for a user
- **WHEN** `list_orders` is called with `page=2, per_page=10`
- **THEN** `result.total_count` SHALL equal 25 AND `result.orders` SHALL be exactly the DESC-ranked rows 11..20

#### Scenario: Cross-user isolation
- **GIVEN** user A with 3 orders and user B with 2 orders
- **WHEN** `list_orders` is called with user A's id
- **THEN** `result.total_count` SHALL equal 3 AND every row SHALL have `user_id == A.id`

#### Scenario: Order items are eagerly loaded
- **WHEN** `list_orders` returns orders that each have ≥1 `order_items` rows
- **THEN** iterating `order.items` on every returned row SHALL NOT emit additional `SELECT FROM order_items` queries (verified via `before_cursor_execute` event listener)

### Requirement: GET /api/v1/orders router serves paginated own-history

The system SHALL expose `GET /api/v1/orders` at `core_api.routers.order_history`. The route SHALL be included in `core_api.main.app`, appear in `ROUTE_MATRIX` as `("GET", "/api/v1/orders"): {"customer"}`, accept query parameters `page: int = Query(1, ge=1)` and `per_page: int = Query(20, ge=1, le=50)`, resolve `user_id` from the JWT `sub` claim via `get_current_user`, invoke `list_orders`, and return `OrderListResponse` as JSON with status 200.

#### Scenario: 401 without Authorization header
- **WHEN** a client sends `GET /api/v1/orders` without an `Authorization` header
- **THEN** the response status SHALL be 401

#### Scenario: 403 for non-customer role
- **WHEN** a client sends `GET /api/v1/orders` with a barista JWT
- **THEN** the response status SHALL be 403

#### Scenario: 422 when per_page exceeds 50
- **WHEN** a client sends `GET /api/v1/orders?per_page=51` with a customer JWT
- **THEN** the response status SHALL be 422

#### Scenario: Caller sees only own orders
- **GIVEN** two users A and B each have seeded orders
- **WHEN** a client sends `GET /api/v1/orders` with A's JWT
- **THEN** every `order.user_id` in the response SHALL equal A's id

#### Scenario: Empty history returns 200 with empty list
- **GIVEN** a customer has no orders
- **WHEN** the client sends `GET /api/v1/orders`
- **THEN** the response status SHALL be 200 AND the body SHALL be `{"orders": [], "total_count": 0, "page": 1, "per_page": 20}`

#### Scenario: Exactly one matching GET /api/v1/orders route
- **WHEN** an introspection test collects `app.routes` for method `GET` + path `/api/v1/orders`
- **THEN** exactly one such route SHALL be registered

### Requirement: Single-order detail is NOT duplicated by order-history

The `order-history` capability SHALL NOT register a route `GET /api/v1/orders/{order_id}`. That route belongs to the `order-checkout` capability in `core_api.routers.orders`. Within this worktree alone, the RED scenario asserting "exactly one GET `/api/v1/orders/{order_id}` route" is marked XFAIL in the test file and SHALL become XPASS (and be cleared) after the `feat/order-checkout` branch is merged.

#### Scenario: No duplicate route registration
- **WHEN** an introspection test collects `app.routes` for method `GET` + path `/api/v1/orders/{order_id}`
- **THEN** at most one such route SHALL match, AND that route SHALL NOT be contributed by `core_api.routers.order_history`

