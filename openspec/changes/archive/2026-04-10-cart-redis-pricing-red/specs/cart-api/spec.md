## ADDED Requirements

_References: PDD §3 (Cart, Cart Item), PDD §5.3 (Redis keys, `cart:{session_id}`, 24 h TTL), PDD §7.2 step 1 (Subtotal), INV-002 (auth for mutations), INV-006 (stop list), INV-010 (role isolation), INV-014 (immutable order items), INV-015 (secrets via env)._

### Requirement: GET /api/v1/cart returns the authenticated customer's cart

The system SHALL expose `GET /api/v1/cart` which returns a `CartResponse` for the authenticated Customer (`request.state.user_id`). The endpoint SHALL read Redis key `cart:{user_id}`, re-fetch fresh prices for every line from the menu tables, and compute `unit_price`, `line_total`, and `subtotal` via `core_api.services.pricing`. If the Redis key is missing or empty, the endpoint SHALL return an empty `CartResponse` (no items, `subtotal=0`, `expires_at=now + cart_ttl_seconds`). Every successful read SHALL renew the key TTL to `settings.cart_ttl_seconds`.

#### Scenario: Customer fetches empty cart
- **WHEN** an authenticated Customer with no `cart:{user_id}` key calls `GET /api/v1/cart`
- **THEN** the response SHALL be `200` with body `items=[]`, `subtotal=0`, `currency="RUB"`, and `expires_at` in the future

#### Scenario: Customer fetches populated cart with fresh prices
- **GIVEN** the cart has one line for a menu item whose `base_price` in the DB has just been updated from `15000` to `17000`
- **WHEN** the Customer calls `GET /api/v1/cart`
- **THEN** the returned `unit_price` and `line_total` SHALL reflect the new `17000` price, not the value at add time

#### Scenario: Unauthenticated caller is rejected
- **WHEN** a request without a valid Customer JWT hits `GET /api/v1/cart`
- **THEN** the response SHALL be `401 Unauthorized` and no Redis read SHALL occur

#### Scenario: Staff role is forbidden
- **WHEN** an authenticated Barista, Courier, or Admin calls `GET /api/v1/cart`
- **THEN** the response SHALL be `403 Forbidden` (INV-010)

#### Scenario: Read refreshes TTL
- **WHEN** an authenticated Customer calls `GET /api/v1/cart` on an existing key
- **THEN** the TTL of `cart:{user_id}` SHALL be reset to `settings.cart_ttl_seconds`

### Requirement: POST /api/v1/cart/items adds a cart line with server-side pricing

The system SHALL expose `POST /api/v1/cart/items` accepting a `CartItemCreate` body. The handler SHALL validate the referenced `menu_item_id`, `size_option_id`, and `modifier_ids` against the DB, enforce INV-006 (stop list), compute a deterministic `line_id` from `(menu_item_id, size_option_id, sorted(modifier_ids))`, and either insert a new line or increment the `quantity` of an existing line with the same `line_id`. On success it SHALL persist the updated cart in Redis with `EX settings.cart_ttl_seconds` and return the full `CartResponse`.

#### Scenario: Successful add creates a new line
- **GIVEN** an empty cart
- **WHEN** the Customer POSTs `{menu_item_id: 1, size_option_id: 3, modifier_ids: [5, 7], quantity: 2}` and all referenced ids are available
- **THEN** the response SHALL be `201` (or `200`, per GREEN decision) with one item in `items`, `unit_price` and `line_total` computed server-side, and the Redis key `cart:{user_id}` SHALL exist with TTL ≈ `cart_ttl_seconds`

#### Scenario: Adding the same item+size+modifiers merges quantity
- **GIVEN** a cart containing one line `(menu_item_id=1, size_option_id=3, modifier_ids=[5,7], quantity=2)`
- **WHEN** the Customer POSTs `(menu_item_id=1, size_option_id=3, modifier_ids=[7,5], quantity=1)` (modifier order MUST NOT matter)
- **THEN** the cart SHALL contain exactly one line with `quantity=3` and the same `line_id`

#### Scenario: Stop-listed menu item is rejected (INV-006)
- **GIVEN** `MenuItem.available = false`
- **WHEN** the Customer POSTs a `CartItemCreate` referencing that item
- **THEN** the response SHALL be `409 Conflict` with a `detail` explaining which item is unavailable, and Redis SHALL NOT be written

#### Scenario: Stop-listed modifier is rejected (INV-006)
- **GIVEN** a `Modifier` with `available = false` included in `modifier_ids`
- **WHEN** the Customer POSTs the request
- **THEN** the response SHALL be `409 Conflict` and Redis SHALL NOT be written

#### Scenario: Stop-listed size option is rejected (INV-006)
- **GIVEN** a `SizeOption` with `available = false` referenced by `size_option_id`
- **WHEN** the Customer POSTs the request
- **THEN** the response SHALL be `409 Conflict` and Redis SHALL NOT be written

#### Scenario: Size option belongs to a different menu item
- **GIVEN** `size_option_id` whose `SizeOption.menu_item_id` does not match the requested `menu_item_id`
- **WHEN** the Customer POSTs the request
- **THEN** the response SHALL be `409 Conflict`

#### Scenario: Modifier is not linked to this menu item
- **GIVEN** a `modifier_id` not present in `menu_item_modifiers` for the requested `menu_item_id`
- **WHEN** the Customer POSTs the request
- **THEN** the response SHALL be `409 Conflict`

#### Scenario: Unknown menu item id
- **WHEN** the Customer POSTs a `menu_item_id` that does not exist
- **THEN** the response SHALL be `404 Not Found`

#### Scenario: Merge exceeding the quantity cap is rejected
- **GIVEN** an existing line with `quantity = 95`
- **WHEN** the Customer POSTs the same line with `quantity = 10`
- **THEN** the response SHALL be `409 Conflict` and the stored quantity SHALL remain `95`

#### Scenario: Unauthenticated POST is rejected
- **WHEN** an anonymous request hits `POST /api/v1/cart/items`
- **THEN** the response SHALL be `401 Unauthorized` and Redis SHALL NOT be written

#### Scenario: Redis write sets TTL atomically with the value
- **WHEN** a successful add persists the cart
- **THEN** the Redis operation SHALL set the value and the TTL in a single command (e.g. `SET ... EX <cart_ttl_seconds>`), not two separate calls that could leave a TTL-less key on partial failure

### Requirement: PATCH /api/v1/cart/items/{line_id} replaces an existing line

The system SHALL expose `PATCH /api/v1/cart/items/{line_id}` accepting a `CartItemCreate` body. The handler SHALL locate the line whose deterministic `line_id` matches the path parameter, replace its `size_option_id`, `modifier_ids`, and `quantity`, re-validate against the menu tables (INV-006), recompute `line_id` from the new payload, and persist. Clients SHALL NOT provide `line_id` in the body.

#### Scenario: Quantity change succeeds
- **GIVEN** a cart with one line `(menu_item_id=1, size_option_id=3, modifier_ids=[5], quantity=2)`
- **WHEN** the Customer PATCHes that `line_id` with `quantity=4`
- **THEN** the response SHALL contain one line with `quantity=4` and `line_total` recomputed

#### Scenario: Changing modifiers recomputes line_id
- **GIVEN** a line with `line_id=A` and `modifier_ids=[5]`
- **WHEN** the Customer PATCHes `A` with `modifier_ids=[5, 7]`
- **THEN** the response SHALL contain one line whose new `line_id` differs from `A` and the old `line_id` SHALL NOT appear

#### Scenario: Unknown line_id returns 404
- **WHEN** the Customer PATCHes a `line_id` that does not exist in the cart
- **THEN** the response SHALL be `404 Not Found`

#### Scenario: Patching to a stop-listed state is rejected
- **WHEN** the PATCH body references a `size_option_id` that is now unavailable
- **THEN** the response SHALL be `409 Conflict` and the stored line SHALL be unchanged

### Requirement: DELETE /api/v1/cart/items/{line_id} removes one line

The system SHALL expose `DELETE /api/v1/cart/items/{line_id}`. If the line is found it SHALL be removed and the updated cart persisted with a refreshed TTL. Returning the remaining `CartResponse` is REQUIRED.

#### Scenario: Delete removes exactly one line
- **GIVEN** a cart with two lines `[A, B]`
- **WHEN** the Customer DELETEs line_id `A`
- **THEN** the response SHALL contain only line `B` and Redis SHALL reflect the same state

#### Scenario: Deleting a missing line_id returns 404
- **WHEN** the Customer DELETEs an unknown `line_id`
- **THEN** the response SHALL be `404 Not Found` and the existing cart SHALL remain unchanged

#### Scenario: Deleting the last line leaves an empty cart, not a missing key
- **GIVEN** a cart with exactly one line
- **WHEN** the Customer DELETEs that line
- **THEN** the response SHALL be an empty `CartResponse` and the Redis key SHALL either be deleted or store the canonical empty-cart representation (implementation choice; GET behavior MUST remain identical)

### Requirement: DELETE /api/v1/cart clears the whole cart

The system SHALL expose `DELETE /api/v1/cart` which deletes `cart:{user_id}` and returns an empty `CartResponse`.

#### Scenario: Clear removes the Redis key
- **GIVEN** a populated cart
- **WHEN** the Customer calls `DELETE /api/v1/cart`
- **THEN** `cart:{user_id}` SHALL be absent from Redis and the response SHALL be an empty `CartResponse`

#### Scenario: Clearing an already-empty cart is idempotent
- **WHEN** the Customer calls `DELETE /api/v1/cart` on a missing key
- **THEN** the response SHALL be `200` with an empty `CartResponse`; no error

### Requirement: Cart endpoints are RBAC-restricted to CUSTOMER

The `ROUTE_MATRIX` in `core_api.rbac_matrix` SHALL contain the following entries, each mapping to `{CUSTOMER}` and to nothing else:

- `("GET",    "/api/v1/cart")`
- `("DELETE", "/api/v1/cart")`
- `("POST",   "/api/v1/cart/items")`
- `("PATCH",  "/api/v1/cart/items/{line_id}")`
- `("DELETE", "/api/v1/cart/items/{line_id}")`

Staff roles (Admin, Barista, Courier) SHALL NOT be authorized for any cart endpoint (INV-010).

#### Scenario: Route coverage test passes
- **WHEN** `tests/test_route_coverage.py` enumerates mounted routes
- **THEN** every `/api/v1/cart*` route SHALL be present in `ROUTE_MATRIX` and absent from `PUBLIC_ROUTES`

#### Scenario: Staff JWT on POST /api/v1/cart/items
- **WHEN** a Barista-role JWT is sent to `POST /api/v1/cart/items`
- **THEN** the response SHALL be `403 Forbidden`

### Requirement: Redis storage contract and TTL

The system SHALL store each customer's cart at Redis key `cart:{user_id}` as a JSON string conforming to:

```
{"items": [{"menu_item_id": int, "size_option_id": int|null, "modifier_ids": [int, ...], "quantity": int}], "updated_at": "<ISO8601>"}
```

No field other than the four input fields plus `updated_at` SHALL be persisted. In particular, `unit_price`, `line_total`, `subtotal`, and snapshot fields SHALL NOT appear in Redis (INV-014 — prices are recomputed on every read). Every write SHALL set the TTL to `settings.cart_ttl_seconds` via a single atomic command.

#### Scenario: Redis payload contains no prices
- **WHEN** a cart is persisted after a successful POST
- **THEN** the JSON at `cart:{user_id}` SHALL NOT contain keys named `unit_price`, `line_total`, `price`, `subtotal`, `menu_item_snapshot`, `size_snapshot`, or `modifiers_snapshot`

#### Scenario: TTL is set on every write
- **WHEN** any POST/PATCH/DELETE/GET completes successfully on a non-empty cart
- **THEN** `TTL cart:{user_id}` SHALL return a value ≤ `settings.cart_ttl_seconds` and > 0

#### Scenario: cart_ttl_seconds is configurable via env
- **WHEN** `CART_TTL_SECONDS=60` is set and a fresh POST is made
- **THEN** the resulting TTL SHALL be ≤ 60 seconds

### Requirement: Cart service rejects unavailable components atomically

`CartService.add_item` and `CartService.update_item` SHALL load every referenced menu entity (`MenuItem`, optional `SizeOption`, all `Modifier`s, junction rows from `menu_item_modifiers`) in a single read before any Redis write. If any entity is missing or unavailable, the service SHALL raise `CartValidationError` before touching Redis. No partial update SHALL be visible.

#### Scenario: Rejection happens before Redis is touched
- **GIVEN** a POST that will be rejected due to a stop-listed modifier
- **WHEN** the handler runs
- **THEN** the Redis `cart:{user_id}` key SHALL NOT be written or modified

### Requirement: Stop-list on read is tolerant, not destructive

`GET /api/v1/cart` SHALL NOT remove or reject lines whose components became unavailable after they were added. It SHALL surface the current `available` state via the `MenuItemCartSnapshot.availability` / `SizeSnapshot` / `ModifierSnapshot` fields so the UI can present a warning.

#### Scenario: Stop-listed line is surfaced, not removed
- **GIVEN** a line added while `MenuItem.available = true`
- **WHEN** the item is stop-listed and the Customer then calls `GET /api/v1/cart`
- **THEN** the response SHALL still contain the line and `items[0].menu_item_snapshot.availability` SHALL be `STOP_LIST`
