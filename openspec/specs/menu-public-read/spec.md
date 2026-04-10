## Requirements

_References: PDD §3 (Domain Language — Category, Menu Item, Size Option, Modifier), PDD §5.2 (Menu table group), PDD §5.4 (Indexes), PDD §7.1 Phase 2 (Menu & Cart), INV-002 (state mutations require auth — does not apply to reads), INV-006 (stop list)._

### Requirement: GET /api/v1/menu returns the active menu grouped by category

The system SHALL expose `GET /api/v1/menu` on the `menu-public` tag. The endpoint SHALL return HTTP 200 with a JSON body of shape `{ "categories": [...] }`, where each category object contains its `items` list. Categories SHALL be ordered by `categories.sort_order` ascending, with ties broken by `categories.id` ascending. Items within a category SHALL be ordered by `menu_items.sort_order` ascending, with ties broken by `menu_items.id` ascending.

#### Scenario: Categories and items are returned in configured sort order
- **WHEN** the database contains two visible non-modifier categories with `sort_order` values `(10, 20)` and each has three items with mixed `sort_order` values
- **THEN** the response SHALL list the categories in `sort_order` order and, within each, the items SHALL be in `sort_order` order

#### Scenario: Empty menu returns an empty categories array
- **WHEN** the database contains no rows that satisfy the visibility rules
- **THEN** the response SHALL be HTTP 200 with body `{"categories": []}` (not 404, not an error)

### Requirement: Archived items are never returned

The endpoint SHALL omit every `menu_items` row whose `archived = TRUE`, unconditionally. This rule SHALL apply before and independently of the `available` query filter.

#### Scenario: Archived item is hidden
- **WHEN** a visible category contains one item with `archived = TRUE` and one item with `archived = FALSE`
- **THEN** only the non-archived item SHALL appear in the response

#### Scenario: Category with only archived items is omitted
- **WHEN** a category's only items are all `archived = TRUE`
- **THEN** that category SHALL NOT appear in the response at all

### Requirement: Invisible categories are never returned

The endpoint SHALL omit every `categories` row whose `is_visible = FALSE`, along with all of that category's items, unconditionally.

#### Scenario: Invisible category is hidden with all its items
- **WHEN** a category has `is_visible = FALSE` and contains two otherwise valid items
- **THEN** neither the category nor its items SHALL appear in the response

### Requirement: The modifier category type is never returned as a browsable category

The endpoint SHALL omit every `categories` row whose `type = 'modifier'`, unconditionally. Modifiers SHALL only surface inline on their parent menu items (see the modifiers-per-item requirement below), never as a top-level category.

#### Scenario: Modifier-type category is excluded
- **WHEN** a visible category has `type = 'modifier'` and contains rows
- **THEN** that category SHALL NOT appear in the response, regardless of `is_visible`

### Requirement: The `available` query parameter hides stop-listed rows when true

The endpoint SHALL accept an optional query parameter `available` with values `true` or `false` (default: absent). When `available=true` is supplied:
- Items with `menu_items.available = FALSE` SHALL be omitted from the response.
- Size options with `size_options.available = FALSE` SHALL be omitted from the enclosing item's `size_options` list.

When the parameter is absent or set to `false`, stop-listed items and stop-listed size options SHALL be included in the response so the client can render them as disabled. The `archived` rule remains in force regardless.

#### Scenario: available=true hides stop-listed items
- **WHEN** the request is `GET /api/v1/menu?available=true` and a visible category contains one item with `available = TRUE` and one with `available = FALSE`
- **THEN** only the `available = TRUE` item SHALL appear in the response

#### Scenario: Default request includes stop-listed items
- **WHEN** the request is `GET /api/v1/menu` (no `available` parameter) and a visible category contains one item with `available = TRUE` and one with `available = FALSE`
- **THEN** both items SHALL appear in the response, and the stop-listed one SHALL carry `available: false`

#### Scenario: available=true prunes stop-listed size options
- **WHEN** the request is `GET /api/v1/menu?available=true` and an included item has two `size_options` with `available` values `(TRUE, FALSE)`
- **THEN** that item's `size_options` list in the response SHALL contain only the `available = TRUE` size

### Requirement: Bilingual projection via Accept-Language

The endpoint SHALL parse the `Accept-Language` request header with a minimal rule: if the header value (after trimming) starts with `en` (case-insensitive), the response language is `EN`; otherwise the response language is `RU` (default, and the fallback for missing, empty, or unrecognized headers). The endpoint SHALL NOT parse quality values, wildcards, or BCP-47 regional subtags beyond the leading language prefix.

For every category and menu item, the response SHALL expose **both** a flat projected field and the raw bilingual pair:
- `name` (flat, picked by language) and `name_ru`, `name_en` (raw).
- For menu items only: `description` (flat, picked by language, `null` if both source fields are `null`) and `description_ru`, `description_en` (raw).
- For modifiers only: `name` (flat) and `name_ru`, `name_en` (raw).
- Size options have no bilingual fields (label is an enum).

#### Scenario: Accept-Language: en selects English flat fields
- **WHEN** the request carries `Accept-Language: en` and an item has `name_ru="Капучино"`, `name_en="Cappuccino"`
- **THEN** the item's response object SHALL have `name = "Cappuccino"`, `name_ru = "Капучино"`, `name_en = "Cappuccino"`

#### Scenario: Missing Accept-Language defaults to Russian
- **WHEN** the request carries no `Accept-Language` header and an item has `name_ru="Капучино"`, `name_en="Cappuccino"`
- **THEN** the item's response object SHALL have `name = "Капучино"`, and both raw fields populated

#### Scenario: Unknown Accept-Language falls back to Russian
- **WHEN** the request carries `Accept-Language: fr-FR` and an item has bilingual names populated
- **THEN** the `name` field SHALL equal `name_ru`

#### Scenario: Null description projects as null
- **WHEN** an item has `description_ru = NULL` and `description_en = NULL` and the language is `RU`
- **THEN** the response item SHALL have `description = null`, `description_ru = null`, `description_en = null`

### Requirement: Size options and modifiers are embedded per item

Each menu item in the response SHALL include a `size_options` list and a `modifiers` list, sourced from the `size_options` and `menu_item_modifiers` relationships of the underlying `menu_items` row. The service SHALL eager-load these relationships so that the entire response materializes without per-item lazy queries.

The `size_options` list items SHALL contain `id`, `label` (enum `S` | `M` | `L`), `price` (integer kopecks, `>= 0`), and `available`. They SHALL be ordered by `label` in the enum order (`S`, `M`, `L`).

The `modifiers` list items SHALL contain `id`, `name` (flat projected), `name_ru`, `name_en`, `price` (integer kopecks, `>= 0`), and `available`. They SHALL be ordered by `modifiers.sort_order` ascending, with ties broken by `modifiers.id` ascending.

#### Scenario: Item embeds its sizes in enum order
- **WHEN** an item has size options with labels `L`, `S`, `M` in insertion order
- **THEN** the response item's `size_options` SHALL be ordered `S`, `M`, `L`

#### Scenario: Item embeds its modifiers with bilingual projection
- **WHEN** an item has two modifiers with `(sort_order, name_ru, name_en) = (10, "Сироп", "Syrup")` and `(20, "Молоко", "Milk")` and the request language is `EN`
- **THEN** the response item's `modifiers` SHALL be `[{name: "Syrup", ...}, {name: "Milk", ...}]` in that order, each carrying the raw `name_ru`/`name_en` fields

#### Scenario: Stop-listed modifier remains visible on the item
- **WHEN** an item has a modifier with `available = FALSE` and the request is `GET /api/v1/menu?available=true`
- **THEN** the modifier SHALL still appear in the item's `modifiers` list with `available: false` (the `available` filter applies to items and size options only, not to modifiers)

### Requirement: Endpoint is unauthenticated

The endpoint SHALL NOT require authentication and SHALL NOT be listed in `core_api.rbac_matrix`. Requests without any `Authorization` header, without any session cookie, and from an anonymous client SHALL succeed with HTTP 200.

#### Scenario: Anonymous request succeeds
- **WHEN** a client sends `GET /api/v1/menu` with no credentials of any kind
- **THEN** the response SHALL be HTTP 200 with a valid `PublicMenuResponse` body

#### Scenario: No RBAC matrix entry exists for the public menu route
- **WHEN** inspecting `core_api.rbac_matrix`
- **THEN** no entry SHALL reference the path `/api/v1/menu` with method `GET`

### Requirement: Query is issued in a bounded, index-friendly shape

The `get_public_menu` service function SHALL materialize the response in a bounded number of SQL statements, independent of the menu size. The item query SHALL filter on `archived = FALSE` so it can use the PDD §5.4 partial index `menu_items(available, archived) WHERE archived = FALSE`. Relationships SHALL be eager-loaded via SQLAlchemy loader options (`selectinload` for collections, `joinedload` for the single-row category) — no lazy loading SHALL occur inside the HTTP handler.

#### Scenario: Response is produced without per-item round trips
- **WHEN** the database contains N visible items (for any N)
- **THEN** the service SHALL issue at most a constant number of SQL statements (not proportional to N), and the response SHALL contain every item's `size_options` and `modifiers` populated

### Requirement: Service layer owns the query, filtering, and projection

The system SHALL provide a module `core_api.services.menu_public` exposing a function `get_public_menu(db: Session, *, only_available: bool, language: Language) -> PublicMenuResponse`. The router SHALL be a thin adapter that parses the request, calls the service, and returns its result. All visibility rules, ordering, eager loading, and bilingual projection SHALL live in the service. The router module SHALL NOT contain SQL, loader options, or bilingual pick logic.

#### Scenario: Router delegates to the service
- **WHEN** the request handler for `GET /api/v1/menu` executes
- **THEN** it SHALL call `core_api.services.menu_public.get_public_menu` exactly once and return its return value (wrapped in the FastAPI response model)

### Requirement: Public response schemas are distinct from admin schemas

The system SHALL define the following Pydantic v2 response schemas in `core_api.schemas.menu`, each with `model_config = ConfigDict(from_attributes=True)`:

- `PublicMenuSizeOption`: `id: int`, `label: SizeLabel`, `price: int` (ge=0), `available: bool`.
- `PublicMenuModifier`: `id: int`, `name: str`, `name_ru: str`, `name_en: str`, `price: int` (ge=0), `available: bool`.
- `PublicMenuItem`: `id: int`, `category_id: int`, `name: str`, `name_ru: str`, `name_en: str`, `description: str | None`, `description_ru: str | None`, `description_en: str | None`, `base_price: int` (ge=0), `image_url: str | None`, `available: bool`, `sort_order: int`, `size_options: list[PublicMenuSizeOption]`, `modifiers: list[PublicMenuModifier]`. It SHALL NOT expose `archived` and SHALL NOT expose the admin `availability` computed field.
- `PublicCategory`: `id: int`, `type: CategoryType`, `name: str`, `name_ru: str`, `name_en: str`, `sort_order: int`, `items: list[PublicMenuItem]`.
- `PublicMenuResponse`: `categories: list[PublicCategory]`.

These schemas SHALL be separate classes — the existing `MenuItemResponse`, `CategoryResponse`, `ModifierResponse`, `SizeOptionResponse` SHALL remain unchanged.

#### Scenario: PublicMenuItem does not expose archived
- **WHEN** a `PublicMenuItem` is serialized to JSON
- **THEN** the output SHALL NOT contain an `archived` key

#### Scenario: Admin MenuItemResponse is untouched
- **WHEN** importing `core_api.schemas.menu.MenuItemResponse`
- **THEN** the class SHALL still expose its existing fields including `archived` and the computed `availability` field

### Requirement: Prices are serialized as integer kopecks

Every price field in the public menu response (`PublicMenuItem.base_price`, `PublicMenuSizeOption.price`, `PublicMenuModifier.price`) SHALL be a non-negative integer representing kopecks. The API SHALL NOT convert to rubles, format as a string, or attach a currency symbol.

#### Scenario: Price is an integer
- **WHEN** an item has `base_price = 15000` (150 rubles) in the database
- **THEN** the response JSON SHALL contain `"base_price": 15000` (integer, not string)
