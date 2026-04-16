## ADDED Requirements

_References: PDD §7.1 Phase 3 items 1-2, PDD §7.2 Order Pricing Chain, PDD §6.1 Order Lifecycle (CREATED/PAID), PDD §6.2 Payment Lifecycle (PENDING), INV-002, INV-004, INV-006, INV-013, INV-014._

### Requirement: Checkout service converts cart to order atomically

The system SHALL expose `core_api.services.checkout.create_order(user_id, request: CreateOrderRequest, redis_client, db_session) -> OrderResponse` that performs the full Cart → Order conversion in a single DB transaction (INV-004). The function SHALL read the Redis cart via `CartService.get()`, run validators (stop-list, working hours, delivery address when `type=DELIVERY`, promocode when provided), execute the PDD §7.2 pricing chain, persist `orders` + `order_items` + `payments` (and conditional `loyalty_transactions` + `promocode_usages`) in one transaction, and return the created `OrderResponse`. For `total > 0` the returned Order MUST have `status=CREATED`. For `total = 0` (full loyalty redemption) the Order SHALL be committed as `PAID` in the same transaction and the Redis cart SHALL be deleted after commit.

#### Scenario: Empty cart is rejected
- **GIVEN** the authenticated Customer has no `cart:{user_id}` key in Redis (or the cart contains zero items)
- **WHEN** `create_order` is invoked
- **THEN** the service SHALL raise a rejection mapped to HTTP `400 Bad Request` with Russian message "Корзина пуста" and SHALL NOT write any row to the database

#### Scenario: Stop-list validator failure aborts before any DB write
- **GIVEN** the cart contains at least one menu item whose `available = false`
- **WHEN** `create_order` is invoked
- **THEN** the service SHALL raise a validator error (propagated as HTTP `409`) and SHALL NOT insert any `orders`, `order_items`, `payments`, `loyalty_transactions`, or `promocode_usages` row

#### Scenario: Delivery type without valid address is rejected
- **GIVEN** `request.type = DELIVERY` and the delivery-address validator rejects the address (outside radius, or `subtotal < min_delivery_amount` per PDD §7.4)
- **WHEN** `create_order` is invoked
- **THEN** the service SHALL raise a validator error (HTTP `409`) and SHALL NOT touch the database

#### Scenario: Normal pickup order produces CREATED status with pending payment
- **GIVEN** a non-empty cart, type=PICKUP, no promocode, no loyalty points, all validators pass, pricing computes `total > 0`
- **WHEN** `create_order` is invoked
- **THEN** a new `orders` row SHALL exist with `status = CREATED`, one `order_items` row per cart line with immutable name/price/modifiers snapshots (INV-014), and one `payments` row with `status = PENDING`, `amount = total`, and a non-null `idempotency_key`

#### Scenario: Loyalty-only payment (total = 0) commits Order as PAID
- **GIVEN** a cart where pricing yields `total = 0` (loyalty covers the whole amount)
- **WHEN** `create_order` is invoked
- **THEN** the returned Order SHALL have `status = PAID`, the `loyalty_transaction` SHALL be persisted with `type = REDEMPTION` (not `RESERVATION`), the `payments.amount` SHALL be `0`, and after commit the Redis `cart:{user_id}` key SHALL be deleted

#### Scenario: Non-zero total enqueues Celery payment task after commit
- **GIVEN** a cart producing `total > 0`
- **WHEN** `create_order` is invoked
- **THEN** `enqueue_payment_task` SHALL be called exactly once with the new `order_id`, `total`, and `idempotency_key`, and the call SHALL happen AFTER the DB transaction commits (not before)

#### Scenario: Non-zero total retains the Redis cart
- **GIVEN** a successful `create_order` call with `total > 0`
- **WHEN** the function returns
- **THEN** the Redis `cart:{user_id}` key SHALL still exist (cart is deleted on `PAID`, not `CREATED`, per PDD §6.1)

#### Scenario: Loyalty reservation debits balance atomically
- **GIVEN** `request.points_to_use = 5000` and the Customer's loyalty balance is `5000`
- **WHEN** `create_order` is invoked with `total > 0`
- **THEN** a `loyalty_transactions` row with `type = RESERVATION` and `amount = -5000` SHALL exist, the `loyalty_accounts.balance` SHALL be decremented to `0`, and the `orders.points_used` SHALL equal `5000` — all inside the same DB transaction as the `orders` INSERT

#### Scenario: Promocode application increments usage counter
- **GIVEN** `request.promocode_code = "SUMMER20"` referencing a valid `ACTIVE` promocode with `current_uses = 0`
- **WHEN** `create_order` is invoked
- **THEN** `promocodes.current_uses` SHALL be `1` after commit, a `promocode_usages` row SHALL exist linking promocode + user + order, and `orders.discount_amount` SHALL equal the discount computed from §7.2 step 2

#### Scenario: Invalid promocode aborts the transaction
- **GIVEN** `request.promocode_code = "EXPIRED"` referencing a promocode whose validator rejects it
- **WHEN** `create_order` is invoked
- **THEN** no DB row SHALL be inserted and an error SHALL be raised (HTTP `409`)

### Requirement: Order items are immutable snapshots (INV-014)

Each `order_items` row created by `create_order` SHALL contain a frozen snapshot of the menu item's `name_ru`, `name_en`, `unit_price`, modifier list with names and prices (`modifiers_snapshot`), and size label + price (when applicable). These values SHALL be taken from the DB at checkout time — not from the Redis cart — so that later UPDATE/ARCHIVE of the menu item cannot change historical order data. The columns `menu_item_id` and `size_option_id` SHALL be stored as plain references (no FK) so that archiving the menu does not break order history (PDD §7.7).

#### Scenario: Snapshot captures current DB prices, not Redis
- **GIVEN** a cart line referencing `MenuItem(base_price = 15000)`, and the DB price is updated to `17000` before checkout
- **WHEN** `create_order` is invoked
- **THEN** the resulting `order_items.unit_price` SHALL be `17000` (fresh DB read at checkout time)

#### Scenario: Modifier snapshot persists even after modifier archival
- **GIVEN** an order is placed with modifier `M1 (price = 5000)`, and after commit the modifier is deleted/archived
- **WHEN** the order is later read
- **THEN** the `order_items.modifiers_snapshot` JSONB SHALL still contain `M1` with its original name and price

### Requirement: POST /api/v1/orders creates an order for the authenticated Customer

The system SHALL expose `POST /api/v1/orders` accepting a `CreateOrderRequest` body. The route SHALL be restricted to role `CUSTOMER` via the RBAC matrix. On success the route SHALL return `201 Created` with body `OrderResponse`. Errors SHALL map to: `400` on empty cart, `409` on validator failure, `422` on Pydantic validation failure, `401` on missing/invalid token, `403` on non-customer role.

#### Scenario: Customer creates pickup order (happy path)
- **GIVEN** a Customer with a non-empty valid cart and `type=PICKUP`
- **WHEN** the Customer POSTs a valid `CreateOrderRequest` with a JWT Authorization header
- **THEN** the response SHALL be `201 Created` with `OrderResponse` whose `status=created`, and the body SHALL contain `items`, `subtotal`, `total`, `estimated_accrual`

#### Scenario: Empty cart produces 400
- **GIVEN** a Customer with an empty Redis cart
- **WHEN** the Customer POSTs `/api/v1/orders`
- **THEN** the response SHALL be `400 Bad Request`

#### Scenario: Validator failure produces 409
- **GIVEN** the cart contains a stop-listed item
- **WHEN** the Customer POSTs `/api/v1/orders`
- **THEN** the response SHALL be `409 Conflict`

#### Scenario: Unauthenticated caller is rejected
- **WHEN** a request without a valid Bearer token hits `POST /api/v1/orders`
- **THEN** the response SHALL be `401 Unauthorized`

#### Scenario: Staff role is forbidden
- **WHEN** a Barista-role JWT is sent to `POST /api/v1/orders`
- **THEN** the response SHALL be `403 Forbidden`

#### Scenario: Malformed body yields 422
- **WHEN** the Customer POSTs a body with an unknown `type` value
- **THEN** the response SHALL be `422 Unprocessable Entity`

### Requirement: GET /api/v1/orders/{order_id} returns order detail for polling

The system SHALL expose `GET /api/v1/orders/{order_id}` returning `OrderResponse`. The route SHALL be restricted to `CUSTOMER`. A Customer SHALL only see their own orders; a request for a foreign order (or a non-existent id) SHALL return `404 Not Found` (do not leak existence). The response SHALL include `confirmation_url` when it has been populated by the payment-worker, enabling the client to poll every 1-2 s while `status = CREATED`.

#### Scenario: Customer fetches own order detail
- **GIVEN** a Customer has a persisted Order with `status = CREATED` and a `Payment.confirmation_url` recently set
- **WHEN** the Customer GETs `/api/v1/orders/{order_id}`
- **THEN** the response SHALL be `200` with `OrderResponse.id`, `status`, `items`, `total`, and `confirmation_url` populated

#### Scenario: Foreign order is 404
- **GIVEN** Customer A authenticates and Customer B owns an order
- **WHEN** Customer A GETs `/api/v1/orders/{B's order_id}`
- **THEN** the response SHALL be `404 Not Found` (same response as unknown id)

#### Scenario: Non-existent order id is 404
- **WHEN** the Customer GETs `/api/v1/orders/{random UUID}`
- **THEN** the response SHALL be `404 Not Found`

#### Scenario: Staff role is forbidden
- **WHEN** an Admin JWT is sent to `GET /api/v1/orders/{order_id}`
- **THEN** the response SHALL be `403 Forbidden`

### Requirement: Orders router is registered in main.py with RBAC matrix coverage

The `core_api.main` module SHALL include `orders_router`, and `core_api.rbac_matrix.ROUTE_MATRIX` SHALL contain both new routes mapping to `{CUSTOMER}` only. Staff roles (ADMIN, BARISTA, COURIER) SHALL NOT be authorized for any orders route (INV-010). Route coverage (`test_route_coverage.py`) SHALL pass for the new routes without additions to `PUBLIC_ROUTES`.

#### Scenario: RBAC matrix contains both orders routes
- **WHEN** `core_api.rbac_matrix.ROUTE_MATRIX` is inspected
- **THEN** it SHALL contain `("POST", "/api/v1/orders") -> {"customer"}` and `("GET", "/api/v1/orders/{order_id}") -> {"customer"}`

#### Scenario: OpenAPI exposes both operations
- **WHEN** `/openapi.json` is fetched
- **THEN** it SHALL declare `post` on `/api/v1/orders` and `get` on `/api/v1/orders/{order_id}`
