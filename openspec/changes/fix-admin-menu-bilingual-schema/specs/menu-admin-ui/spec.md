## MODIFIED Requirements

_References: PDD §3 (Domain Language), PDD §5.2 (Menu table group), PDD §7.1 Phase 2 (Menu & Cart), INV-002 (state mutations require auth — unchanged). Source of truth: `services/core-api/src/core_api/schemas/menu.py`._

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

### Requirement: Admin menu display picks the active UI language

**Previously:** Menu tables and lists displayed `item.name` directly — a single string.

**Now:** Every admin surface that displays a Category, MenuItem, or Modifier SHALL pick between its `name_ru` and `name_en` based on the active `i18n.language`, with `name_ru` as the fallback when the active language has an empty string. A shared helper `pickLang(ru, en, lang)` in `web/admin/src/pages/Menu/utils.ts` SHALL be the single implementation of this rule.

#### Scenario: Switching admin UI language repicks displayed names
- **WHEN** the admin switches UI language from `ru` to `en` while the menu page is open
- **THEN** every category, item, and modifier name in the visible tables SHALL re-render from `name_en` without a page reload
