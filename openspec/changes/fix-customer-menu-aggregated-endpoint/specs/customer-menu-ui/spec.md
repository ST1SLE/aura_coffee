## MODIFIED Requirements

_References: PDD §7.1 Phase 2 (Menu & Cart), PDD §3 (Domain Language — Category, Menu Item), archived change `2026-04-10-add-public-menu-green` (defines `GET /api/v1/menu` as the single public menu endpoint)._

### Requirement: Customer menu page data source

**Previously:** The menu page in `web/customer/` fetched its data via three independent calls — `listCategories()`, `listMenuItems()`, and `getMenuItem(id)` — hitting `/api/v1/menu/categories`, `/api/v1/menu/items`, and `/api/v1/menu/items/:id` respectively. These paths do not exist on the backend; the RBAC middleware default-denies them with 401/403.

**Now:** The customer SPA SHALL fetch the menu via a single function `fetchPublicMenu(language: 'ru' | 'en'): Promise<PublicMenuResponse>` that issues `GET /api/v1/menu` with an `Accept-Language` header matching `language`. The function SHALL be the only data-source entry point in `web/customer/src/api/menu.ts`; `listCategories`, `listMenuItems`, and `getMenuItem` SHALL be removed.

#### Scenario: Menu page loads via the aggregated endpoint
- **WHEN** the customer navigates to `/menu` while the active i18n language is `ru`
- **THEN** the SPA SHALL issue exactly one HTTP request, `GET /api/v1/menu`, with header `Accept-Language: ru`
- **AND** it SHALL render `response.categories` in the order the server returned, with each category's `items` in server-returned order, without applying any client-side `sort()` on `sort_order`

#### Scenario: Language switch refetches the menu
- **WHEN** the menu page is mounted and the user switches the i18n language from `ru` to `en`
- **THEN** the SPA SHALL issue a second `GET /api/v1/menu` with header `Accept-Language: en`
- **AND** the rendered category and item names SHALL update to the `name` values returned in that second response (which the backend resolves from `name_en`)

#### Scenario: Dead endpoints are not called
- **WHEN** any page in `web/customer/` needs menu data
- **THEN** no call SHALL be made to `/api/v1/menu/categories`, `/api/v1/menu/items`, or `/api/v1/menu/items/:id`
- **AND** the type `MenuItemResponse` (the old monolingual alias) SHALL NOT be exported from `web/customer/src/api/menuTypes.ts`

### Requirement: Customer menu types mirror the backend public schema

**Previously:** `menuTypes.ts` defined `CategoryResponse`, `MenuItemResponse`, `ModifierResponse`, `SizeOptionResponse` as flat shapes close to — but not identical to — the backend's `CategoryBase` admin schema. Individual resource types encouraged one-resource-at-a-time fetching.

**Now:** `web/customer/src/api/menuTypes.ts` SHALL export `PublicMenuSizeOption`, `PublicMenuModifier`, `PublicMenuItem`, `PublicCategory`, `PublicMenuResponse` — names and field shapes matching `services/core-api/src/core_api/schemas/menu.py` classes `PublicMenuSizeOption`, `PublicMenuModifier`, `PublicMenuItem`, `PublicCategory`, `PublicMenuResponse` one-to-one. Every field that exists on the backend class SHALL exist on the TypeScript interface with the same JSON name.

#### Scenario: Types match the backend aggregated response
- **WHEN** a developer imports `PublicMenuResponse` from `@/api/menuTypes`
- **THEN** `response.categories[0].items[0].name` SHALL be typed as `string` (already language-resolved by the server)
- **AND** `response.categories[0].items[0].name_ru` and `name_en` SHALL both be typed as `string` (raw bilingual pair still exposed for tooltips / debug)
- **AND** `response.categories[0].items[0].size_options` SHALL be typed as `PublicMenuSizeOption[]`
- **AND** `response.categories[0].items[0].modifiers` SHALL be typed as `PublicMenuModifier[]`
