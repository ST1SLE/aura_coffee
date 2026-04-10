## 1. API client foundation

- [x] 1.1 Create `web/admin/src/api/` directory.
- [x] 1.2 Add `web/admin/src/api/client.ts` with `authenticatedFetch(path, init?)`, `ApiError` class, a `getAccessToken(): string | null` seam (stub returning `null` for now), and base-URL resolution from `import.meta.env.VITE_API_BASE_URL`.
- [x] 1.3 Add a unit test for `authenticatedFetch` covering: (a) token present → `Authorization` header set, (b) token absent → no header, (c) caller-supplied `Content-Type` preserved, (d) non-2xx → throws `ApiError` with numeric `status` and parsed body.
- [x] 1.4 Add `web/admin/src/api/menu.ts` with hand-written DTO types mirroring `core_api.schemas.menu` (`CategoryResponse`, `CategoryCreate`, `CategoryUpdate`, `MenuItemResponse`, `MenuItemCreate`, `MenuItemUpdate`, `ModifierResponse`, `ModifierCreate`, `ModifierUpdate`, `SizeOptionResponse`, `SizeOptionCreate`, `SizeOptionUpdate`, `AvailabilityPatch`, and the `availability` enum `'AVAILABLE' | 'STOP_LIST' | 'ARCHIVED'`). Add a comment pointing back to the Pydantic source file.
- [x] 1.5 Implement all menu-admin endpoint wrappers in `api/menu.ts` as specified in `design.md` D3 (categories, items, modifiers, sizes, availability PATCH for items and modifiers). Each function delegates to `authenticatedFetch`, parses JSON, and throws `ApiError` on non-2xx.
- [x] 1.6 Add a unit test for `api/menu.ts` covering at least: `listCategories`, `createItem`, `setItemAvailability`, and a 409 on `deleteCategory` surfacing as `ApiError(409)`. Use `fetch` mocked via `vi.stubGlobal`.

## 2. shadcn primitives needed by the page

- [x] 2.1 Vendor the shadcn `dialog`, `input`, `label`, `table`, `switch`, and `badge` primitives into `web/admin/src/components/ui/` (only these — do not bulk-import). Match the style of the existing `button.tsx`.
- [x] 2.2 If no toast primitive exists, vendor a minimal `sonner` or `toast` primitive, or add a tiny `useNotifier` hook that renders inline banners. Pick one approach and use it consistently across the page.

## 3. Page module scaffold

- [x] 3.1 Create `web/admin/src/pages/Menu/index.tsx` exporting `MenuPage`. Compose three panes: `CategoryList` (left), `MenuItemsTable` (main, scoped to the selected category), and `ModifiersPanel` (secondary area or drawer).
- [x] 3.2 Add a single `useCurrentRole()` hook or module-level getter in `pages/Menu/index.tsx` that returns `'admin' | 'barista'` — stubbed as `'admin'` for now with a `TODO: wire via staff-auth`. This is the seam for D4.
- [x] 3.3 Delete the old placeholder `web/admin/src/pages/MenuPage.tsx` and update `web/admin/src/App.tsx` to import `MenuPage` from `./pages/Menu`.
- [ ] 3.4 Manually verify the route `/menu` renders the new empty layout without errors.

## 4. Categories pane

- [x] 4.1 Implement `pages/Menu/CategoryList.tsx`: fetch on mount via `listCategories()`, render a selectable list, emit `onSelect(categoryId)` to the parent.
- [x] 4.2 Add "New category" dialog/form wired to `createCategory`.
- [x] 4.3 Add inline rename (or edit-in-dialog) wired to `updateCategory`.
- [x] 4.4 Add delete with confirmation wired to `deleteCategory`, catching 409 specifically and showing the "category still has items" message from the i18n file (not a generic error).
- [x] 4.5 Hide "New", "Rename", and "Delete" controls when `currentRole === 'barista'`.
- [x] 4.6 Unit test: the 409 branch of the delete handler surfaces the right i18n key and leaves the category in the list.

## 5. Menu items table

- [x] 5.1 Implement `pages/Menu/MenuItemsTable.tsx`: fetch via `listItems({ categoryId })` when the selected category changes. Render a table with name, price (kopecks→rubles formatted), availability badge, and row actions.
- [x] 5.2 Implement price formatting (kopecks → rubles) as a small utility in `pages/Menu/` (not as a global). Format per current locale.
- [x] 5.3 Render an availability `Switch` per row, disabled when `availability === 'ARCHIVED'`.
- [x] 5.4 Wire the switch to `setItemAvailability(id, next)`; on failure, revert the UI state to the previous value and show an error toast/banner.
- [x] 5.5 Add row actions "Edit" and "Delete" visible only to `admin`. Edit opens `MenuItemFormDialog` prefilled. Delete confirms, calls `deleteItem`, and removes the row on 2xx.
- [x] 5.6 Add a "New item" button above the table visible only to `admin`, which opens `MenuItemFormDialog` in create mode.

## 6. Menu item form dialog

- [x] 6.1 Implement `pages/Menu/MenuItemFormDialog.tsx` with fields `name`, `description`, `category_id` (select from loaded categories), `price` (ruble input, converted to kopecks on submit), `archived` checkbox. Disable submit while a request is in flight.
- [x] 6.2 Native HTML validation plus a hand-written validator: `name` required, `price >= 0`, `category_id` required.
- [x] 6.3 Submit handler: create mode calls `createItem`, on 2xx switch the dialog to edit mode rebound to the returned item; edit mode calls `updateItem`.
- [x] 6.4 On 422, parse the error body and show a validation message referencing the failing fields. Dialog stays open.
- [x] 6.5 Embed `SizeOptionsEditor` below the main form, disabled in create mode until the first save succeeds, enabled in edit mode.

## 7. Size options editor

- [x] 7.1 Implement `pages/Menu/SizeOptionsEditor.tsx` bound to a `menuItemId`. Render the current `size_options` array from the parent item.
- [x] 7.2 "Add size" row wired to `createSize` (`label`, `volume_ml`, `price_kopecks`). On 2xx append to the local list.
- [x] 7.3 Edit-in-place wired to `updateSize`.
- [x] 7.4 Delete wired to `deleteSize`.
- [x] 7.5 On 409 from `createSize` (duplicate label), surface the "Size label already exists" i18n message; do NOT append a duplicate row locally.
- [x] 7.6 Hide all controls (or render disabled) when `currentRole !== 'admin'`.

## 8. Modifiers panel

- [x] 8.1 Implement `pages/Menu/ModifiersPanel.tsx` as an inline section or drawer. Fetch via `listModifiers()` on mount.
- [x] 8.2 Render each modifier with name, price, availability switch (active for admin + barista).
- [x] 8.3 Admin-only: "New modifier" form wired to `createModifier`, "Edit" wired to `updateModifier`, "Delete" wired to `deleteModifier`.
- [x] 8.4 Availability switch wired to `setModifierAvailability`; rollback UI on failure same as item switch.

## 9. i18n

- [x] 9.1 Add RU + EN keys under `pages.menu.*` and `menu.common.*` covering: page title, "New" / "Edit" / "Delete" / "Save" / "Cancel", every field label, availability badges ("Stop", "Archived"), delete-confirmation texts, the "category still has items" message, and the "size label already exists" message.
- [x] 9.2 Verify no hard-coded Russian or English literals remain in `pages/Menu/*`.
- [ ] 9.3 Manual check: toggling `LanguageSwitcher` updates every visible string on the page.

## 10. Role-awareness end-to-end check

- [ ] 10.1 Temporarily flip the `useCurrentRole` stub to `'barista'` and verify: category mutation controls hidden; item create/edit/delete hidden; modifier create/edit/delete hidden; availability switches still work.
- [ ] 10.2 Revert the stub to `'admin'` and re-verify all controls reappear.

## 11. Manual acceptance

- [ ] 11.1 Document in the PR description how to manually inject an access token in devtools so the page can be tested before `staff-auth` lands (e.g., `localStorage.setItem('accessToken', ...)` or whichever key the getter reads).
- [ ] 11.2 With a real backend running, walk through: create category → create item in that category → add two size options → archive the item → un-archive via the form → stop-list it as barista → un-stop-list it → create a modifier → stop-list the modifier → delete the modifier → delete the category (expect 409 because the item still exists) → delete the item → delete the category (now succeeds).
- [ ] 11.3 Note any backend discrepancies against `menu-admin-crud` as follow-up tickets; do NOT patch them in this change.

## 12. Validation

- [x] 12.1 Run `openspec validate menu-admin-ui` and fix any reported issues.
- [x] 12.2 Run `cd web/admin && npm run lint && npm run test && npm run build` — all green.
