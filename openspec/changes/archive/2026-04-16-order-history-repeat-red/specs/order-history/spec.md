## ADDED Requirements

_References: PDD §7.7 (Order history, Repeat Order Chain), §5.2 (Order, OrderItem), INV-002 (auth for mutations — applies to the history read only as authorization), INV-013 (PII isolation — reads user-scoped data by opaque UUID), INV-014 (order items are immutable snapshots)._

### Requirement: Paginated order history service lists only caller's orders

The system SHALL expose a service function `list_orders(user_id: UUID, page: int = 1, per_page: int = 20, db_session: Session) -> OrderListResponse` at `core_api.services.order_history`. It SHALL query the `orders` table filtered by `user_id`, sort by `created_at DESC`, paginate with SQL `OFFSET (page - 1) * per_page LIMIT per_page`, and return a DTO containing the paginated `orders` (with their `order_items` eagerly loaded via joined/selectinload), a `total_count: int` equal to the full count of that user's orders, and echoed `page` / `per_page` values.

In the RED change this symbol MUST NOT exist. Every scenario below MUST fail with `ImportError` (or `ModuleNotFoundError`) when the test imports the target symbol inside the test body.

#### Scenario: RED — service module is absent
- **WHEN** a test body executes `from core_api.services.order_history import list_orders`
- **THEN** the import SHALL raise `ModuleNotFoundError` or `ImportError`, and the assertion wrapping this import SHALL fail the test

#### Scenario: Returns empty response for user with no orders
- **GIVEN** a user_id that has no rows in `orders`
- **WHEN** the service is called with that user_id
- **THEN** it SHALL return `OrderListResponse(orders=[], total_count=0, page=1, per_page=20)` (assertion deferred to GREEN; RED test pins the expected shape via dict/attr comparison and is expected to fail due to missing implementation)

#### Scenario: Sort order is created_at DESC
- **GIVEN** three orders for a user created at times T1 < T2 < T3
- **WHEN** the service is called with `page=1, per_page=20`
- **THEN** the returned `orders` list SHALL be ordered `[T3, T2, T1]`

#### Scenario: Pagination yields exact slice and stable total
- **GIVEN** 25 orders for a user
- **WHEN** the service is called with `page=2, per_page=10`
- **THEN** `total_count` SHALL equal 25 AND `orders` SHALL contain exactly the rows with DESC rank 11..20

#### Scenario: Cross-user isolation
- **GIVEN** user A with 3 orders and user B with 2 orders
- **WHEN** the service is called with user A's id
- **THEN** `total_count` SHALL equal 3 AND none of the returned rows SHALL have `user_id == B.id`

#### Scenario: Order items are eagerly loaded
- **WHEN** the service returns an order that has ≥1 `order_items` row
- **THEN** accessing `order.items` on the returned instance SHALL NOT emit additional SQL queries (joined/selectinload)

### Requirement: GET /api/v1/orders router serves paginated own-history

The system SHALL expose `GET /api/v1/orders` at `core_api.routers.order_history`. The route SHALL require the `customer` role via the existing RBAC dependency. Query parameters: `page: int = Query(1, ge=1)`, `per_page: int = Query(20, ge=1, le=50)`. Response body: `OrderListResponse`. It SHALL resolve the caller's `user_id` from the JWT `sub` claim and forward it to `list_orders`.

In the RED change this route MUST NOT be registered in `core_api.main.app`. Requests SHALL return HTTP 404.

#### Scenario: RED — route is not registered
- **WHEN** a test sends `GET /api/v1/orders` with a valid customer JWT
- **THEN** the response status SHALL be 404 (the route is absent until GREEN)

#### Scenario: 401 without Authorization header
- **GIVEN** the route is registered (GREEN phase)
- **WHEN** a client sends `GET /api/v1/orders` without an `Authorization` header
- **THEN** the response status SHALL be 401

#### Scenario: 403 for non-customer role
- **GIVEN** the route is registered
- **WHEN** a client sends `GET /api/v1/orders` with a barista JWT
- **THEN** the response status SHALL be 403

#### Scenario: 422 when per_page exceeds 50
- **GIVEN** the route is registered
- **WHEN** a client sends `GET /api/v1/orders?per_page=51` with a customer JWT
- **THEN** the response status SHALL be 422 (FastAPI Query `le=50` violation)

#### Scenario: Caller sees only own orders
- **GIVEN** the route is registered, and two users A and B each have seeded orders
- **WHEN** a client sends `GET /api/v1/orders` with A's JWT
- **THEN** every `order.user_id` in the response SHALL equal A's id

#### Scenario: Empty history returns 200 with empty list
- **GIVEN** the route is registered and a customer has no orders
- **WHEN** the client sends `GET /api/v1/orders`
- **THEN** the response status SHALL be 200 AND the body SHALL be `{"orders": [], "total_count": 0, "page": 1, "per_page": 20}`

### Requirement: Single-order detail is NOT duplicated

The order-history capability SHALL NOT introduce a route `GET /api/v1/orders/{order_id}`. That route is owned by the order-checkout capability in `core_api.routers.orders`.

#### Scenario: No duplicate route registration
- **WHEN** an introspection test collects the FastAPI route map
- **THEN** exactly one route SHALL match method `GET` + path `/api/v1/orders/{order_id}`
