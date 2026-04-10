## ADDED Requirements

_References: PDD §3 (Category, Menu Item, Modifier, Size Option, Stop List), PDD §7.1 Phase 2 (Menu & Cart), PDD §4 (Frontend — web/customer), INV-006 (stop list), INV-010 (customer role isolation)._

### Requirement: Menu API client wrapper

The system SHALL expose a typed client module `web/customer/src/api/menu.ts` that calls the public menu endpoints through the shared `authenticatedFetch` from `api/client.ts`. It SHALL export at minimum `listCategories(): Promise<CategoryResponse[]>`, `listMenuItems(params?: { categoryId?: number }): Promise<MenuItemResponse[]>`, and `getMenuItem(id: number): Promise<MenuItemResponse>`. The TypeScript response types SHALL mirror `core_api.schemas.menu` (bilingual names, `base_price`, `size_options`, `modifiers`, `available`, `archived`). The module SHALL NOT contain hand-rolled URL strings spread across pages — every request SHALL go through a single function per endpoint.

#### Scenario: listCategories issues a GET to the public menu route
- **WHEN** `listCategories()` is called with a mocked fetch
- **THEN** the mock SHALL receive exactly one `GET /api/v1/menu/categories` request with the auth header provided by `authenticatedFetch`

#### Scenario: listMenuItems forwards the categoryId filter
- **WHEN** `listMenuItems({ categoryId: 7 })` is called
- **THEN** the issued request SHALL be `GET /api/v1/menu/items?category_id=7`

#### Scenario: HTTP errors surface as rejected promises
- **WHEN** the mocked fetch returns HTTP 500 for `GET /api/v1/menu/items`
- **THEN** the returned promise SHALL reject with an error carrying the status code, and no partial data SHALL be returned

### Requirement: Menu page lists categories and items

The system SHALL render a `MenuPage` at route `/menu` that fetches categories on mount, renders them in PDD `sort_order` order, and for each category renders its menu items in a grid. Each item card SHALL display bilingual name (switched by `i18n.language`), localized description when present, `base_price` formatted in rubles (kopecks divided by 100, locale-aware), and the `image_url` when set. The page SHALL show a loading skeleton while fetching and a localized error message on fetch failure.

#### Scenario: Categories render in sort order
- **WHEN** the API returns three categories with `sort_order` values `[30, 10, 20]`
- **THEN** the page SHALL render them top-to-bottom in the order `[10, 20, 30]`

#### Scenario: Empty menu renders an empty-state message
- **WHEN** the API returns zero categories
- **THEN** the page SHALL render a localized "menu is empty" message and no item grid

#### Scenario: Fetch failure renders an error message with retry
- **WHEN** `listCategories()` rejects
- **THEN** the page SHALL render a localized error message and a "retry" control that re-invokes the fetch

### Requirement: Menu item stop list is respected in the UI

Menu items whose `available` field is `false` (stop list) OR whose `archived` field is `true` SHALL be rendered as visually disabled (greyed out, non-clickable) in the grid, with a localized "unavailable" badge. The UI SHALL NOT open the item-detail card for such items, and the Add-to-Cart action SHALL be unreachable. The client SHALL NOT attempt to infer availability from any field other than those returned by the server (INV-006).

#### Scenario: Unavailable item is not clickable
- **WHEN** the item grid contains a `MenuItemResponse` with `available = false`
- **THEN** clicking its card SHALL NOT open the detail view and SHALL NOT call any API

#### Scenario: Archived item renders unavailable badge
- **WHEN** the item grid contains a `MenuItemResponse` with `archived = true`
- **THEN** the card SHALL render the localized "unavailable" badge and SHALL be non-interactive

### Requirement: Item detail card with size and modifier selection

The `MenuPage` SHALL open an item-detail view (card, drawer, or modal — the visual form is unspecified) when the user taps an available item. The detail view SHALL render all `size_options` as a single-select control and all `modifiers` as a multi-select control. If the item has at least one size option, one SHALL be preselected (the first by server order) and the user MUST pick exactly one before Add-to-Cart is enabled. Modifier selection SHALL default to empty and is always optional. The detail view SHALL display a live "current price" label equal to `size_option.price` (or `base_price` when the item has no sizes) plus the sum of selected `modifier.price` values, all formatted in rubles. Unavailable size options and unavailable modifiers SHALL be disabled in the controls.

#### Scenario: Selecting a larger size updates the displayed price
- **WHEN** the user selects size `L` whose `price` is `22000` on an item with base price `15000`
- **THEN** the displayed current price SHALL read `220 ₽` (or the localized equivalent), independent of `base_price`

#### Scenario: Adding a modifier updates the displayed price
- **WHEN** a size priced at `15000` is selected and the user toggles a modifier priced at `5000`
- **THEN** the displayed current price SHALL read `200 ₽`

#### Scenario: Unavailable size option is disabled
- **WHEN** one of the item's size options has `available = false`
- **THEN** that option SHALL render as disabled and SHALL NOT be selectable

#### Scenario: Add-to-Cart is blocked until a size is selected
- **WHEN** the item has two size options and none is selected (hypothetical forced state)
- **THEN** the Add-to-Cart button SHALL be disabled

### Requirement: Add-to-Cart posts the selection to the cart API

When the user clicks Add-to-Cart in the item-detail view, the page SHALL call the cart API client's add-item action with `{ menu_item_id, size_option_id, modifier_ids, quantity: 1 }`, then refresh the cart store from the response. The page SHALL NOT compute `unit_price` or `line_total` locally — prices MUST always come from the server response (INV-006). On success the detail view SHALL close and a localized "added to cart" toast SHALL be shown. On failure an error toast SHALL be shown and the detail view SHALL remain open.

#### Scenario: Successful add closes the detail view and updates the store
- **WHEN** Add-to-Cart is clicked and the cart API returns HTTP 200 with a `CartResponse`
- **THEN** the cart store SHALL be updated with the returned `CartResponse` and the detail view SHALL close

#### Scenario: Failed add keeps the detail view open
- **WHEN** the cart API rejects with HTTP 409 (e.g. item moved to stop list)
- **THEN** the detail view SHALL remain open and a localized error toast SHALL be rendered

### Requirement: Menu page is gated by customer authentication

`/menu` and `/menu/:categoryId` SHALL be mounted behind the existing `requireAuth` guard from `frontend-routing`. Unauthenticated visitors SHALL be redirected to `/login` with a return-URL preserving the requested path (INV-010).

#### Scenario: Unauthenticated visit redirects to login
- **WHEN** an unauthenticated user navigates to `/menu`
- **THEN** the router SHALL redirect to `/login?redirect=/menu`
