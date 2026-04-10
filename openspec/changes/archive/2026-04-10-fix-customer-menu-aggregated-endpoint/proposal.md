## Why

The customer SPA menu page is broken end-to-end. `web/customer/src/api/menu.ts` calls three endpoints that the backend never exposes publicly:

- `GET /api/v1/menu/categories`
- `GET /api/v1/menu/items[?category_id=…]`
- `GET /api/v1/menu/items/:id`

The public menu router (`services/core-api/src/core_api/routers/menu_public.py:19`) only registers **one** public endpoint, `GET /api/v1/menu`, returning the full aggregated `PublicMenuResponse` in a single round trip. The RBAC middleware default-denies unknown paths, so every call from `MenuPage.tsx` returns 401/403 before the router even sees it. The menu page therefore never renders items, blocking Phase 2 scenarios 2.x and all of Block 3 (cart) in the Phase 2 test matrix.

The backend's aggregated shape is the intentional design (see archived change `2026-04-10-add-public-menu-green` — one bounded query, eager-loaded, ordered, bilingual). This change makes the customer SPA consume that shape instead of inventing endpoints that don't exist.

**MVP Phase**: Phase 2 — Menu & Cart (PDD §7.1).

## What Changes

- Rewrite `web/customer/src/api/menu.ts` to expose **one** function `fetchPublicMenu(language: 'ru' | 'en'): Promise<PublicMenuResponse>` that calls `GET /api/v1/menu` with the matching `Accept-Language` header.
- Remove `listCategories`, `listMenuItems`, `getMenuItem` — they are dead weight against the real backend and every caller will be updated in this change.
- Update `web/customer/src/api/menuTypes.ts` to mirror the backend's `PublicMenuResponse` tree: `PublicMenuResponse → PublicCategory → PublicMenuItem → { PublicMenuSizeOption, PublicMenuModifier }`. Flat per-resource types (`CategoryResponse`, `MenuItemResponse`) are replaced by their `Public*` equivalents so the frontend can't drift from the backend schema again.
- Rewrite `MenuPage.tsx` to fetch once, walk `response.categories[*].items[*]`, and render exactly what the backend already ordered and grouped. Drop the client-side `sort((a,b) => a.sort_order - b.sort_order)` calls — the backend is authoritative.
- Wire the active i18n language into the fetch: when the user switches RU ↔ EN via react-i18next, the menu refetches with the new `Accept-Language` header so bilingual strings come from the server. The `name_ru` / `name_en` fallbacks still live in the response for client-side tooltips / debugging.
- Update `MenuPage.test.tsx`, `menu.test.ts`, and the `vi.mock('@/api/menu', …)` block in `App.menuCart.test.tsx` to match the new one-function API. Tests SHALL be updated in the same change so the test suite stays green.
- `ItemDetail.tsx` keeps its props but switches from `MenuItemResponse` to `PublicMenuItem`. If type renames cascade into `MenuItemCard.tsx`, update the type imports only — no behavior change.

## Capabilities

### Modified Capabilities
- `customer-menu-ui`: switch the menu page's data source from three non-existent endpoints to the aggregated `GET /api/v1/menu`, and bind the request's `Accept-Language` header to the active i18n language.

## Impact

- **Code**:
  - `web/customer/src/api/menu.ts` — rewrite (7 export lines → 1 export line).
  - `web/customer/src/api/menu.test.ts` — rewrite tests to cover the single `fetchPublicMenu` function and the `Accept-Language` header wiring.
  - `web/customer/src/api/menuTypes.ts` — replace monolingual aliases with `Public*` types.
  - `web/customer/src/pages/Menu/MenuPage.tsx` — remove two-call `Promise.all`, drop client-side sort.
  - `web/customer/src/pages/Menu/MenuPage.test.tsx` — update render assertions.
  - `web/customer/src/pages/Menu/ItemDetail.tsx` — type rename only if the compiler demands it.
  - `web/customer/src/pages/Menu/MenuItemCard.tsx` — type rename only if the compiler demands it.
  - `web/customer/src/App.menuCart.test.tsx` — update the `vi.mock('@/api/menu', …)` block to mock `fetchPublicMenu`.
- **APIs**: no backend changes. This change consumes an endpoint that already exists.
- **DB**: none.
- **Auth / RBAC**: none.
- **Workers**: none.
- **Dependencies**: none.

## Non-Goals

- **No new backend endpoints.** `/api/v1/menu/categories`, `/api/v1/menu/items`, `/api/v1/menu/items/:id` are explicitly NOT going to be added. The aggregated endpoint is the contract.
- **No cart behavior changes.** This change touches the menu page only. Cart fixes (including the suspected `PATCH /api/v1/cart/items/:id` schema mismatch) are out of scope and will be handled separately if testing confirms them.
- **No i18n infrastructure changes.** The existing `react-i18next` setup is reused as-is; no provider swap, no new locale files.
- **No admin SPA changes.** This change stays inside `web/customer/`.
- **No nginx / deploy changes.**
- **No client-side caching / SWR.** The SPA refetches on language change and on explicit retry. Memoization can be added later if profiling shows the menu endpoint is hot.
- **MUST NOT edit** any file under `web/admin/**`, `deploy/**`, `services/**`, `packages/**`.

## File Lane (merge safety)

This change is allowed to modify ONLY the following files. Agents working in parallel worktrees on `fix-admin-menu-bilingual-schema` and `fix-admin-spa-basepath` will not touch any of these, so merges are append-only:

```
web/customer/src/api/menu.ts
web/customer/src/api/menu.test.ts
web/customer/src/api/menuTypes.ts
web/customer/src/pages/Menu/MenuPage.tsx
web/customer/src/pages/Menu/MenuPage.test.tsx
web/customer/src/pages/Menu/ItemDetail.tsx
web/customer/src/pages/Menu/MenuItemCard.tsx
web/customer/src/App.menuCart.test.tsx
```

Any need to touch a file outside this list MUST be surfaced back to the user before the change proceeds.
