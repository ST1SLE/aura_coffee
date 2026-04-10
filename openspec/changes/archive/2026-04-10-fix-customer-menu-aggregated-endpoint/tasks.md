## 1. Types — mirror the backend `PublicMenuResponse` tree

- [x] 1.1 RED [web-customer] In `web/customer/src/api/menu.test.ts`, add a failing type-import test `test('menuTypes exports PublicMenuResponse with categories: PublicCategory[]', …)` that imports `PublicMenuResponse`, `PublicCategory`, `PublicMenuItem`, `PublicMenuSizeOption`, `PublicMenuModifier` from `@/api/menuTypes` and asserts at the type level (via `expectTypeOf` or a hand-rolled assignability helper) that `PublicMenuResponse['categories']` is `PublicCategory[]`. MUST fail today because those names don't exist.
- [x] 1.2 GREEN [web-customer] Rewrite `web/customer/src/api/menuTypes.ts`: export `PublicMenuSizeOption`, `PublicMenuModifier`, `PublicMenuItem`, `PublicCategory`, `PublicMenuResponse` with the exact field shape returned by `services/core-api/src/core_api/schemas/menu.py:172-225`. Delete the old `CategoryResponse`, `MenuItemResponse`, `ModifierResponse`, `SizeOptionResponse` aliases if no caller still imports them. → passes 1.1.
- [x] 1.3 REFACTOR [web-customer] Verify via `tsc --noEmit` (or the equivalent Vite script) that no file in `web/customer/src/**` still references the removed monolingual type names. Fix cascading import errors by renaming the type references; no behavior change.

## 2. API client — single aggregated fetch

- [x] 2.1 RED [web-customer] In `web/customer/src/api/menu.test.ts`, add a failing test `test('fetchPublicMenu GETs /api/v1/menu with Accept-Language header')` that mocks `apiRequest` (or the underlying fetch) and asserts: (a) exactly one call, (b) path `/api/v1/menu`, (c) header `Accept-Language: en` when called with `'en'`, (d) returns the mocked `PublicMenuResponse` verbatim. MUST fail because `fetchPublicMenu` does not exist yet.
- [x] 2.2 RED [web-customer] Add a second failing test in the same file `test('fetchPublicMenu sends Accept-Language: ru by default')` that calls `fetchPublicMenu('ru')` and asserts the header.
- [x] 2.3 GREEN [web-customer] Rewrite `web/customer/src/api/menu.ts`: export a single function `fetchPublicMenu(language: 'ru' | 'en'): Promise<PublicMenuResponse>` that calls `apiRequest<PublicMenuResponse>('/api/v1/menu', { headers: { 'Accept-Language': language } })`. Remove `listCategories`, `listMenuItems`, `getMenuItem`. → passes 2.1, 2.2.
- [x] 2.4 REFACTOR [web-customer] Re-read `menu.ts` and delete any unused imports introduced by the rewrite (e.g. old type imports). Run `vitest run src/api/menu.test.ts` once and capture green output in the task log.

## 3. MenuPage — consume the aggregated tree

- [x] 3.1 RED [web-customer] In `web/customer/src/pages/Menu/MenuPage.test.tsx`, update the existing happy-path test so its mock of `@/api/menu` returns a `PublicMenuResponse` with two categories (`sort_order` 10 and 20) each containing two pre-sorted items. Assert that after `await findAllByRole('heading', …)` the rendered category headings appear in the order returned by the mock — NOT client-side resorted. MUST fail today because `MenuPage` calls `listCategories`/`listMenuItems` and re-sorts client-side.
- [x] 3.2 RED [web-customer] Add a second failing test `test('MenuPage refetches when i18n language changes')` that: renders with `i18n.language = 'ru'`, spies on `fetchPublicMenu`, asserts one call with `'ru'`, then fires a language change to `'en'` via `act(() => i18n.changeLanguage('en'))`, and asserts a second call with `'en'`. MUST fail today — current `MenuPage` calls load once in a mount effect.
- [x] 3.3 IMPL [web-customer] Rewrite `web/customer/src/pages/Menu/MenuPage.tsx`: on mount and on i18n language change, call `fetchPublicMenu(lang)`; store the `PublicMenuResponse` in state; render `menu.categories.map(cat => <section>…cat.items.map(renderCard)…</section>)` without any client-side `sort()`. Keep the existing loading / error / empty states intact — only swap data source. → passes 3.1, 3.2.
- [x] 3.4 IMPL [web-customer] Update `web/customer/src/pages/Menu/MenuItemCard.tsx` to accept `item: PublicMenuItem` and read `item.name` (already bilingual-resolved by the backend) instead of picking `name_ru` / `name_en` locally. Keep `lang` prop for display formatting if needed, otherwise remove.
- [x] 3.5 TEST [web-customer] Update `web/customer/src/pages/Menu/MenuItemCard.test.tsx` to pass a `PublicMenuItem` fixture and assert it renders `item.name` verbatim. Fix any fixture references that used the old monolingual type.
- [x] 3.6 IMPL [web-customer] Update `web/customer/src/pages/Menu/ItemDetail.tsx` signature to accept `item: PublicMenuItem` and read `item.name`, `item.description`, `item.size_options`, `item.modifiers` from the already-resolved bilingual projection. No UI layout changes.
- [x] 3.7 TEST [web-customer] Update `web/customer/src/pages/Menu/ItemDetail.test.tsx` fixtures and type references to match the new `PublicMenuItem` shape. Only type-level updates — assertions on computed totals stay unchanged.
- [x] 3.8 REFACTOR [web-customer] Re-read `MenuPage.tsx`, `MenuItemCard.tsx`, `ItemDetail.tsx` and drop any prop or helper that only existed to bridge the old monolingual types (e.g. `lang` picking logic). No behavior change.

## 4. App-level test mock

- [x] 4.1 IMPL [web-customer] Update the `vi.mock('@/api/menu', …)` block in `web/customer/src/App.menuCart.test.tsx` to mock `fetchPublicMenu: vi.fn().mockResolvedValue({ categories: [] })` instead of `listCategories` / `listMenuItems`. Re-run the file and confirm it stays green.

## 5. Verify

- [x] 5.1 VERIFY [web-customer] Run `vitest run` in `web/customer/` and confirm the full suite is green. Capture the summary in the task log.

  > **Result:** 20 test files, 111 tests — all passed.

- [x] 5.2 VERIFY [web-customer] Run `tsc --noEmit` (or the package.json equivalent) and confirm zero type errors. Any remaining reference to the removed monolingual type names MUST cause an explicit compile error, not a silent `any`.

  > **Result:** Zero new errors from our changes. Three pre-existing TS6133 (unused import) warnings in `App.test.tsx` and `VerifyPage.test.tsx` (files outside our lane). No reference to removed monolingual type names survives.

- [ ] 5.3 VERIFY [web-customer] Bring the dev stack up via `./scripts/up.sh`, log in as a customer, seed one category + one item, open `/menu`, and confirm: (a) item renders, (b) switching RU ↔ EN updates the visible name without a hard reload, (c) Network tab shows exactly one `GET /api/v1/menu` per language switch with the correct `Accept-Language` header.

    > **Soft dependency on `fix-admin-menu-bilingual-schema`.** This verify step needs at least one category and one menu item in the database. Two options:
    >
    > - **If `fix-admin-menu-bilingual-schema` has already merged:** seed the data through the admin SPA at `http://localhost:${WEB_ADMIN_PORT}/` (or `/admin/` if `fix-admin-spa-basepath` has also merged). This is the easier path.
    > - **If `fix-admin-menu-bilingual-schema` has NOT yet merged:** the admin SPA cannot create menu data — every POST 422s. Seed directly via one of the following instead:
    >     - `docker compose exec postgres psql -U ${POSTGRES_USER} -d ${POSTGRES_DB}` and run an `INSERT` for one `categories` row + one `menu_items` row (match the column types in `database/migrations`).
    >     - Or call `POST /api/v1/admin/menu/categories` and `POST /api/v1/admin/menu/items` directly via Swagger at `http://localhost:${CORE_API_PORT}/docs`, constructing the bilingual payload by hand — the backend accepts it even when the admin SPA cannot send it.
    >
    > This dependency is one-directional: `fix-admin-menu-bilingual-schema` does NOT need `fix-customer-menu-aggregated-endpoint` to merge first. It can be implemented, tested, and merged entirely in isolation.
