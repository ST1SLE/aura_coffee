## 1. Prerequisites

- [x] 1.1 PREREQ [web-customer] Inspect `web/customer/package.json` and record the store library to use in `api/cart.ts` (zustand if absent; reuse existing library if one is already present). Lock the decision in a short comment at the top of the store file created in task 4.1.
- [x] 1.2 PREREQ [web-customer] Install zustand in `web/customer/package.json` if and only if 1.1 concluded that no store library exists. Skip this task otherwise.
- [x] 1.3 PREREQ [web-customer] Create `web/customer/src/api/menuTypes.ts` with TypeScript interfaces `CategoryResponse`, `MenuItemResponse`, `SizeOptionResponse`, `ModifierResponse` mirroring `core_api.schemas.menu` (bilingual name fields, kopecks as `number`, `available`, `archived`).
- [x] 1.4 PREREQ [web-customer] Create `web/customer/src/api/cartTypes.ts` with TypeScript interfaces `CartItemCreate`, `MenuItemCartSnapshot`, `SizeSnapshot`, `ModifierSnapshot`, `CartItemResponse`, `CartResponse` mirroring `core_api.schemas.cart` (`unit_price`, `line_total`, `subtotal` as integer kopecks, `currency: "RUB"`, `expires_at: string`).

## 2. Price formatting helper

- [x] 2.1 RED [web-customer] Create `web/customer/src/lib/formatPrice.test.ts` with cases: `formatPrice(0)` → `"0 ₽"` (RU), `formatPrice(15000)` → `"150 ₽"` (RU), `formatPrice(123450)` → `"1 234,50 ₽"` (RU), `formatPrice(15000, "en")` → `"₽150.00"` or equivalent. Test MUST fail with ImportError.
- [x] 2.2 GREEN [web-customer] Create `web/customer/src/lib/formatPrice.ts` implementing `formatPrice(kopecks: number, locale?: string): string` using `Intl.NumberFormat` with currency `RUB`. Passes 2.1.

## 3. API clients

- [x] 3.1 RED [web-customer] Create `web/customer/src/api/menu.test.ts` that mocks `authenticatedFetch` and asserts: `listCategories()` calls `GET /api/v1/menu/categories`, `listMenuItems({categoryId: 7})` calls `GET /api/v1/menu/items?category_id=7`, `getMenuItem(3)` calls `GET /api/v1/menu/items/3`, HTTP 500 rejects with an error carrying the status. Test MUST fail (module does not exist).
- [x] 3.2 GREEN [web-customer] Create `web/customer/src/api/menu.ts` exporting `listCategories`, `listMenuItems`, `getMenuItem` built on `authenticatedFetch` from `api/client.ts`, returning the types from `menuTypes.ts`. Passes 3.1.
- [x] 3.3 RED [web-customer] Create `web/customer/src/api/cart.test.ts` that mocks `authenticatedFetch` and asserts: `getCart()` → `GET /api/v1/cart`; `addItem({menu_item_id:3,size_option_id:1,modifier_ids:[4],quantity:1})` → `POST /api/v1/cart/items` with that exact JSON body; `updateItem("abc", {quantity: 3})` → `PATCH /api/v1/cart/items/abc` with body `{"quantity":3}`; `removeItem("abc")` → `DELETE /api/v1/cart/items/abc`. Test MUST fail.
- [x] 3.4 GREEN [web-customer] Create `web/customer/src/api/cart.ts` exporting `getCart`, `addItem`, `updateItem`, `removeItem`, returning `CartResponse`. Passes 3.3.
- [x] 3.5 REFACTOR [web-customer] If `api/menu.ts` and `api/cart.ts` share URL-building or JSON-body boilerplate, extract a private helper colocated in `api/client.ts` (do not create a new file). No behavior change; both test suites still pass.

## 4. Cart store

- [x] 4.1 RED [web-customer] Create `web/customer/src/store/cart.test.ts` that mocks `api/cart.ts` and asserts: initial state is `{status: "idle", cart: null}`; `refresh()` transitions to `loading`, then `ready` with the server's `CartResponse`; `addItem(payload)` replaces the stored cart with the server response (reference equality check on `items`); `updateQuantity(id, n)` replaces state with the server response; `removeItem(id)` replaces state with the server response; a rejected `removeItem` leaves state unchanged and rejects the caller; `itemCount` selector sums `quantity` across items; `subtotal` selector returns `response.subtotal` unchanged. Test MUST fail.
- [x] 4.2 GREEN [web-customer] Create `web/customer/src/store/cart.ts` implementing the store using the library chosen in 1.1/1.2, delegating every action to `api/cart.ts` and replacing the stored response wholesale. No local arithmetic on `line_total` or `subtotal`. Passes 4.1.
- [x] 4.3 REFACTOR [web-customer] Extract any duplicated "call api → replace state → rethrow" glue into a single private helper inside `store/cart.ts`. Keep the file single-responsibility; do not create new files. 4.1 still passes.

## 5. i18n keys

- [x] 5.1 IMPL [web-customer] Add `menu.*` keys to `web/customer/src/i18n/locales/ru.json` (or the project's RU resource path): `title`, `empty`, `loading`, `error`, `retry`, `unavailable`, `addToCart`, `added`, `price`, `selectSize`, `modifiers`.
- [x] 5.2 IMPL [web-customer] Add the same `menu.*` keys to the EN resource file.
- [x] 5.3 IMPL [web-customer] Add `cart.*` keys to the RU resource file: `title`, `empty`, `emptyCta`, `loading`, `error`, `retry`, `subtotal`, `remove`, `expired`, `decrement`, `increment`, `modifierSeparator`.
- [x] 5.4 IMPL [web-customer] Add the same `cart.*` keys to the EN resource file.

## 6. Menu page

- [x] 6.1 IMPL [web-customer] Create `web/customer/src/pages/Menu/MenuPage.tsx` rendering loading skeleton → category list ordered by `sort_order` → per-category item grid. On mount call `listCategories()` and `listMenuItems()`. Read `i18n.language` to switch bilingual names. Use `formatPrice` for `base_price`.
- [x] 6.2 TEST [web-customer] Create `web/customer/src/pages/Menu/MenuPage.test.tsx` with MSW handlers for `GET /api/v1/menu/categories` and `GET /api/v1/menu/items`. Cases: renders categories in `sort_order`; renders empty-state when zero categories; renders error with retry on fetch failure and retry re-invokes the fetch.
- [x] 6.3 IMPL [web-customer] Create `web/customer/src/pages/Menu/MenuItemCard.tsx` — single item card. Greyed out and non-clickable when `available === false` or `archived === true`, with a localized `menu.unavailable` badge.
- [x] 6.4 TEST [web-customer] Create `web/customer/src/pages/Menu/MenuItemCard.test.tsx` asserting: clicking an available card fires the `onOpen` callback exactly once; clicking an unavailable card does nothing; unavailable badge renders for `available: false` and for `archived: true`.
- [x] 6.5 IMPL [web-customer] Create `web/customer/src/pages/Menu/ItemDetail.tsx` — drawer/modal rendering `size_options` as single-select (first preselected) and `modifiers` as multi-select. Displays a live current-price label equal to `selectedSize.price + Σ selectedModifiers.price` (or `base_price` if no sizes), formatted via `formatPrice`. Unavailable sizes and modifiers render as disabled. Add-to-Cart is disabled until a size is selected when sizes exist.
- [x] 6.6 TEST [web-customer] Create `web/customer/src/pages/Menu/ItemDetail.test.tsx`. Cases: selecting size `L` (price 22000) shows `220 ₽`; toggling a modifier (price 5000) on top of a 15000 size shows `200 ₽`; unavailable size option renders disabled and is not selectable; Add-to-Cart is disabled when no size is selected on a multi-size item.
- [x] 6.7 IMPL [web-customer] Wire Add-to-Cart in `ItemDetail.tsx` to call `cartStore.addItem({menu_item_id, size_option_id, modifier_ids, quantity: 1})`, then close on success and show a localized `menu.added` toast. On failure keep the view open and show a localized error toast.
- [x] 6.8 TEST [web-customer] Extend `ItemDetail.test.tsx` (or create `ItemDetail.addToCart.test.tsx`) with mocked `cartStore.addItem`: success closes the view and calls the store with the selected payload; rejected `addItem` keeps the view open and renders the error toast.
- [x] 6.9 REFACTOR [web-customer] Review `MenuPage.tsx`, `MenuItemCard.tsx`, `ItemDetail.tsx` for duplicated i18n/price plumbing. Collapse to shared hooks if duplication is literal (≥3 identical lines). Do not introduce new files otherwise. All `pages/Menu/*.test.tsx` still pass.

## 7. Cart page

- [x] 7.1 IMPL [web-customer] Create `web/customer/src/pages/Cart/CartPage.tsx` that calls `cartStore.refresh()` on mount, renders a loading skeleton while `status === "loading"`, and an error state with retry on `"error"`. When `items.length === 0` render the empty-state with a primary action linking to `/menu` and SHALL NOT render the subtotal line.
- [x] 7.2 TEST [web-customer] Create `web/customer/src/pages/Cart/CartPage.test.tsx`. Cases: loading skeleton on initial mount; empty-state hides subtotal and the CTA navigates to `/menu`; error state renders retry which re-invokes `refresh`.
- [x] 7.3 IMPL [web-customer] Create `web/customer/src/pages/Cart/CartLine.tsx` rendering a single `CartItemResponse`: bilingual `menu_item_snapshot.name`, `size_snapshot.label` when present, joined `modifiers_snapshot` names with `cart.modifierSeparator`, `unit_price` and `line_total` via `formatPrice`, quantity display, and `+` / `−` / remove controls.
- [x] 7.4 TEST [web-customer] Create `web/customer/src/pages/Cart/CartLine.test.tsx`. Cases: renders snapshot text (name, size label, two modifiers joined), unit and line totals in rubles; `−` disabled when `quantity === 1`; `+` disabled when `quantity === 99`; clicking `+` at quantity 1 calls `onUpdateQuantity(itemId, 2)` once; clicking remove calls `onRemove(itemId)` once.
- [x] 7.5 IMPL [web-customer] Wire `CartPage.tsx` to render a list of `CartLine` bound to `cartStore.updateQuantity` and `cartStore.removeItem`, and render a bottom-pinned subtotal line showing `formatPrice(subtotal)` together with `currency`. Subtotal line SHALL NOT be rendered when `items.length === 0`.
- [x] 7.6 TEST [web-customer] Extend `CartPage.test.tsx` with MSW/store mocks: rendering a two-item `CartResponse` shows the correct subtotal; after `updateQuantity` resolves with a new subtotal, the rendered subtotal reflects the new value; `removeItem` button triggers `cartStore.removeItem` once with the correct id.
- [x] 7.7 IMPL [web-customer] Handle cart-expired error in `CartPage.tsx`: when a store action rejects with a response identifying expiry (HTTP 410 or backend-defined code from `cart-schema`), render a localized `cart.expired` toast and call `refresh()` once. Do not build a live countdown.
- [x] 7.8 TEST [web-customer] Extend `CartPage.test.tsx` with a cart-expired mock: toast renders and `refresh` is called exactly once.
- [x] 7.9 REFACTOR [web-customer] Collapse any duplicated store-selector plumbing between `CartPage.tsx` and `CartLine.tsx` into a small hook colocated in `store/cart.ts`. No new files. All `pages/Cart/*.test.tsx` still pass.

## 8. Routing and shell wiring

- [x] 8.1 IMPL [web-customer] Update `web/customer/src/App.tsx` to mount `MenuPage` at `/menu` and `/menu/:categoryId` behind `requireAuth`, and replace the existing `/cart` placeholder with the new `CartPage` behind `requireAuth`.
- [x] 8.2 TEST [web-customer] Extend `web/customer/src/App.test.tsx` (or add `App.menuCart.test.tsx` if the existing file resists extension) to assert: unauthenticated `/menu` redirects to `/login?redirect=/menu`; unauthenticated `/cart` redirects to `/login?redirect=/cart`; authenticated `/menu` renders `MenuPage`; authenticated `/cart` renders `CartPage`.
- [x] 8.3 IMPL [web-customer] If `HomePage.tsx` still renders a placeholder, replace its primary CTA with a link to `/menu`. Do not redirect automatically — leave the splash behavior intact.

## 9. Verification

- [x] 9.1 VERIFY [web-customer] Run `pnpm --filter @aura/customer test` (or the equivalent npm/yarn command wired in `package.json`) and confirm the full frontend test suite passes, including every new test from sections 2–8.
- [x] 9.2 VERIFY [web-customer] Run `pnpm --filter @aura/customer build` (or equivalent) and confirm the production build passes with no TypeScript errors and no missing i18n keys in dev-mode warnings.
- [x] 9.3 VERIFY [web-customer] Manual smoke with `docker compose up` and a seeded menu: log in as a customer, browse `/menu`, open an item, pick size + modifiers, add to cart, open `/cart`, change quantity, remove an item, confirm the subtotal displayed matches the `CartResponse.subtotal` returned by the backend in DevTools Network. Only runs after the backend `menu_public` and `cart` routers land; may be deferred and re-run on integration day.
