## ADDED Requirements

_References: PDD §3 (Cart, Cart Item), PDD §5.3 (Redis — `cart:{session_id}`), PDD §7.1 Phase 2 (Menu & Cart), INV-006 (stop list / server-computed prices), INV-010 (customer role isolation)._

### Requirement: Cart API client wrapper

The system SHALL expose a typed client module `web/customer/src/api/cart.ts` that calls the customer cart endpoints through `authenticatedFetch`. It SHALL export at minimum `getCart(): Promise<CartResponse>`, `addItem(payload: CartItemCreate): Promise<CartResponse>`, `updateItem(itemId: string, body: { quantity: number }): Promise<CartResponse>`, and `removeItem(itemId: string): Promise<CartResponse>`. The TypeScript types SHALL mirror `core_api.schemas.cart` (`CartItemCreate`, `CartItemResponse`, `CartResponse`, including `unit_price`, `line_total`, `subtotal`, `currency`, `expires_at`, and the snapshot sub-types). The module SHALL NOT hand-roll URL strings in pages.

#### Scenario: getCart issues a GET to the cart route
- **WHEN** `getCart()` is called with a mocked fetch
- **THEN** the mock SHALL receive exactly one `GET /api/v1/cart` request with the auth header provided by `authenticatedFetch`

#### Scenario: addItem posts the CartItemCreate body
- **WHEN** `addItem({ menu_item_id: 3, size_option_id: 1, modifier_ids: [4], quantity: 1 })` is called
- **THEN** the mock SHALL receive a `POST /api/v1/cart/items` whose JSON body equals the provided payload

#### Scenario: removeItem issues DELETE on the item id
- **WHEN** `removeItem("abc-123")` is called
- **THEN** the mock SHALL receive a `DELETE /api/v1/cart/items/abc-123` request

### Requirement: Cart store holds the last server response

The system SHALL expose a cart store at `web/customer/src/store/cart.ts` that holds the last `CartResponse` returned by the API and exposes actions `refresh()`, `addItem(payload)`, `updateQuantity(itemId, quantity)`, and `removeItem(itemId)`. Every action SHALL delegate to the cart API client and replace the stored `CartResponse` with the server's response. The store SHALL NOT mutate `items`, `line_total`, or `subtotal` locally between requests — prices and totals come exclusively from the server (INV-006). The store SHALL expose derived selectors `items`, `subtotal`, `currency`, `expiresAt`, and `itemCount` (sum of `quantity`), all read from the stored response.

#### Scenario: addItem replaces store state with server response
- **WHEN** `addItem` is called and the API resolves with a `CartResponse` containing `subtotal = 40000`
- **THEN** the store's `subtotal` selector SHALL return `40000` and `items` SHALL equal the server response's `items` array reference-equally

#### Scenario: updateQuantity replaces store state with server response
- **WHEN** `updateQuantity("item-1", 3)` is called and the API returns a new `CartResponse`
- **THEN** the store's state SHALL equal the returned response, and no local arithmetic on `line_total` SHALL have taken place

#### Scenario: Failed action does not mutate the store
- **WHEN** `removeItem("item-1")` is called and the API rejects with HTTP 500
- **THEN** the store state SHALL be unchanged from before the call and the rejection SHALL propagate to the caller

#### Scenario: itemCount sums item quantities from the response
- **WHEN** the stored `CartResponse` has items with quantities `[1, 2, 3]`
- **THEN** the `itemCount` selector SHALL return `6`

### Requirement: Cart page renders items from CartResponse

The system SHALL render a `CartPage` at route `/cart` that calls `refresh()` on mount and renders the store's `items`. Each line SHALL display: bilingual `menu_item_snapshot.name` (switched by `i18n.language`), selected `size_snapshot.label` when present, selected `modifiers_snapshot` names joined with a bilingual separator, `unit_price` and `line_total` formatted in rubles, and quantity controls. The page SHALL show a loading skeleton on the initial fetch and a localized error state with a retry control on fetch failure.

#### Scenario: Each item renders its snapshot text and line total
- **WHEN** the `CartResponse` contains one item with `unit_price = 20000`, `quantity = 2`, `line_total = 40000`, and a size snapshot label `L`
- **THEN** the rendered line SHALL display the bilingual name, the label `L`, `200 ₽` as unit price, and `400 ₽` as line total (or their localized equivalents)

#### Scenario: Modifiers snapshot is rendered
- **WHEN** an item has `modifiers_snapshot` of length 2
- **THEN** both modifier names SHALL be rendered on the line separated by the localized separator

### Requirement: Quantity controls and item removal hit the server

Each cart line SHALL render `+`, `−`, and remove controls. Pressing `+` or `−` SHALL call the store's `updateQuantity(itemId, newQuantity)` action with the item's current quantity plus or minus one, clamped to the range `[1, 99]` per `cart-schema`. Pressing remove SHALL call `removeItem(itemId)`. The `−` control SHALL be disabled when `quantity === 1`; the `+` control SHALL be disabled when `quantity === 99`. Between the click and the server response, the control SHALL be disabled to prevent double-submits. No UI path SHALL compute the new `line_total` or `subtotal` locally — the store replaces state on the server's response.

#### Scenario: Increment at quantity 1 calls updateQuantity with 2
- **WHEN** a line shows quantity 1 and the user presses `+`
- **THEN** `updateQuantity(itemId, 2)` SHALL be called exactly once

#### Scenario: Decrement is disabled at quantity 1
- **WHEN** a line shows quantity 1
- **THEN** the `−` control SHALL be rendered as disabled and clicking it SHALL NOT call any action

#### Scenario: Increment is disabled at quantity 99
- **WHEN** a line shows quantity 99
- **THEN** the `+` control SHALL be rendered as disabled and clicking it SHALL NOT call any action

#### Scenario: Remove control calls removeItem
- **WHEN** the user presses remove on a line
- **THEN** `removeItem(itemId)` SHALL be called exactly once and the store SHALL be updated from the server's response

### Requirement: Subtotal and currency are read from the server

The cart page SHALL render the server-provided `subtotal` formatted in rubles together with the `currency` code (always `RUB` per `cart-schema`). The subtotal line SHALL be pinned to the bottom of the viewport on mobile screens and SHALL update whenever the store's `CartResponse` changes. The rendered subtotal value SHALL be exactly `subtotal / 100` — no local recomputation, no fallback to summing `line_total` on the client.

#### Scenario: Subtotal mirrors the server field
- **WHEN** the store holds a `CartResponse` with `subtotal = 123450`
- **THEN** the rendered subtotal SHALL read `1 234,50 ₽` (or the localized equivalent)

#### Scenario: Subtotal updates after a quantity change
- **WHEN** `updateQuantity` resolves with a new `CartResponse` whose `subtotal` differs from the previous state
- **THEN** the rendered subtotal SHALL reflect the new server value on the next render

### Requirement: Empty cart state

When the stored `CartResponse.items` is an empty array, the cart page SHALL render a localized empty-state message and a primary action button linking to `/menu`. In this state the subtotal line SHALL NOT be rendered.

#### Scenario: Empty cart hides the subtotal line
- **WHEN** the store holds a `CartResponse` with `items = []`
- **THEN** the subtotal line SHALL NOT be rendered and the empty-state message SHALL be visible

#### Scenario: Empty cart links to menu
- **WHEN** the empty-state primary action is clicked
- **THEN** the router SHALL navigate to `/menu`

### Requirement: Cart page is gated by customer authentication

`/cart` SHALL be mounted behind the existing `requireAuth` guard from `frontend-routing`. Unauthenticated visitors SHALL be redirected to `/login` preserving the `/cart` return URL (INV-010).

#### Scenario: Unauthenticated visit redirects to login
- **WHEN** an unauthenticated user navigates to `/cart`
- **THEN** the router SHALL redirect to `/login?redirect=/cart`
