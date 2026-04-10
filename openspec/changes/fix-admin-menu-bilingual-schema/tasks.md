## 1. API client types — Category

- [ ] 1.1 RED [web-admin] In `web/admin/src/api/menu.test.ts`, add a failing test `test('CategoryCreate requires name_ru, name_en, type, sort_order, is_visible')` that uses `@ts-expect-error` to prove a monolingual `{ name: 'x' }` literal is NOT assignable to `CategoryCreate`, and prove a full bilingual literal IS assignable. MUST fail to compile today (the error will NOT appear on the monolingual literal).
- [ ] 1.2 RED [web-admin] In the same file, add a failing runtime test `test('createCategory POSTs bilingual payload')` that mocks `authenticatedFetch`, calls `createCategory({ type: 'drink', name_ru: 'Кофе', name_en: 'Coffee', sort_order: 0, is_visible: true })`, and asserts `JSON.parse(init.body)` equals that object exactly. MUST fail today because the current client sends `{ name: ... }`.
- [ ] 1.3 GREEN [web-admin] In `web/admin/src/api/menu.ts`, declare `export type CategoryType = 'drink' | 'food' | 'merch' | 'modifier'`. Replace `CategoryResponse`, `CategoryCreate`, `CategoryUpdate` with bilingual shapes: `{ id, type, name_ru, name_en, sort_order, is_visible, created_at?, updated_at? }`, and Create / Update drop `id` / make fields optional per Pydantic semantics. Keep the CRUD function names and URLs unchanged. → passes 1.1, 1.2.

## 2. API client types — MenuItem

- [ ] 2.1 RED [web-admin] Add failing test `test('MenuItemCreate requires name_ru, name_en, base_price')` with `@ts-expect-error` on the old `{ name, price_kopecks }` literal and an assignability check on the full bilingual literal. MUST fail to compile today.
- [ ] 2.2 RED [web-admin] Add failing runtime test `test('createItem POSTs bilingual payload with base_price')` mocking `authenticatedFetch` and asserting the JSON body shape matches the backend `MenuItemCreate`.
- [ ] 2.3 GREEN [web-admin] In `web/admin/src/api/menu.ts`, replace `MenuItemResponse`, `MenuItemCreate`, `MenuItemUpdate` with shapes matching `services/core-api/src/core_api/schemas/menu.py:109-146`. Include `modifiers: ModifierResponse[]` on `MenuItemResponse`. Remove `price_kopecks` and flat `name` / `description`. → passes 2.1, 2.2.

## 3. API client types — Modifier

- [ ] 3.1 RED [web-admin] Add failing test `test('ModifierCreate requires name_ru, name_en, price')` parallel to 1.1.
- [ ] 3.2 RED [web-admin] Add failing runtime test `test('createModifier POSTs bilingual payload')` parallel to 1.2.
- [ ] 3.3 GREEN [web-admin] Replace `ModifierResponse`, `ModifierCreate`, `ModifierUpdate` with the bilingual shape. Rename `price_kopecks` → `price`. Add `sort_order`. → passes 3.1, 3.2.

## 4. API client types — SizeOption

- [ ] 4.1 RED [web-admin] Add failing test `test('SizeOptionCreate requires label: SizeLabel and price')` that `@ts-expect-error`s the old `{ label: 'Small', volume_ml, price_kopecks }` literal and asserts `{ menu_item_id, label: 'S', price: 1500, available: true }` is assignable.
- [ ] 4.2 RED [web-admin] Add failing runtime test `test('createSize POSTs enum label and price')` mocking fetch.
- [ ] 4.3 GREEN [web-admin] Declare `export type SizeLabel = 'S' | 'M' | 'L'`. Replace `SizeOptionResponse`, `SizeOptionCreate`, `SizeOptionUpdate` with the backend shape. Drop `volume_ml`. Rename `price_kopecks` → `price`. → passes 4.1, 4.2.

## 5. API client refactor

- [ ] 5.1 REFACTOR [web-admin] Re-read `web/admin/src/api/menu.ts` top to bottom. Confirm every exported type name matches the backend Pydantic class name (modulo `Response` → `Response`, `Create` → `Create`). Delete unused imports. Run `vitest run src/api/menu.test.ts` and confirm all tests in tasks 1–4 pass together.

## 6. Helper — language-picked display name

- [ ] 6.1 RED [web-admin] In a new or existing `web/admin/src/pages/Menu/utils.test.ts`, add failing test `test('pickLang returns ru for ru, en for en, falls back to ru')` asserting `pickLang('Кофе', 'Coffee', 'en') === 'Coffee'`, `pickLang('Кофе', 'Coffee', 'ru') === 'Кофе'`, `pickLang('Кофе', '', 'en') === 'Кофе'`.
- [ ] 6.2 GREEN [web-admin] In `web/admin/src/pages/Menu/utils.ts`, add `export function pickLang(ru: string, en: string, lang: string): string` implementing the three branches above. Leave existing helpers untouched. → passes 6.1.

## 7. CategoryList — bilingual form

- [ ] 7.1 RED [web-admin] In a new or existing `web/admin/src/pages/Menu/CategoryList.test.tsx`, add a failing test `test('CategoryList create form has name_ru, name_en, and type inputs')` that renders the component with an admin role and asserts three inputs exist via `getByLabelText`. MUST fail today.
- [ ] 7.2 RED [web-admin] Add a second failing test `test('CategoryList create form POSTs bilingual payload')` that mocks `createCategory` and asserts it's called with `{ type: 'drink', name_ru: 'Кофе', name_en: 'Coffee', sort_order: 0, is_visible: true }` after filling the fields and clicking the add button.
- [ ] 7.3 IMPL [web-admin] Rewrite the creation form in `web/admin/src/pages/Menu/CategoryList.tsx` to collect `name_ru`, `name_en`, `type` (as a `<select>` of `CategoryType`). Default `sort_order = categories.length`, `is_visible = true`. Display each category in the list via `pickLang(cat.name_ru, cat.name_en, i18n.language)`. → passes 7.1, 7.2.
- [ ] 7.4 IMPL [web-admin] Rewrite the inline edit mode to expose `name_ru` and `name_en` side by side. `type` SHOULD also be editable via a small `<select>`. `sort_order` and `is_visible` MAY stay hidden for now.
- [ ] 7.5 IMPL [web-admin] Copy the 422 `err.body.detail[*].loc` → field-list pattern from `MenuItemFormDialog` into the category save / create error handlers so users see which bilingual field failed. Reuse existing i18n key style.

## 8. MenuItemFormDialog — bilingual form

- [ ] 8.1 RED [web-admin] In `web/admin/src/pages/Menu/MenuItemFormDialog.test.tsx` (create if absent), add failing test `test('MenuItemFormDialog has name_ru, name_en, description_ru, description_en, sort_order, image_url')` asserting six inputs via `getByLabelText`.
- [ ] 8.2 RED [web-admin] Add failing test `test('MenuItemFormDialog submits bilingual payload with base_price')` mocking `createItem` and asserting the full body shape.
- [ ] 8.3 IMPL [web-admin] Rewrite `FormState` and the form JSX in `MenuItemFormDialog.tsx`: replace `name` with `name_ru` + `name_en` (both required), replace `description` with `description_ru` + `description_en` (both optional), add `sort_order` (number, default 0), add `image_url` (text, optional). Update `handleSubmit` to build the bilingual body with `base_price: rublesToKopecks(form.price)`. → passes 8.1, 8.2.
- [ ] 8.4 IMPL [web-admin] Update the category `<select>` to display options via `pickLang(c.name_ru, c.name_en, i18n.language)`.
- [ ] 8.5 IMPL [web-admin] Update `validate()` to check `name_ru` and `name_en` separately with their own error messages, and `base_price` instead of `price_kopecks` in the 422 field-list mapping.

## 9. MenuItemsTable — language-picked display

- [ ] 9.1 RED [web-admin] In `web/admin/src/pages/Menu/MenuItemsTable.test.tsx` (create if absent), add failing test `test('MenuItemsTable renders picked name and base_price')` asserting that for language `'en'` the table row shows the `name_en` string and the base price (rubles formatting).
- [ ] 9.2 IMPL [web-admin] Update `MenuItemsTable.tsx` to read `item.name_{ru|en}` via `pickLang` and `item.base_price` instead of `item.price_kopecks`. Availability badge logic untouched. → passes 9.1.

## 10. ModifiersPanel — bilingual form

- [ ] 10.1 RED [web-admin] Add failing test `test('ModifiersPanel create form has name_ru, name_en, price')` in a new or existing component test file.
- [ ] 10.2 RED [web-admin] Add failing test `test('ModifiersPanel submits bilingual payload with price')` mocking `createModifier`.
- [ ] 10.3 IMPL [web-admin] Rewrite the creation inputs in `ModifiersPanel.tsx` to `name_ru`, `name_en`, `price`. Add `sort_order` (default 0). Keep `available` toggle. Update the list display to `pickLang`. → passes 10.1, 10.2.
- [ ] 10.4 IMPL [web-admin] Surface 422 field-list errors using the same pattern as `MenuItemFormDialog`.

## 11. SizeOptionsEditor — enum label, drop volume

- [ ] 11.1 RED [web-admin] Add failing test `test('SizeOptionsEditor label input is a select of S, M, L')` asserting three `<option>` elements.
- [ ] 11.2 RED [web-admin] Add failing test `test('SizeOptionsEditor submits price, not price_kopecks')` mocking `createSize`.
- [ ] 11.3 IMPL [web-admin] Rewrite the add-row and edit-row UI in `SizeOptionsEditor.tsx`: label is a `<select>` with `S`, `M`, `L`. Remove the `volume_ml` input. Rename `price_kopecks` → `price` in the submitted body. → passes 11.1, 11.2.

## 12. i18n

- [ ] 12.1 IMPL [web-admin] Add new keys to `web/admin/src/i18n/locales/ru/common.json`: `pages.menu.itemForm.nameRu`, `nameEn`, `descriptionRu`, `descriptionEn`, `sortOrder`, `imageUrl`, `validationNameRu`, `validationNameEn`, `validationBasePrice`; plus `pages.menu.categories.nameRu`, `nameEn`, `type`, `typeOptions.drink`, `typeOptions.food`, `typeOptions.merch`; plus `pages.menu.modifiers.nameRu`, `nameEn`, `price`, `sortOrder`. Remove keys that only existed to label the removed monolingual fields.
- [ ] 12.2 IMPL [web-admin] Mirror every key added in 12.1 in `web/admin/src/i18n/locales/en/common.json` with English strings.
- [ ] 12.3 TEST [web-admin] Add a key-parity test in `web/admin/src/i18n/locales/__tests__/parity.test.ts` (create if absent) that flattens both JSONs and asserts the sorted key lists are identical. This prevents future drift.

## 13. Verify

> **Downstream dependency.** `fix-customer-menu-aggregated-endpoint` has a soft dependency on this change: its verify step 5.3 needs at least one category and one menu item in the database, and the easiest way to seed that is through the admin SPA after this change lands. Two consequences for whoever picks up this worktree:
>
> - If `fix-customer-menu-aggregated-endpoint` has already merged, you can test the customer menu page end-to-end as part of verify step 13.3 below (create a category here, then navigate to the customer SPA `/menu` and confirm the item appears). This is an unlocked bonus smoke test, not a requirement.
> - If `fix-customer-menu-aggregated-endpoint` has NOT yet merged, the customer `/menu` page will still be broken — do NOT treat that as a regression from this change. The customer fix owns the customer menu page; this change owns the admin CRUD surface.
>
> This change does NOT depend on either of the other two sibling changes. It can be implemented, tested, and merged entirely in isolation.

- [ ] 13.1 VERIFY [web-admin] Run `vitest run` in `web/admin/` and capture a green summary. Any failing test MUST be investigated before proceeding.
- [ ] 13.2 VERIFY [web-admin] Run `tsc --noEmit` (or the package.json equivalent) and confirm zero type errors. Any `any` introduced to paper over a rename MUST be removed.
- [ ] 13.3 VERIFY [web-admin] Bring the dev stack up via `./scripts/up.sh`. Log into the admin SPA directly (`http://localhost:<WEB_ADMIN_PORT>/` — do NOT rely on `/admin`, that is `fix-admin-spa-basepath`'s job). Create a category, a modifier, an item with sizes. Confirm every action round-trips without 422. Toggle stop-list for item and modifier. Capture screenshots or a short text log in the task notes.
- [ ] 13.4 VERIFY [web-admin] Confirm via the browser DevTools Network tab that every `POST` / `PUT` / `PATCH` to `/api/v1/admin/menu/*` sends only bilingual keys. No `name`, `price_kopecks`, or `volume_ml` SHALL appear.
