## Why

Every admin menu CRUD operation fails end-to-end. Manual testing of Phase 2 Block 1 (admin menu CRUD) confirmed that category creation surfaces a red error, modifier creation reports "Could not save modifier", and downstream blocks 1.2, 1.3, 1.5 are blocked because no category can exist to host items.

Root cause is a **complete schema mismatch** between the admin SPA and the backend. The backend ships bilingual, typed, ordered schemas (`services/core-api/src/core_api/schemas/menu.py`); the admin SPA ships monolingual, untyped, unordered ones (`web/admin/src/api/menu.ts:14-67`). Every `POST` / `PUT` from the admin to `/api/v1/admin/menu/*` currently returns HTTP 422.

Concrete per-resource drift:

| Resource | Backend requires | Admin frontend sends |
|---|---|---|
| Category | `type: CategoryType`, `name_ru`, `name_en`, `sort_order`, `is_visible` | `name` only |
| MenuItem | `category_id`, `name_ru`, `name_en`, `description_ru?`, `description_en?`, `base_price`, `image_url?`, `available`, `sort_order` | `category_id`, `name`, `description?`, `price_kopecks` |
| Modifier | `name_ru`, `name_en`, `price`, `available`, `sort_order` | `name`, `price_kopecks` |
| SizeOption | `label: SizeLabel` enum (`S`/`M`/`L`), `price`, `available` | `label: string`, `volume_ml?`, `price_kopecks` |

The admin frontend appears to have been built from an older, pre-bilingual draft and merged without a contract test against the backend. The backend schema (and the customer SPA's `menuTypes.ts`) are the source of truth; the admin SPA must align.

**MVP Phase**: Phase 2 — Menu & Cart (PDD §7.1). Also relevant to Phase 6 (Admin Panel) but scoped here to what Phase 2 needs to function.

## What Changes

### API client (`web/admin/src/api/menu.ts`)

- Replace the current `CategoryResponse`, `CategoryCreate`, `CategoryUpdate` with types matching `CategoryBase` / `CategoryResponse` in `services/core-api/src/core_api/schemas/menu.py:20-46`:
  - Add required fields `type: CategoryType`, `name_ru`, `name_en`, `sort_order: number`, `is_visible: boolean`, `created_at?`, `updated_at?`.
  - Remove `name`. Category now has two names.
- Replace `MenuItemResponse` / `MenuItemCreate` / `MenuItemUpdate` with types matching `MenuItemBase` / `MenuItemResponse`:
  - Add `name_ru`, `name_en`, `description_ru`, `description_en`, `base_price`, `image_url`, `sort_order`, and the embedded `modifiers: ModifierResponse[]` list returned by the backend.
  - Rename `price_kopecks` → `base_price`, remove flat `name` / `description`.
- Replace `ModifierResponse` / `ModifierCreate` / `ModifierUpdate` with the bilingual, ordered shape: `name_ru`, `name_en`, `price`, `available`, `sort_order`.
- Replace `SizeOptionResponse` / `SizeOptionCreate` / `SizeOptionUpdate` with the backend shape: `label: SizeLabel` (`'S' | 'M' | 'L'`), `price`, `available`, `menu_item_id`. Drop `volume_ml` (not on the backend). Drop `price_kopecks` alias — server field is `price`.
- Add a `CategoryType` enum export mirroring `shared.enums.CategoryType` (`'drink' | 'food' | 'merch' | 'modifier'`).
- Add a `SizeLabel` enum export mirroring `shared.enums.SizeLabel` (`'S' | 'M' | 'L'`).
- All CRUD functions keep the same names and URL paths. Only their request/response types change.

### CategoryList (`web/admin/src/pages/Menu/CategoryList.tsx`)

- Replace the single `<Input name>` with a minimal creation form that collects `name_ru`, `name_en`, and `type` (dropdown of `CategoryType`). `sort_order` defaults to the current length of the category list; `is_visible` defaults to `true`. These two defaults SHOULD be editable via an "edit category" expansion but MAY ship as defaults in the first iteration.
- Display the category as `{ru | en depending on UI language}` — read from `i18n.language` and fall back to `name_ru`.
- Edit mode SHALL allow updating `name_ru` and `name_en` side-by-side. `type` SHOULD be editable; `sort_order` and `is_visible` MAY be deferred to a follow-up.
- Delete-confirm and error handling stay the same.

### MenuItemFormDialog (`web/admin/src/pages/Menu/MenuItemFormDialog.tsx`)

- Replace the single `name` field with two side-by-side inputs `name_ru` and `name_en`, both required.
- Replace the single `description` field with two side-by-side inputs `description_ru` and `description_en`, both optional.
- Rename the `price` field handler so it submits `base_price` (kopecks) — the existing `rublesToKopecks` helper stays as-is.
- Add a `sort_order` number input (default 0).
- Add an optional `image_url` text field.
- Category select reads bilingual names for display (same language pick as CategoryList).
- Validation errors for the 422 case SHALL map backend `loc` field names (`name_ru`, `name_en`, `base_price`, …) to localized error messages.

### ModifiersPanel (`web/admin/src/pages/Menu/ModifiersPanel.tsx`)

- Replace the single `name` field with `name_ru` + `name_en`.
- Rename `price_kopecks` → `price`.
- Add `sort_order` (default 0).
- `available` toggle stays unchanged.

### SizeOptionsEditor (`web/admin/src/pages/Menu/SizeOptionsEditor.tsx`)

- Replace free-text `label` input with a `<select>` restricted to `S`, `M`, `L`.
- Remove `volume_ml` input (not on the backend; re-add later as its own change if the PDD grows this field).
- Rename `price_kopecks` → `price`.

### MenuItemsTable (`web/admin/src/pages/Menu/MenuItemsTable.tsx`)

- Replace `item.name` / `item.price_kopecks` with `item.name_{ru|en}` (language-picked) and `item.base_price`.
- Availability badge logic is unchanged (still reads `item.available` / `item.archived`).

### i18n (`web/admin/src/i18n/locales/{ru,en}/common.json`)

- Add keys for `pages.menu.itemForm.nameRu`, `nameEn`, `descriptionRu`, `descriptionEn`, `sortOrder`, `imageUrl`, `validationNameRu`, `validationNameEn`, `validationBasePrice` (and their modifier / category equivalents).
- Add keys for `pages.menu.categories.nameRu`, `nameEn`, `type`, `typeOptions.drink`, `typeOptions.food`, `typeOptions.merch`.
- Remove keys that referenced the old monolingual `name` where they're now unused.

### Tests (`web/admin/src/api/menu.test.ts` + component tests)

- Every existing mock payload is updated to the bilingual shape. Any test asserting on the old `{ name: … }` request body is rewritten to assert `{ name_ru, name_en, type, sort_order, is_visible }` for categories (and analogous shapes for items / modifiers / sizes).
- A new contract-style test SHALL be added: it imports `CategoryCreate` from `@/api/menu`, constructs one using only the fields the type allows, and `JSON.stringify`s it. A snapshot comparison against a hand-written "expected backend payload" JSON prevents silent monolingual regressions.

## Capabilities

### Modified Capabilities
- `menu-admin-ui`: admin menu CRUD forms and API client now carry the bilingual, typed, ordered schema the backend actually accepts, so every create/update/delete round-trips without a 422.

## Impact

- **Code**:
  - `web/admin/src/api/menu.ts` — full rewrite of types; CRUD functions unchanged in shape.
  - `web/admin/src/api/menu.test.ts` — rewrite expected payloads.
  - `web/admin/src/pages/Menu/CategoryList.tsx` — bilingual form fields + type dropdown.
  - `web/admin/src/pages/Menu/MenuItemFormDialog.tsx` — bilingual name/description, rename price field, add sort_order + image_url.
  - `web/admin/src/pages/Menu/MenuItemsTable.tsx` — language-picked display.
  - `web/admin/src/pages/Menu/ModifiersPanel.tsx` — bilingual fields, rename price.
  - `web/admin/src/pages/Menu/SizeOptionsEditor.tsx` — enum dropdown for label, rename price, drop volume_ml.
  - `web/admin/src/pages/Menu/utils.ts` — no rename expected (helpers are rubles↔kopecks and are backend-agnostic); touched only if a test fixture moves here.
  - `web/admin/src/pages/Menu/index.tsx` — touched only if the bilingual display layer requires new props. Aim: zero touch.
  - `web/admin/src/i18n/locales/ru/common.json` + `en/common.json` — new keys.
- **APIs**: no backend changes. This change brings the admin SPA into compliance with the backend that already ships.
- **DB**: none.
- **Auth / RBAC**: none — same endpoints, same role requirements.
- **Workers**: none.
- **Dependencies**: none.

## Non-Goals

- **No backend schema changes.** The backend bilingual/typed/ordered schema is authoritative. This change does NOT simplify the backend to match the old admin shape.
- **No customer SPA changes.** Customer side is handled by `fix-customer-menu-aggregated-endpoint`.
- **No nginx / basepath fix.** Handled by `fix-admin-spa-basepath`. This change assumes the admin SPA is accessed directly at its dev port.
- **No `volume_ml` field.** It does not exist on the backend; re-adding it is a separate concern.
- **No sort-order drag-and-drop UX.** A plain number input is sufficient for this fix; reorder ergonomics can follow later.
- **No image upload / CDN work.** `image_url` is a text input only.
- **No RBAC / barista-specific UI.** The existing `currentRole === 'admin' | 'barista'` gating stays as-is.
- **No route changes.** `App.tsx`, `main.tsx`, and `vite.config.ts` MUST NOT be touched by this change (reserved for `fix-admin-spa-basepath`).

## File Lane (merge safety)

This change is allowed to modify ONLY the following files:

```
web/admin/src/api/menu.ts
web/admin/src/api/menu.test.ts
web/admin/src/pages/Menu/CategoryList.tsx
web/admin/src/pages/Menu/MenuItemFormDialog.tsx
web/admin/src/pages/Menu/MenuItemsTable.tsx
web/admin/src/pages/Menu/ModifiersPanel.tsx
web/admin/src/pages/Menu/SizeOptionsEditor.tsx
web/admin/src/pages/Menu/utils.ts              (only if strictly required)
web/admin/src/pages/Menu/*.test.tsx             (any existing Menu test files)
web/admin/src/i18n/locales/ru/common.json
web/admin/src/i18n/locales/en/common.json
packages/shared/src/**                          (ONLY if a SizeLabel / CategoryType
                                                 enum already lives here; otherwise
                                                 re-declare as a TS-local union)
```

This change MUST NOT touch:

```
web/admin/src/App.tsx
web/admin/src/main.tsx
web/admin/vite.config.ts
web/admin/src/pages/Menu/index.tsx              (aim to avoid; see Impact notes)
web/customer/**
services/**
deploy/**
```

If a task would require touching a forbidden file, STOP and surface the conflict to the user before proceeding.
