## 1. API client

- [x] 1.1 [web-admin] RED: write `web/admin/src/api/promocodes.test.ts` with failing tests for `listPromocodes` (query-string assembly for `state`, `code`, `page`, `per_page`, and `state='all'` omission), `getPromocode`, `createPromocode` (kopecks conversion for `fixed_amount`, integer passthrough for `percent`), `updatePromocode`, `activatePromocode`, `deactivatePromocode`, and 422 error parsing to structured field errors — all should ImportError or AssertionError against missing module
- [x] 1.2 [web-admin] GREEN: create `web/admin/src/api/promocodes.ts` with zod schemas (`PromocodeState`, `PromocodeResponse`, `PromocodeListResponse`, `PromocodeCreateInput`, `PromocodeUpdateInput`) and the six fetch helpers using existing `client.ts` bearer wrapper → passes 1.1

## 2. Routing and removal of flat stub

- [x] 2.1 [web-admin] IMPL: delete `web/admin/src/pages/PromosPage.tsx` flat stub and add `web/admin/src/pages/Promos/index.tsx` re-exporting `PromosPage`
- [x] 2.2 [web-admin] IMPL: update `web/admin/src/App.tsx` — change import to `@/pages/Promos` and wrap the `/promos` route in a dedicated `<ProtectedRoute allowedRoles={['admin']}>` (separate from the admin+barista Layout)

## 3. Table component

- [x] 3.1 [web-admin] IMPL: create `web/admin/src/pages/Promos/PromosTable.tsx` rendering columns `code` (monospace), `state_chip`, `discount` preview, `valid_until` (dim when `state==='expired'`), `uses` (`"n / m"` or `"n / ∞"`), and actions per D10 matrix; clicking a row opens `PromoFormDialog` in edit-mode
- [x] 3.2 [web-admin] TEST: write `web/admin/src/pages/Promos/PromosTable.test.tsx` asserting state-chip render for each of `active | inactive | expired | exhausted`; action visibility/disabled matrix (expired: no activate; active: deactivate only; inactive: activate only); uses-unbounded (`"3 / ∞"`); dim styling on expired row

## 4. Form dialog component

- [x] 4.1 [web-admin] IMPL: create `web/admin/src/pages/Promos/PromoFormDialog.tsx` supporting both create and edit modes with fields `code`, `discount_type` (radio percent/fixed), `discount_value` (suffix `%`/`₽`), `min_order_amount`, `valid_from`, `valid_until` (datetime-local), `max_uses`, `max_uses_per_user`; implements rubles↔kopecks conversion at save/load; lock-after-use disable for `code`/`discount_type`/`discount_value` when `current_uses > 0` with `pages.promos.locked_hint` tooltip; footer renders Cancel/Save/Activate/Deactivate per D10; Activate and Deactivate dispatch separate POST requests (never embedded in PATCH)
- [x] 4.2 [web-admin] TEST: write `web/admin/src/pages/Promos/PromoFormDialog.test.tsx` asserting enabled-matrix for `current_uses=0` vs `current_uses>0`; rubles→kopecks on save and kopecks→rubles on load for `fixed_amount` + `min_order_amount`; percent stays integer; footer buttons for each edit-mode state combo; server 422 `field_locked_after_use` surfaces localized inline error

## 5. Page shell

- [x] 5.1 [web-admin] IMPL: create `web/admin/src/pages/Promos/PromosPage.tsx` shell with state-filter tabs (All/Active/Inactive/Expired/Exhausted, default All, mapping to `?state=` with `all` omitted), debounced (300 ms) code search, Create button opening `PromoFormDialog` in create-mode, and `PromosTable` bound to the React Query list (key `['promos', state, codeDebounced, page]`)
- [x] 5.2 [web-admin] TEST: write `web/admin/src/pages/Promos/PromosPage.test.tsx` asserting tab click triggers list reload with the right `?state=`; `all` tab omits the param and resets page=1; rapid typing debounces into one request; create-dialog open/close wiring

## 6. i18n

- [x] 6.1 [web-admin] IMPL: add `pages.promos.{title, create, search_placeholder, empty, locked_hint}`, `pages.promos.state.{all, active, inactive, expired, exhausted}`, `pages.promos.state_chip.{active, inactive, expired, exhausted}`, `pages.promos.columns.{code, discount, valid_until, uses, actions}`, `pages.promos.form.{code, discount_type, percent, fixed, discount_value, discount_value_percent_suffix, discount_value_rub_suffix, min_order, valid_from, valid_until, max_uses, max_uses_per_user, create_title, edit_title}`, `pages.promos.actions.{create, save, cancel, activate, deactivate, edit}`, `pages.promos.errors.{duplicate_code, dates_inverted, percent_out_of_range, field_locked_after_use, activate_requires_valid_until, activate_expired, activate_exhausted}` to `web/admin/src/i18n/locales/ru.json`
- [x] 6.2 [web-admin] IMPL: add the same key set to `web/admin/src/i18n/locales/en.json` with English copy

## 7. Verification

- [x] 7.1 [web-admin] VERIFY: run `npm --prefix web/admin test` — all new and existing vitest suites pass
- [x] 7.2 [web-admin] VERIFY: run `npm --prefix web/admin run build` — TypeScript + Vite build succeeds with no errors
