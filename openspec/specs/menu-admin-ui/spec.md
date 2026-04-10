## Requirements

_References: PDD §7.1 Phase 6 (Admin Panel), PDD §3 (Domain Language — Category, Menu Item, Modifier, Size Option, Stop List), INV-002, INV-006, INV-010. Consumes the API defined by spec `menu-admin-crud`. Source of truth for API types: `services/core-api/src/core_api/schemas/menu.py`._

### Requirement: Menu admin page module layout

The system SHALL provide a menu admin page module at `web/admin/src/pages/Menu/` that exports a `MenuPage` component as its default-style entry (`index.tsx`), and SHALL wire it into the admin SPA router in place of the current placeholder `MenuPage.tsx`. The module SHALL decompose into at least the files `index.tsx`, `CategoryList.tsx`, `MenuItemsTable.tsx`, `MenuItemFormDialog.tsx`, `SizeOptionsEditor.tsx`, and `ModifiersPanel.tsx`, so no single file exceeds a reasonable review budget.

#### Scenario: Admin navigates to the menu route
- **WHEN** an authenticated user with role `admin` navigates to `/menu` in the admin SPA
- **THEN** the router SHALL render the new `MenuPage` from `pages/Menu/index.tsx` and SHALL NOT render the old placeholder component

#### Scenario: Placeholder file is removed
- **WHEN** inspecting `web/admin/src/pages/`
- **THEN** the flat `MenuPage.tsx` placeholder file SHALL NOT exist; the menu page SHALL only be reachable through `pages/Menu/index.tsx`

### Requirement: Admin menu API client schema

**Previously:** `web/admin/src/api/menu.ts` exported monolingual types `CategoryResponse { id, name }`, `MenuItemCreate { category_id, name, description?, price_kopecks }`, `ModifierCreate { name, price_kopecks }`, and `SizeOptionCreate { menu_item_id, label: string, volume_ml?, price_kopecks }`. Every POST / PUT built from these types was rejected by the backend with HTTP 422.

**Now:** The admin API client SHALL export types that match the backend Pydantic schemas in `services/core-api/src/core_api/schemas/menu.py` class-for-class and field-for-field, for `Category`, `MenuItem`, `Modifier`, and `SizeOption`. Specifically:

- `CategoryCreate` SHALL require `type: CategoryType`, `name_ru: string`, `name_en: string`, `sort_order: number`, `is_visible: boolean`. It SHALL NOT contain a field named `name`.
- `MenuItemCreate` SHALL require `category_id: number`, `name_ru: string`, `name_en: string`, `base_price: number`. It SHALL expose optional `description_ru`, `description_en`, `image_url`, `sort_order`, `available`. It SHALL NOT contain fields named `name`, `description`, or `price_kopecks`.
- `ModifierCreate` SHALL require `name_ru: string`, `name_en: string`, `price: number`. It SHALL expose optional `available`, `sort_order`. It SHALL NOT contain a field named `price_kopecks`.
- `SizeOptionCreate` SHALL require `menu_item_id: number`, `label: SizeLabel`, `price: number`, where `SizeLabel = 'S' | 'M' | 'L'`. It SHALL NOT contain fields named `volume_ml` or `price_kopecks`.
- The enums `CategoryType = 'drink' | 'food' | 'merch' | 'modifier'` and `SizeLabel = 'S' | 'M' | 'L'` SHALL be exported from `web/admin/src/api/menu.ts`.

URL paths and CRUD function names SHALL remain unchanged (`createCategory`, `updateItem`, `deleteModifier`, etc.).

#### Scenario: Monolingual category payload is a compile error
- **WHEN** a developer writes `createCategory({ name: 'Coffee' })` in admin SPA source
- **THEN** the TypeScript compiler SHALL report an error on the literal, because `name` is not a field of `CategoryCreate` and `name_ru`, `name_en`, `type`, `sort_order`, `is_visible` are required

#### Scenario: Bilingual category payload is accepted
- **WHEN** a developer writes `createCategory({ type: 'drink', name_ru: 'Кофе', name_en: 'Coffee', sort_order: 0, is_visible: true })`
- **THEN** the call SHALL type-check and the outbound POST body SHALL contain exactly those keys (and no others)

#### Scenario: Create size option submits SizeLabel enum
- **WHEN** the admin submits a size with `label: 'S'`, `price: 25000`, `menu_item_id: 42`
- **THEN** the outbound POST body SHALL be `{ menu_item_id: 42, label: 'S', price: 25000 }` — without `volume_ml`, without `price_kopecks`

#### Scenario: Listing categories hits the correct URL
- **WHEN** UI code calls `listCategories()` from `api/menu.ts`
- **THEN** the request SHALL be `GET ${VITE_API_BASE_URL}/api/v1/admin/menu/categories` issued via `authenticatedFetch`, and the resolved value SHALL be an array of `CategoryResponse`

#### Scenario: Creating an item sends MenuItemCreate
- **WHEN** UI code calls `createItem(body)` with a valid `MenuItemCreate` shape
- **THEN** the request SHALL be `POST /api/v1/admin/menu/items` with `Content-Type: application/json` and the body as JSON, and the resolved value SHALL be a `MenuItemResponse`

#### Scenario: Availability PATCH uses the exact body shape
- **WHEN** UI code calls `setItemAvailability(id, false)`
- **THEN** the request SHALL be `PATCH /api/v1/admin/menu/items/{id}/availability` with body exactly `{"available": false}` and no other fields

#### Scenario: Non-2xx responses raise a typed error
- **WHEN** any `api/menu.ts` function receives a non-2xx response
- **THEN** it SHALL throw an `ApiError` carrying the numeric `status`, the parsed response body (or `null` if not JSON), and a human-readable message; the caller SHALL be able to distinguish 409 and 404 by `error.status`

### Requirement: Authenticated fetch helper for the admin app

The system SHALL provide `web/admin/src/api/client.ts` exporting an `authenticatedFetch(path, init?)` function that prepends the base URL from `import.meta.env.VITE_API_BASE_URL`, merges an `Authorization: Bearer <token>` header when a token is available from a single `getAccessToken()` seam, and passes through caller-supplied headers without overwriting them. The module SHALL export an `ApiError` class used by `api/menu.ts`. This helper SHALL NOT implement 401 refresh-and-retry — that responsibility belongs to the future `staff-auth` work.

#### Scenario: Request with an access token available
- **WHEN** `authenticatedFetch('/api/v1/admin/menu/categories')` is called and `getAccessToken()` returns a non-empty string
- **THEN** the underlying `fetch` SHALL be called with the full URL and an `Authorization: Bearer <token>` header

#### Scenario: Request without an access token
- **WHEN** `authenticatedFetch` is called and `getAccessToken()` returns `null`
- **THEN** the request SHALL be issued without an `Authorization` header (the server decides whether to reject)

#### Scenario: Caller headers are preserved
- **WHEN** `authenticatedFetch(path, { headers: { 'Content-Type': 'application/json' } })` is called
- **THEN** both the `Authorization` header (if present) AND the caller's `Content-Type` SHALL appear on the outgoing request

#### Scenario: 401 surfaces as an ApiError without refresh
- **WHEN** the server returns HTTP 401 to any request issued via `authenticatedFetch`
- **THEN** the `api/menu.ts` wrapper SHALL throw `ApiError` with `status === 401`, and the client SHALL NOT attempt a silent refresh or retry in this change

### Requirement: Category CRUD UI

The menu admin page SHALL render a category list pane that lets a user with role `admin` create, rename, and delete categories, and lets any authorized role (at least `admin` and `barista`) view the list. Selecting a category in the list SHALL filter the items table to items whose `category_id` matches the selection. Deleting a category SHALL ask for confirmation first.

#### Scenario: Admin creates a category
- **WHEN** an `admin` clicks "New category", enters a name, and submits
- **THEN** the UI SHALL call `createCategory`, and upon 2xx response the new category SHALL appear in the list without a full page reload

#### Scenario: Admin renames a category
- **WHEN** an `admin` edits a category name and confirms
- **THEN** the UI SHALL call `updateCategory(id, { name })`, and upon 2xx response the list entry SHALL reflect the new name

#### Scenario: Admin deletes an empty category
- **WHEN** an `admin` confirms deletion of a category that has no items
- **THEN** the UI SHALL call `deleteCategory(id)`, receive 204, and remove the row from the list

#### Scenario: Deleting a referenced category surfaces a specific error
- **WHEN** an `admin` confirms deletion of a category that still has items
- **THEN** the UI SHALL catch the 409 `ApiError` and SHALL display a user-facing message identifying that the category still has items, NOT a generic error, and the category SHALL remain in the list

#### Scenario: Barista sees no mutation controls for categories
- **WHEN** the page renders with `currentRole === 'barista'`
- **THEN** the category list SHALL be visible but the "New", "Rename", and "Delete" controls SHALL NOT be rendered

### Requirement: Menu items table UI

The menu admin page SHALL render a table of menu items for the currently selected category, showing at minimum each item's name, base price (formatted from kopecks to rubles), and current availability state. The table SHALL be visible to both `admin` and `barista` roles. Row actions for create / edit / delete SHALL be visible only to `admin`.

#### Scenario: Table loads items for the selected category
- **WHEN** the page mounts and a category is selected
- **THEN** the UI SHALL call `listItems({ categoryId })` and render one row per returned `MenuItemResponse`

#### Scenario: Admin clicks "Edit"
- **WHEN** an `admin` clicks the edit action on a row
- **THEN** the UI SHALL open `MenuItemFormDialog` prefilled with that item's fields via `getItem(id)` or the already-loaded row

#### Scenario: Admin deletes an item
- **WHEN** an `admin` confirms deletion of an item
- **THEN** the UI SHALL call `deleteItem(id)` and, on 2xx, remove the row from the table

#### Scenario: Barista sees no create / edit / delete on rows
- **WHEN** the page renders with `currentRole === 'barista'`
- **THEN** the "New item", "Edit", and "Delete" controls SHALL NOT be rendered; only the availability switch SHALL be interactive

#### Scenario: Price is displayed as rubles, stored as kopecks
- **WHEN** the table renders a row whose `price_kopecks === 15000`
- **THEN** the price cell SHALL show `"150,00 ₽"` (or the i18n-formatted equivalent), and the underlying DTO sent back to the server SHALL still carry the integer kopecks value

### Requirement: Admin menu forms collect bilingual fields

**Previously:** `CategoryList`, `MenuItemFormDialog`, `ModifiersPanel`, and `SizeOptionsEditor` collected a single `name` string (and a single `description` for items) and submitted monolingual payloads.

**Now:** Every admin menu form that creates or updates a Category, MenuItem, or Modifier SHALL present two labelled inputs for name — one for Russian (`name_ru`) and one for English (`name_en`) — and SHALL treat both as required with their own validation errors. Menu item forms SHALL additionally present two optional inputs for `description_ru` and `description_en`, a numeric `sort_order`, and an optional `image_url`. The SizeOptionsEditor SHALL present a `<select>` restricted to `S`, `M`, `L` instead of a free-text `label` input.

#### Scenario: Category creation form fields
- **WHEN** the admin opens the category creation form
- **THEN** the form SHALL expose labelled inputs for `name_ru`, `name_en`, and a `type` select, and submit SHALL POST a full bilingual `CategoryCreate` payload

#### Scenario: Menu item form validation surfaces each bilingual field
- **WHEN** the admin submits the menu item form with both name fields empty
- **THEN** the form SHALL display two separate validation errors, one under `name_ru` and one under `name_en`, and SHALL NOT submit

#### Scenario: Size option label is constrained to the SizeLabel enum
- **WHEN** the admin adds a new size to a menu item
- **THEN** the label input SHALL be a `<select>` with exactly three options `S`, `M`, `L` and SHALL NOT accept arbitrary text

#### Scenario: Creating a valid item
- **WHEN** an `admin` fills all required fields and clicks "Save"
- **THEN** the UI SHALL call `createItem(body)`; on 2xx the dialog SHALL remain open, rebound to the returned `MenuItemResponse`, and the item SHALL appear in the table behind the dialog

#### Scenario: Submitting with a missing required field
- **WHEN** an `admin` clicks "Save" with an empty `name_ru`
- **THEN** the UI SHALL block the submit, highlight the `name_ru` field, and SHALL NOT call the API

#### Scenario: Backend rejects the payload with 422
- **WHEN** the server responds with HTTP 422 to a `createItem` call
- **THEN** the UI SHALL display a validation error message referencing the offending fields from the response body, and the dialog SHALL remain open

#### Scenario: Archiving an item via the form
- **WHEN** an `admin` toggles the `archived` checkbox on an existing item and saves
- **THEN** the UI SHALL call `updateItem(id, { archived: true })` and the item row SHALL reflect `availability === 'ARCHIVED'` after the response

### Requirement: Admin menu display picks the active UI language

**Previously:** Menu tables and lists displayed `item.name` directly — a single string.

**Now:** Every admin surface that displays a Category, MenuItem, or Modifier SHALL pick between its `name_ru` and `name_en` based on the active `i18n.language`, with `name_ru` as the fallback when the active language has an empty string. A shared helper `pickLang(ru, en, lang)` in `web/admin/src/pages/Menu/utils.ts` SHALL be the single implementation of this rule.

#### Scenario: Switching admin UI language repicks displayed names
- **WHEN** the admin switches UI language from `ru` to `en` while the menu page is open
- **THEN** every category, item, and modifier name in the visible tables SHALL re-render from `name_en` without a page reload

### Requirement: Stop-list availability toggle for items

Every menu item row SHALL render an availability control that, when operated, sends `PATCH /api/v1/admin/menu/items/{id}/availability` with exactly `{ "available": bool }`. The control SHALL be enabled for roles `admin` and `barista` and SHALL remain disabled for other roles. The row SHALL render a badge that reflects the returned `MenuItemResponse.availability`: `AVAILABLE` shows no badge and the switch on, `STOP_LIST` shows a "Stop" badge and the switch off, `ARCHIVED` shows an "Archived" badge and the switch disabled. Implements INV-006.

#### Scenario: Barista stop-lists an item
- **WHEN** a `barista` toggles the availability switch on a row whose current availability is `AVAILABLE`
- **THEN** the UI SHALL call `setItemAvailability(id, false)`, and upon 2xx the row SHALL re-render with the switch off and a "Stop" badge

#### Scenario: Barista un-stop-lists an item
- **WHEN** a `barista` toggles the availability switch on a row whose current availability is `STOP_LIST`
- **THEN** the UI SHALL call `setItemAvailability(id, true)`, and upon 2xx the row SHALL re-render with the switch on and no badge

#### Scenario: Archived item cannot be toggled
- **WHEN** the row's current availability is `ARCHIVED`
- **THEN** the availability switch SHALL be rendered disabled, attempting to click it SHALL NOT issue a network request, and the "Archived" badge SHALL remain

#### Scenario: Toggle failure rolls back the UI state
- **WHEN** `setItemAvailability` rejects with a non-2xx response
- **THEN** the switch SHALL return to its prior on/off state (no optimistic divergence), and the user SHALL see an error message

### Requirement: Size options editor inside the item dialog

The item form dialog SHALL host a size options editor that lists every `SizeOptionResponse` attached to the currently edited item, lets an `admin` add a new size (`label`, `volume_ml`, `price_kopecks`), edit an existing size, and delete a size. Size operations SHALL use `createSize` / `updateSize` / `deleteSize` from `api/menu.ts`. The editor SHALL only be active when the dialog is editing an already-persisted item (i.e., after the first save in create mode).

#### Scenario: Adding a size to a new item after initial save
- **WHEN** an `admin` creates a new item, the dialog transitions to edit mode, and the admin adds a size row with `label = "M"`
- **THEN** the UI SHALL call `createSize({ menu_item_id, label: "M", ... })`, and on 2xx the row SHALL appear in the size list

#### Scenario: Duplicate size label is rejected by the backend
- **WHEN** the admin tries to create a second size with `label = "M"` on the same item
- **THEN** the UI SHALL catch the 409 `ApiError` and display a "Size label already exists" message; the list SHALL NOT show a duplicate row

#### Scenario: Deleting a size
- **WHEN** an `admin` clicks delete on a size row and confirms
- **THEN** the UI SHALL call `deleteSize(id)`, and on 2xx the row SHALL be removed from the list

#### Scenario: Size editor is disabled before the item exists
- **WHEN** the dialog is open in create mode and the item has not yet been saved
- **THEN** the size editor SHALL render in a disabled state with a hint that the item must be saved first, and "Add size" SHALL NOT issue any network request

### Requirement: Modifiers management panel

The menu admin page SHALL provide a modifiers panel (inline section or drawer) that lists every `ModifierResponse`, lets an `admin` create, edit, and delete modifiers using `ModifierCreate` / `ModifierUpdate`, and lets both `admin` and `barista` toggle each modifier's availability via `setModifierAvailability`. Modifiers SHALL NOT be edited from inside the item form dialog; the panel is the single place that manages them.

#### Scenario: Admin creates a modifier
- **WHEN** an `admin` opens the modifiers panel, enters a new modifier's name and price, and saves
- **THEN** the UI SHALL call `createModifier(body)` and the new modifier SHALL appear in the list

#### Scenario: Barista toggles a modifier's availability
- **WHEN** a `barista` toggles the availability switch on a modifier row
- **THEN** the UI SHALL call `setModifierAvailability(id, newValue)` and the row SHALL reflect the returned `ModifierResponse.available`

#### Scenario: Barista sees no create / edit / delete for modifiers
- **WHEN** the modifiers panel renders with `currentRole === 'barista'`
- **THEN** only the per-row availability switches SHALL be interactive; "New modifier", "Edit", and "Delete" controls SHALL NOT be rendered

### Requirement: Role awareness via prop, server is source of truth

The `MenuPage` component SHALL accept or derive a `currentRole` value from the admin app's auth state (stubbed as `'admin'` via a single module-level getter until `staff-auth` lands). The UI SHALL hide controls that correspond to actions the current role cannot perform per spec `menu-admin-crud`'s RBAC matrix. The UI SHALL NOT rely on hiding for security — the server remains the source of truth (INV-010).

#### Scenario: Role is read from a single seam
- **WHEN** inspecting `pages/Menu/index.tsx`
- **THEN** the `currentRole` value SHALL be sourced from exactly one import / getter, so that wiring real auth later is a single-point change

#### Scenario: Hidden control cannot be reached by direct URL
- **WHEN** a `barista` somehow triggers a create-item request (e.g., via devtools)
- **THEN** the server SHALL still return 403 (handled by `menu-admin-crud`), and the UI SHALL surface the 403 as an error message without crashing

### Requirement: Bilingual UI strings (RU + EN)

All user-visible strings in the menu admin page SHALL be rendered through `react-i18next` under the `pages.menu.*` and `menu.common.*` key namespaces, with both RU and EN translations added in the same change. No hard-coded Russian or English literals SHALL appear in JSX or in confirmation dialog text.

#### Scenario: Switching language updates the page
- **WHEN** the user switches the app language from RU to EN via the existing `LanguageSwitcher`
- **THEN** every label, button, badge, column header, confirmation text, and error message on the menu admin page SHALL re-render in English

#### Scenario: Translation keys exist in both locale files
- **WHEN** inspecting the `i18n` locale files for RU and EN
- **THEN** every `pages.menu.*` key referenced in the page module SHALL have a non-empty value in both locales
