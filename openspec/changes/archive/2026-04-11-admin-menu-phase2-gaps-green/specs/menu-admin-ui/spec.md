## ADDED Requirements

### Requirement: Modifier picker inside the item form dialog

The item form dialog SHALL host a modifier picker that lists every `ModifierResponse` in the system and lets an `admin` attach and detach modifiers on the currently edited item by toggling checkboxes. The picker SHALL live in a new component `web/admin/src/pages/Menu/ModifiersPicker.tsx`, rendered inside `MenuItemFormDialog` below the `SizeOptionsEditor`. The picker SHALL only be interactive when the dialog is editing an already-persisted item (i.e., after the first save in create mode) — the same gating rule used by the size options editor.

Each toggle SHALL issue a single `setItemModifiers(itemId, nextIds)` call that replaces the full set of attached modifiers for the item. On a non-2xx response the picker SHALL surface an error via `onError` and SHALL NOT update its local state (no optimistic divergence). On a 2xx response the picker SHALL reconcile its local `selectedIds` from `response.modifiers.map(m => m.id)` and propagate the new set to `MenuItemFormDialog` so the parent table and the dialog's `item` snapshot reflect the change.

The list of available modifiers rendered by the picker SHALL be passed in from `MenuPage` via a new `modifiers: ModifierResponse[]` prop on `MenuItemFormDialog`. `MenuItemFormDialog` SHALL NOT fetch modifiers itself. When the list changes (for example because an admin created a new modifier in `ModifiersPanel` while the dialog is open), the picker SHALL re-render to include the new row without losing the user's current selection.

Only role `admin` SHALL see the picker as interactive. For `barista` the picker SHALL either not be rendered at all or SHALL be rendered read-only (showing which modifiers are attached but disallowing toggles). The item form dialog is already hidden from `barista` for create/edit use cases, so this is defense-in-depth and does not need to be pixel-perfect.

#### Scenario: Admin attaches a modifier via the picker
- **WHEN** an `admin` is editing an existing item, the dialog is open, and the admin checks a previously unchecked modifier row
- **THEN** the UI SHALL call `setItemModifiers(item.id, [...currentIds, newId])`, and upon 2xx the checkbox SHALL remain checked, the item row behind the dialog SHALL reflect the new modifier set, and no full page reload SHALL occur

#### Scenario: Admin detaches a modifier via the picker
- **WHEN** an `admin` unchecks a previously checked modifier row
- **THEN** the UI SHALL call `setItemModifiers(item.id, currentIds.filter(id => id !== removedId))`, and upon 2xx the checkbox SHALL remain unchecked

#### Scenario: Picker is disabled before the item exists
- **WHEN** the dialog is open in create mode and the item has not yet been saved
- **THEN** the modifier picker SHALL render in a disabled state with a hint that the item must be saved first, and clicking a checkbox SHALL NOT issue any network request

#### Scenario: Picker becomes active after first save in create mode
- **WHEN** an `admin` fills the item form in create mode, clicks "Save", and the server returns 201
- **THEN** the dialog SHALL transition to edit mode, and the modifier picker SHALL become interactive for the newly created item

#### Scenario: Failed toggle rolls back the UI state
- **WHEN** `setItemModifiers` rejects with a non-2xx response after the admin toggled a checkbox
- **THEN** the checkbox SHALL return to its prior state, an error message SHALL be surfaced via `onError`, and no propagation to the parent table SHALL occur

#### Scenario: New modifier added in the panel appears in the open dialog
- **WHEN** the item form dialog is open in edit mode, and an `admin` navigates to `ModifiersPanel` (or the panel is visible behind the dialog) and creates a new modifier, then returns to the picker
- **THEN** the picker SHALL list the newly created modifier as an unchecked row, and the user's existing selection SHALL be preserved

#### Scenario: Dialog initial render reflects pre-existing modifier links
- **WHEN** an `admin` opens the dialog on an item that already has modifiers `[1, 3]` linked
- **THEN** the picker SHALL render with checkboxes for modifiers `1` and `3` pre-checked and all others unchecked, without issuing a network request on open

#### Scenario: Modifier list is passed from MenuPage, not fetched by the dialog
- **WHEN** inspecting `MenuItemFormDialog.tsx`
- **THEN** the component SHALL accept `modifiers: ModifierResponse[]` as a prop, SHALL NOT call `listModifiers()` directly, and SHALL pass the prop down to `ModifiersPicker`

## MODIFIED Requirements

### Requirement: Admin menu forms collect bilingual fields

The admin menu forms SHALL present bilingual name and description inputs as previously required, AND the category edit row SHALL additionally present a numeric `sort_order` input so admins can reorder existing categories.

**Previously:** Every admin menu form that creates or updates a Category, MenuItem, or Modifier presented two labelled inputs for name (`name_ru`, `name_en`) and treated both as required. Menu item forms additionally presented two optional inputs for `description_ru` and `description_en`, a numeric `sort_order`, and an optional `image_url`. The `CategoryList` edit row collected `name_ru`, `name_en`, and `type` only — NOT `sort_order` — so admins could not reorder existing categories through the UI.

**Now:** In addition to the previous requirement, the category edit row in `CategoryList.tsx` SHALL present a numeric `sort_order` input pre-filled from the edited category's current `sort_order`. On save, the UI SHALL include the parsed integer in the `updateCategory` request body. On a `NaN` parse result, the UI SHALL fall back to the category's existing `sort_order` value and not reject the save. The create form MAY continue to hardcode `sort_order: categories.length` for newly created categories; reorder is only required to be available on the edit row.

After a successful edit that changes `sort_order`, the client SHALL re-sort its local `categories` array by `sort_order` ascending with ties broken by `id` so that the on-screen order matches the server's canonical ordering (which is already `ORDER BY sort_order, id`).

Menu item forms continue to present `sort_order`, `image_url`, and the bilingual name/description fields as before. Size options continue to use the `S` / `M` / `L` `<select>`. Modifier creation continues to live in `ModifiersPanel`, not in the item form dialog — the item form dialog gains the `ModifiersPicker` (see ADDED requirement above) but does NOT gain modifier create/edit/delete controls.

#### Scenario: Category creation form fields
- **WHEN** the admin opens the category creation form
- **THEN** the form SHALL expose labelled inputs for `name_ru`, `name_en`, and a `type` select, and submit SHALL POST a full bilingual `CategoryCreate` payload with `sort_order` set to the current categories count

#### Scenario: Category edit row exposes sort_order
- **WHEN** an `admin` clicks the edit action on an existing category
- **THEN** the edit row SHALL include a numeric `sort_order` input pre-filled from the category's current `sort_order` value

#### Scenario: Admin reorders an existing category
- **WHEN** an `admin` edits a category, changes its `sort_order` from `3` to `0`, and clicks save
- **THEN** the UI SHALL call `updateCategory(id, { name_ru, name_en, type, sort_order: 0 })`, and upon 2xx the category list SHALL re-render with the edited category appearing at the position dictated by sorting the full list by `(sort_order, id)`

#### Scenario: Non-numeric sort_order input falls back to current value
- **WHEN** an `admin` clears the `sort_order` input (leaving it empty) and clicks save
- **THEN** the UI SHALL parse the input, detect `NaN`, substitute the category's previous `sort_order`, and proceed with the save rather than blocking it

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

### Requirement: Admin menu API client schema

The admin menu API client SHALL export every function and type previously required, AND SHALL additionally export a new `setItemModifiers(id, modifier_ids)` helper that calls the new item-modifier set-replacement endpoint.

**Previously:** `web/admin/src/api/menu.ts` exported typed helpers for category/item/modifier/size CRUD and the two availability PATCH endpoints, but had no helper for attaching modifiers to a menu item — consistent with the fact that no such backend endpoint existed.

**Now:** In addition to every function and type required by the prior version of this requirement (which remain unchanged in name, path, and shape), the admin API client SHALL export a new function:

```ts
export const setItemModifiers = (
  id: number,
  modifier_ids: number[],
): Promise<MenuItemResponse>;
```

This function SHALL issue `PUT /api/v1/admin/menu/items/{id}/modifiers` via `authenticatedFetch` with `Content-Type: application/json` and a body of exactly `{ "modifier_ids": [...] }`, and SHALL resolve to the parsed `MenuItemResponse`. On non-2xx responses it SHALL throw `ApiError` following the existing pattern. The function name, path shape, and body shape SHALL match this requirement verbatim.

The existing `CategoryUpdate` TypeScript interface continues to include `sort_order?: number` (already present); no type-level change is required for gap 1. All other previously defined types and helpers (`listCategories`, `createCategory`, `updateCategory`, `deleteCategory`, `listItems`, `getItem`, `createItem`, `updateItem`, `deleteItem`, `setItemAvailability`, `listModifiers`, `createModifier`, `updateModifier`, `deleteModifier`, `setModifierAvailability`, `createSize`, `updateSize`, `deleteSize`, `ApiError`, `CategoryType`, `SizeLabel`, and all `*Response` / `*Create` / `*Update` shapes) SHALL remain exactly as specified by the prior version of this requirement.

#### Scenario: setItemModifiers hits the correct URL with the correct body
- **WHEN** UI code calls `setItemModifiers(42, [1, 2, 3])`
- **THEN** the request SHALL be `PUT /api/v1/admin/menu/items/42/modifiers` with `Content-Type: application/json` and body exactly `{"modifier_ids":[1,2,3]}`, and the resolved value SHALL be a `MenuItemResponse`

#### Scenario: setItemModifiers with an empty array detaches everything
- **WHEN** UI code calls `setItemModifiers(42, [])`
- **THEN** the outbound body SHALL be exactly `{"modifier_ids":[]}` (not omitted, not `null`)

#### Scenario: Non-2xx responses raise a typed error
- **WHEN** `setItemModifiers` receives a non-2xx response
- **THEN** it SHALL throw an `ApiError` carrying the numeric `status`, the parsed response body (or `null` if not JSON), and a human-readable message; the caller SHALL be able to distinguish 404 and 422 by `error.status`

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
