## ADDED Requirements

_References: PDD §7.7 (Repeat Order Chain), §5.2 (Order, OrderItem — non-FK `menu_item_id`/`size_option_id` so archived menu items do not break history), INV-002 (auth for mutations — repeat writes to cart), INV-006 (stop list — enforced via CartService delegation), INV-013 (PII isolation), INV-014 (order_items are immutable — repeat reads, never writes `order_items`)._

_Previously: the `order-repeat` capability was introduced by the RED change `2026-04-16-order-history-repeat-red` with "module/route MUST NOT exist" scenarios. RED was not synced to the living specs by design. This GREEN change registers the live contract in full._

_Now: `core_api.services.order_repeat.repeat_order`, the domain errors `OrderNotFoundError` and `NoItemsAvailableError`, and the `POST /api/v1/orders/{order_id}/repeat` route all exist. All RED tests targeting this capability pass._

### Requirement: Repeat-order service replays a historical order into the cart at current prices

The system SHALL expose `repeat_order(order_id: UUID, user_id: UUID, redis: redis.Redis, db_session: Session) -> RepeatOrderResult` at `core_api.services.order_repeat`.

Algorithm (PDD §7.7):

1. Load `Order` by `order_id`. If absent OR `order.user_id != user_id`, raise `OrderNotFoundError`. The router SHALL map this to HTTP 404 with body `{"detail": "order_not_found"}` (no 403 — existence is not leaked).

2. For each `OrderItem` on the loaded order, look up the current `MenuItem` by `order_item.menu_item_id`:
   - If the `MenuItem` row is missing (deleted): skip the item with `RepeatOrderSkippedEntry(reason="menu_item_deleted", message_ru="Позиция больше не в меню")`.
   - If `MenuItem.archived == True`: skip with `reason="menu_item_archived"`, `message_ru=f"{menu_item.name_ru} больше не в меню"`.
   - If `MenuItem.available == False`: skip with `reason="menu_item_unavailable"`, `message_ru=f"{menu_item.name_ru} сейчас недоступен"`.
   - Otherwise, resolve size and modifiers:
     - If `order_item.size_option_id` is set: load `SizeOption`. If missing OR `available == False`, skip the ENTIRE item with `reason="size_unavailable"`, `message_ru=f"Размер {order_item.size_label} для {menu_item.name_ru} недоступен"`.
     - For each modifier id in `order_item.modifiers_snapshot`: the id SHALL be read as `entry["id"]` if the entry is a dict, else as `int(entry)` if scalar. Load `Modifier`. If missing OR `available == False`, drop that modifier and append `reason="modifier_unavailable"` to `skipped`; keep the item with the remaining modifiers.
   - The surviving item SHALL be added to the caller's cart via `CartService.add_item(CartItemCreate(menu_item_id=..., size_option_id=..., modifier_ids=[surviving_ids], quantity=order_item.quantity))`. `CartItemCreate` SHALL NOT include price fields — `CartService` hydrates current prices server-side.

3. If `added_to_cart == 0`, raise `NoItemsAvailableError("Ни одна позиция из этого заказа сейчас недоступна")`. Router maps to HTTP 422.

4. Otherwise return `RepeatOrderResult(added_to_cart=<int>, skipped=<list[RepeatOrderSkippedEntry]>)`.

5. The service SHALL NOT insert into `orders` or `payments`. It populates the cart only. PDD §7.7 requires the client to review before checkout.

#### Scenario: Happy path — all items available, current prices used
- **GIVEN** a historical order whose three items are fully available (menu items active, sizes available, modifiers available), and the current menu prices differ from `order_item.unit_price`
- **WHEN** `repeat_order` is invoked by the owning user
- **THEN** `CartService.add_item` SHALL be called 3 times AND each `CartItemCreate` SHALL NOT carry any price field AND `RepeatOrderResult.added_to_cart` SHALL equal 3 AND `skipped` SHALL be empty

#### Scenario: Ownership violation raises OrderNotFoundError
- **GIVEN** an order belonging to user B
- **WHEN** `repeat_order` is invoked with `user_id = A`
- **THEN** the service SHALL raise `OrderNotFoundError` AND `CartService.add_item` SHALL NOT be called

#### Scenario: Stop-listed menu item is skipped with RU notification
- **GIVEN** an order item whose current `MenuItem.available == False`
- **WHEN** `repeat_order` runs
- **THEN** that item SHALL be absent from cart additions AND `skipped` SHALL contain exactly one entry with `reason == "menu_item_unavailable"` and `message_ru == f"{menu_item.name_ru} сейчас недоступен"`

#### Scenario: Archived menu item is skipped with RU notification
- **GIVEN** an order item whose current `MenuItem.archived == True`
- **WHEN** `repeat_order` runs
- **THEN** `skipped` SHALL contain an entry with `reason == "menu_item_archived"` and `message_ru == f"{menu_item.name_ru} больше не в меню"`

#### Scenario: Deleted menu item is skipped with RU notification
- **GIVEN** an `order_item.menu_item_id` not present in the current `menu_items` table
- **WHEN** `repeat_order` runs
- **THEN** `skipped` SHALL contain an entry with `reason == "menu_item_deleted"` and `message_ru == "Позиция больше не в меню"`

#### Scenario: Unavailable size skips the ENTIRE item
- **GIVEN** an order item whose `MenuItem` is available BUT the referenced `SizeOption.available == False`
- **WHEN** `repeat_order` runs
- **THEN** the item SHALL be absent from cart additions AND `skipped` SHALL contain an entry with `reason == "size_unavailable"` and `message_ru == f"Размер {order_item.size_label} для {menu_item.name_ru} недоступен"`

#### Scenario: Unavailable modifier drops the modifier, keeps the item
- **GIVEN** an order item with `MenuItem` and size available, and `modifiers_snapshot` containing two modifier ids — one available, one `available == False`
- **WHEN** `repeat_order` runs
- **THEN** the item SHALL be added to the cart with ONLY the available modifier id in `CartItemCreate.modifier_ids` AND `skipped` SHALL contain exactly one entry with `reason == "modifier_unavailable"`

#### Scenario: All items unavailable raises NoItemsAvailableError
- **GIVEN** an order whose every item maps to something unavailable
- **WHEN** `repeat_order` runs
- **THEN** it SHALL raise `NoItemsAvailableError` whose message equals `"Ни одна позиция из этого заказа сейчас недоступна"` AND `CartService.add_item` SHALL NOT be called

#### Scenario: Repeat does NOT create a new order row
- **GIVEN** a historical order with N items
- **WHEN** `repeat_order` runs (success or error branch)
- **THEN** the count of rows in `orders` SHALL be unchanged after the call

#### Scenario: RepeatOrderResult carries exactly two fields
- **WHEN** a test introspects `RepeatOrderResult.model_fields`
- **THEN** the set of field names SHALL equal `{"added_to_cart", "skipped"}` with types `int` and `list[RepeatOrderSkippedEntry]`

### Requirement: POST /api/v1/orders/{order_id}/repeat router

The system SHALL expose `POST /api/v1/orders/{order_id}/repeat` at `core_api.routers.order_history`. The route SHALL be registered in `core_api.main.app`, appear in `ROUTE_MATRIX` as `("POST", "/api/v1/orders/{order_id}/repeat"): {"customer"}`, resolve `user_id` from the JWT `sub` claim, invoke `repeat_order`, and return `RepeatOrderResult` as JSON with status 200 on success.

Error mapping:
- `OrderNotFoundError` → HTTP 404 with body `{"detail": "order_not_found"}`.
- `NoItemsAvailableError` → HTTP 422 with body `{"detail": "Ни одна позиция из этого заказа сейчас недоступна"}`.
- Auth/role failures → 401 / 403 via the standard RBAC layer.

#### Scenario: 401 without Authorization header
- **WHEN** the client sends POST to the endpoint without an `Authorization` header
- **THEN** the status SHALL be 401

#### Scenario: 403 for wrong role
- **WHEN** the client sends POST with a barista JWT
- **THEN** the status SHALL be 403

#### Scenario: 404 for another user's order
- **GIVEN** an order owned by user B
- **WHEN** user A sends POST to `/api/v1/orders/{B_order_id}/repeat`
- **THEN** the status SHALL be 404 AND `response.json()["detail"]` SHALL equal `"order_not_found"`

#### Scenario: 200 with RepeatOrderResult on success
- **GIVEN** an owned order with all items available
- **WHEN** the owning customer sends POST
- **THEN** the status SHALL be 200 AND the body SHALL deserialize into `RepeatOrderResult` with `added_to_cart >= 1` AND the Redis key `cart:{user_id}` SHALL contain the added items

#### Scenario: 422 when every item is unavailable
- **GIVEN** an owned order whose every item is unavailable
- **WHEN** the owning customer sends POST
- **THEN** the status SHALL be 422 AND `response.json()["detail"]` SHALL equal `"Ни одна позиция из этого заказа сейчас недоступна"`

#### Scenario: Does NOT auto-checkout
- **WHEN** a successful repeat is performed
- **THEN** no new row SHALL be inserted into `orders` AND no row SHALL be inserted into `payments`

#### Scenario: Exactly one matching POST repeat route
- **WHEN** an introspection test collects `app.routes` for method `POST` + path `/api/v1/orders/{order_id}/repeat`
- **THEN** exactly one such route SHALL be registered
