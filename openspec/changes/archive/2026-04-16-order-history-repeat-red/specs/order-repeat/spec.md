## ADDED Requirements

_References: PDD §7.7 (Repeat Order Chain), §5.2 (Order, OrderItem — `menu_item_id` and `size_option_id` are non-FK references so archived menu items do not break history), INV-002 (auth for mutations — repeat writes to cart), INV-006 (stop list), INV-013 (PII isolation), INV-014 (order items are immutable snapshots — repeat reads, never writes `order_items`)._

### Requirement: Repeat-order service replays a historical order into the cart at current prices

The system SHALL expose a service function `repeat_order(order_id: UUID, user_id: UUID, redis: redis.Redis, db_session: Session) -> RepeatOrderResult` at `core_api.services.order_repeat`.

Algorithm (PDD §7.7):
1. Load the `Order` by `order_id`. If not found, OR if `order.user_id != user_id`, the service SHALL raise an authorization/not-found error that the router layer maps to HTTP 404.
2. For each `OrderItem` on the loaded order, the service SHALL look up the current `MenuItem` by `order_item.menu_item_id`:
   - If `MenuItem` is missing (deleted), the entire item SHALL be skipped with a `menu_item_deleted` notification (`"Позиция больше не в меню"`).
   - If `MenuItem.archived == True`, the entire item SHALL be skipped with a `menu_item_archived` notification (`"{name} больше не в меню"`).
   - If `MenuItem.available == False` (stop-list), the entire item SHALL be skipped with a `menu_item_unavailable` notification (`"{name} сейчас недоступен"`).
   - Otherwise, the service SHALL resolve size and modifiers:
     - If `order_item.size_option_id` is set: look up the `SizeOption`. If missing OR `available == False`, the ENTIRE item SHALL be skipped with a `size_unavailable` notification (`"Размер {label} для {name} недоступен"`, using the order-item snapshot `size_label` and current `menu_item.name_ru`).
     - For each modifier id in `order_item.modifiers_snapshot`: look up the `Modifier`. If missing OR `available == False`, that modifier SHALL be dropped and a `modifier_unavailable` notification SHALL be appended, but the item SHALL still be added with the remaining modifiers.
   - The surviving item SHALL be added to the caller's cart via `CartService.add_item(CartItemCreate(menu_item_id=..., size_option_id=..., modifier_ids=[surviving_ids], quantity=order_item.quantity))`. Prices SHALL be read from the CURRENT menu (enforced by `CartService` hydrating from DB).
3. If ≥1 item was added, the service SHALL return `RepeatOrderResult(added_to_cart=<count>, skipped=<notifications>)`. If 0 items were added, the service SHALL raise an error that the router maps to HTTP 422 with message `"Ни одна позиция из этого заказа сейчас недоступна"`.
4. The service SHALL NOT auto-checkout; it only populates the cart. PDD §7.7 requires the client to review the cart.

In the RED change this symbol MUST NOT exist.

#### Scenario: RED — service module is absent
- **WHEN** a test body executes `from core_api.services.order_repeat import repeat_order`
- **THEN** the import SHALL raise `ModuleNotFoundError` or `ImportError`

#### Scenario: Happy path — all items available, current prices used
- **GIVEN** a historical order whose three items are fully available (menu items active, sizes available, modifiers available), where the current menu prices differ from the order-item `unit_price` snapshot
- **WHEN** `repeat_order` is invoked by the owning user
- **THEN** `CartService.add_item` SHALL be called 3 times
- **AND** each `CartItemCreate` passed SHALL NOT contain any price field (per cart-schema spec; `unit_price` is derived server-side from CURRENT menu)
- **AND** the returned `RepeatOrderResult.added_to_cart` SHALL equal 3
- **AND** `skipped` SHALL be empty

#### Scenario: Ownership violation raises authorization error
- **GIVEN** an order belonging to user B
- **WHEN** `repeat_order` is invoked with `user_id = A`
- **THEN** the service SHALL raise an error that the router maps to HTTP 404 (not 403, to avoid leaking existence)
- **AND** `CartService.add_item` SHALL NOT be called

#### Scenario: Stop-listed menu item is skipped with RU notification
- **GIVEN** an order item whose current `MenuItem.available == False`
- **WHEN** `repeat_order` runs
- **THEN** that item SHALL be absent from the cart additions
- **AND** `skipped` SHALL contain exactly one entry with `reason == "menu_item_unavailable"` and `message_ru == f"{menu_item.name_ru} сейчас недоступен"`

#### Scenario: Archived menu item is skipped with RU notification
- **GIVEN** an order item whose current `MenuItem.archived == True`
- **WHEN** `repeat_order` runs
- **THEN** that item SHALL be absent from the cart additions
- **AND** `skipped` SHALL contain an entry with `reason == "menu_item_archived"` and `message_ru == f"{menu_item.name_ru} больше не в меню"`

#### Scenario: Deleted menu item is skipped with RU notification
- **GIVEN** an order item whose `menu_item_id` is NOT present in the current `menu_items` table
- **WHEN** `repeat_order` runs
- **THEN** that item SHALL be absent from the cart additions
- **AND** `skipped` SHALL contain an entry with `reason == "menu_item_deleted"` and `message_ru == "Позиция больше не в меню"`

#### Scenario: Unavailable size skips the ENTIRE item
- **GIVEN** an order item whose current `MenuItem` is available BUT the referenced `SizeOption.available == False`
- **WHEN** `repeat_order` runs
- **THEN** that item SHALL be absent from the cart additions (the entire item is skipped, not just the size)
- **AND** `skipped` SHALL contain an entry with `reason == "size_unavailable"` and `message_ru == f"Размер {order_item.size_label} для {menu_item.name_ru} недоступен"`

#### Scenario: Unavailable modifier drops the modifier, keeps the item
- **GIVEN** an order item whose `MenuItem` and size are available, and whose `modifiers_snapshot` has two modifier ids — one available, one with `available == False`
- **WHEN** `repeat_order` runs
- **THEN** the item SHALL be added to the cart with ONLY the available modifier id in `CartItemCreate.modifier_ids`
- **AND** `skipped` SHALL contain exactly one entry with `reason == "modifier_unavailable"`

#### Scenario: All items unavailable raises a domain error
- **GIVEN** an order whose every item maps to something unavailable (stop-list / archived / deleted / size)
- **WHEN** `repeat_order` runs
- **THEN** it SHALL raise a domain error whose message equals `"Ни одна позиция из этого заказа сейчас недоступна"`
- **AND** `CartService.add_item` SHALL NOT be called

#### Scenario: Repeat does NOT create a new order row
- **GIVEN** a historical order with N items
- **WHEN** `repeat_order` runs (any branch — success or error)
- **THEN** the count of rows in `orders` SHALL be unchanged after the call

### Requirement: POST /api/v1/orders/{order_id}/repeat router

The system SHALL expose `POST /api/v1/orders/{order_id}/repeat` at `core_api.routers.order_history` (co-located with the history listing). The route SHALL require the `customer` role, resolve `user_id` from the JWT `sub`, invoke `repeat_order`, and return `RepeatOrderResult` as JSON with HTTP 200 on success.

Error mapping:
- Order not found OR not owned by caller → HTTP 404 (body `{"detail": "order_not_found"}`).
- All items unavailable → HTTP 422 with the Russian message from PDD §7.7 under `detail`.
- Auth/role failures → 401 / 403 via the standard RBAC layer.

In the RED change this route MUST NOT be registered. Requests SHALL return HTTP 404 because the path is absent (indistinguishable from order-not-found by status code, but in RED this 404 is because of missing route — asserted by absence in the OpenAPI route list).

#### Scenario: RED — route is not registered
- **WHEN** a test inspects `app.routes` for a POST route matching `/api/v1/orders/{order_id}/repeat`
- **THEN** no such route SHALL be found

#### Scenario: 401 without Authorization header
- **GIVEN** the route is registered (GREEN phase)
- **WHEN** the client sends POST to the endpoint without Authorization
- **THEN** the status SHALL be 401

#### Scenario: 403 for wrong role
- **GIVEN** the route is registered
- **WHEN** the client sends POST with a barista JWT
- **THEN** the status SHALL be 403

#### Scenario: 404 for another user's order
- **GIVEN** the route is registered, and an order owned by user B
- **WHEN** user A sends POST to `/api/v1/orders/{B_order_id}/repeat`
- **THEN** the status SHALL be 404

#### Scenario: 200 with RepeatOrderResult on success
- **GIVEN** the route is registered and an owned order with all items available
- **WHEN** the owning customer sends POST to the endpoint
- **THEN** the status SHALL be 200 AND the body SHALL deserialize into a `RepeatOrderResult` with `added_to_cart >= 1`
- **AND** the customer's Redis cart (key `cart:{user_id}`) SHALL contain the added items

#### Scenario: 422 when every item is unavailable
- **GIVEN** the route is registered and an owned order whose every item is unavailable
- **WHEN** the owning customer sends POST
- **THEN** the status SHALL be 422
- **AND** `response.json()["detail"]` SHALL equal `"Ни одна позиция из этого заказа сейчас недоступна"`

#### Scenario: Does NOT auto-checkout
- **WHEN** a successful repeat is performed
- **THEN** no new row SHALL be inserted into `orders` as a result of the repeat call
- **AND** no row SHALL be inserted into `payments` as a result of the repeat call
