# admin-orders-api Specification

## Purpose
TBD - created by archiving change admin-orders-api-green. Update Purpose after archive.

## Requirements

_References: PDD §4.5 (admin panel surfaces), §5.4 (partial index `orders (status) WHERE status NOT IN (COMPLETED, CANCELLED)`), §6.1 (order state machine), §7.1 Phase 6 (Admin Panel), INV-010 (role isolation — staff queries live behind staff endpoints), INV-013 (PII isolation — `user_id` is an opaque UUID, no phone/full name returned)._

### Requirement: Staff-scoped list service

The system SHALL expose a service function `list_orders_for_staff(*, status_filter, type_filter, page, per_page, db_session) -> OrderListResponse` at `core_api.services.order_history`. It SHALL be distinct from the existing customer-scoped `list_orders` function — it MUST NOT filter by `user_id` and MUST NOT accept a `user_id` argument.

- `status_filter` accepts either a concrete `OrderStatus` member OR the string `"active"`.
  - `"active"` SHALL filter `status NOT IN (COMPLETED, CANCELLED)`, exploiting the partial index from PDD §5.4.
  - A concrete `OrderStatus` SHALL filter `status = <value>`.
- `type_filter` accepts `None` (no filter) or a concrete `OrderType` member.
- `page: int >= 1`, `per_page: int in [1, 100]`.
- Ordering:
  - When `status_filter == "active"` OR `status_filter` is a non-finalized `OrderStatus` (any value other than `COMPLETED` or `CANCELLED`) — rows SHALL be ordered `created_at DESC`.
  - When `status_filter` is `COMPLETED` or `CANCELLED` — rows SHALL be ordered `updated_at DESC`.
- The returned `OrderListResponse` (from `core_api.schemas.order_history`) SHALL contain the paginated `orders`, the full `total_count` (ignoring `page`/`per_page`), and echoed `page`/`per_page`.

#### Scenario: Default "active" filter excludes completed and cancelled orders
- **GIVEN** orders in statuses `{CREATED, PAID, PREPARING, READY, IN_DELIVERY, COMPLETED, CANCELLED}` seeded under multiple users
- **WHEN** the service is called with `status_filter="active"`
- **THEN** the returned `orders` SHALL include every non-finalized order and SHALL NOT include any `COMPLETED` or `CANCELLED` order

#### Scenario: Concrete status filter returns only that status
- **GIVEN** orders across all statuses
- **WHEN** the service is called with `status_filter=OrderStatus.PREPARING`
- **THEN** every returned row SHALL have `status == OrderStatus.PREPARING`

#### Scenario: Type filter is AND-combined with status
- **GIVEN** a mix of `OrderType.PICKUP` and `OrderType.DELIVERY` orders in PREPARING
- **WHEN** the service is called with `status_filter=OrderStatus.PREPARING, type_filter=OrderType.DELIVERY`
- **THEN** every returned row SHALL have both `status == PREPARING` AND `type == DELIVERY`

#### Scenario: Active feed is ordered by created_at DESC
- **GIVEN** three active orders with `created_at` at T1 < T2 < T3
- **WHEN** the service is called with `status_filter="active"`
- **THEN** the returned `orders` SHALL be ordered `[T3, T2, T1]`

#### Scenario: Finalized feed is ordered by updated_at DESC
- **GIVEN** three CANCELLED orders with `updated_at` at U1 < U2 < U3 (created_at differs)
- **WHEN** the service is called with `status_filter=OrderStatus.CANCELLED`
- **THEN** the returned `orders` SHALL be ordered `[U3, U2, U1]`

#### Scenario: Pagination yields exact slice and stable total
- **GIVEN** 25 active orders
- **WHEN** the service is called with `status_filter="active", page=2, per_page=10`
- **THEN** `total_count` SHALL equal 25 AND `orders` SHALL contain exactly the DESC-ranked rows 11..20

#### Scenario: Staff see orders of every user
- **GIVEN** user A with 2 active orders and user B with 3 active orders
- **WHEN** the service is called with `status_filter="active"`
- **THEN** `total_count` SHALL equal 5 AND the returned `orders` SHALL contain rows from both `user_id == A.id` and `user_id == B.id`

### Requirement: Staff-scoped detail service

The system SHALL expose a service function `get_order_for_staff(order_id, db_session) -> OrderResponse` at `core_api.services.order_history`. The function SHALL NOT perform an ownership check and SHALL return the order for any `user_id` that owns it. If the id is unknown the function SHALL raise `OrderNotFoundForStaffError` (defined in the same module).

#### Scenario: Staff read another user's order
- **GIVEN** an order owned by user B
- **WHEN** the service is called with that `order_id`
- **THEN** the function SHALL return an `OrderResponse` whose `user_id == B.id`, WITHOUT raising any ownership error

#### Scenario: Unknown order id raises not-found
- **GIVEN** an id that is not present in the `orders` table
- **WHEN** the service is called with that id
- **THEN** the function SHALL raise `OrderNotFoundForStaffError`

### Requirement: GET /api/v1/admin/orders list endpoint

The system SHALL expose `GET /api/v1/admin/orders` at `core_api.routers.admin_orders`. The route SHALL be open to `{ADMIN, BARISTA}` only via RBAC; CUSTOMER and COURIER SHALL receive 403; requests without a valid Bearer token SHALL receive 401. Query parameters:

- `status: OrderStatus | "active"` — default `"active"`.
- `type: OrderType | None` — optional.
- `page: int = Query(1, ge=1)`.
- `per_page: int = Query(20, ge=1, le=100)`.

Response body: `OrderListResponse` from `core_api.schemas.order_history`.

#### Scenario: Route is registered exactly once
- **WHEN** a test inspects `app.routes` for a GET matching `/api/v1/admin/orders`
- **THEN** the match count SHALL equal 1

#### Scenario: 401 without Authorization header
- **WHEN** a client sends `GET /api/v1/admin/orders` without an `Authorization` header
- **THEN** the response status SHALL be 401

#### Scenario: 403 for customer role
- **WHEN** a client sends `GET /api/v1/admin/orders` with a customer JWT
- **THEN** the response status SHALL be 403

#### Scenario: 403 for courier role
- **WHEN** a client sends `GET /api/v1/admin/orders` with a courier JWT
- **THEN** the response status SHALL be 403

#### Scenario: 422 when per_page exceeds 100
- **WHEN** a client sends `GET /api/v1/admin/orders?per_page=101` with an admin JWT
- **THEN** the response status SHALL be 422 (FastAPI Query `le=100` violation)

#### Scenario: Admin sees active orders by default
- **GIVEN** orders exist across active and finalized statuses for multiple users
- **WHEN** an admin sends `GET /api/v1/admin/orders`
- **THEN** the response SHALL be 200 AND the returned `orders` SHALL exclude every `COMPLETED` and `CANCELLED` row

#### Scenario: Type filter narrows the feed
- **GIVEN** active orders exist with both `type=PICKUP` and `type=DELIVERY`
- **WHEN** an admin sends `GET /api/v1/admin/orders?type=delivery`
- **THEN** every returned row SHALL have `type == "delivery"`

#### Scenario: Barista access is identical to admin
- **GIVEN** orders are seeded
- **WHEN** a barista sends `GET /api/v1/admin/orders`
- **THEN** the response status SHALL be 200 with the same body shape the admin receives

#### Scenario: Admin feed contains rows from multiple users
- **GIVEN** orders owned by user A and user B
- **WHEN** an admin sends `GET /api/v1/admin/orders`
- **THEN** the returned `orders` SHALL contain rows where `user_id == A.id` AND rows where `user_id == B.id`

### Requirement: GET /api/v1/admin/orders/{order_id} detail endpoint

The system SHALL expose `GET /api/v1/admin/orders/{order_id}` at `core_api.routers.admin_orders`. The route SHALL be open to `{ADMIN, BARISTA}` only; CUSTOMER and COURIER SHALL receive 403; requests without a valid Bearer token SHALL receive 401. There SHALL NOT be an ownership check — staff SHALL be able to read any user's order. Unknown `order_id` SHALL return 404. Response body: `OrderResponse` from `core_api.schemas.order_history`, including the `user_id` field.

#### Scenario: Route is registered exactly once
- **WHEN** a test inspects `app.routes` for a GET matching `/api/v1/admin/orders/{order_id}`
- **THEN** the match count SHALL equal 1

#### Scenario: 401 without Authorization header
- **WHEN** a client sends `GET /api/v1/admin/orders/<uuid>` without an `Authorization` header
- **THEN** the response status SHALL be 401

#### Scenario: 403 for customer role
- **WHEN** a client sends `GET /api/v1/admin/orders/<uuid>` with a customer JWT
- **THEN** the response status SHALL be 403

#### Scenario: Admin reads order of another user
- **GIVEN** an order belongs to user B
- **WHEN** an admin sends `GET /api/v1/admin/orders/<order_id>`
- **THEN** the response SHALL be 200 AND `body["user_id"] == str(B.id)`

#### Scenario: Barista reads order of another user
- **GIVEN** an order belongs to user B
- **WHEN** a barista sends `GET /api/v1/admin/orders/<order_id>`
- **THEN** the response SHALL be 200 AND `body["user_id"] == str(B.id)`

#### Scenario: 404 on unknown order id
- **WHEN** an admin sends `GET /api/v1/admin/orders/<random-uuid>`
- **THEN** the response status SHALL be 404

### Requirement: RBAC matrix registers the admin-orders prefix

`core_api.rbac_matrix.ROUTE_MATRIX` SHALL contain rows for `("GET", "/api/v1/admin/orders")` and `("GET", "/api/v1/admin/orders/{order_id}")` with the role set `{ADMIN, BARISTA}`. The same routes SHALL NOT appear in `PUBLIC_ROUTES`.

#### Scenario: Admin-orders routes map to admin + barista only
- **WHEN** a test reads `ROUTE_MATRIX[("GET", "/api/v1/admin/orders")]` and `ROUTE_MATRIX[("GET", "/api/v1/admin/orders/{order_id}")]`
- **THEN** each value SHALL equal `{ADMIN, BARISTA}`

#### Scenario: Admin-orders routes are not public
- **WHEN** a test reads `PUBLIC_ROUTES`
- **THEN** neither `("GET", "/api/v1/admin/orders")` nor `("GET", "/api/v1/admin/orders/{order_id}")` SHALL be present

### Requirement: Customer-scoped endpoints remain unchanged

The existing `/api/v1/orders/*` routes and the customer-scoped `list_orders` service SHALL remain unmodified. Staff SHALL reach order data strictly via the new `/api/v1/admin/orders/*` prefix and the new `list_orders_for_staff` / `get_order_for_staff` helpers.

#### Scenario: Customer `list_orders` signature is untouched
- **WHEN** a test introspects `inspect.signature(core_api.services.order_history.list_orders)`
- **THEN** the signature SHALL include a `user_id` parameter

#### Scenario: Existing `/api/v1/orders/{order_id}` row still lists CUSTOMER
- **WHEN** a test reads `ROUTE_MATRIX[("GET", "/api/v1/orders/{order_id}")]`
- **THEN** the value SHALL still contain `CUSTOMER`
