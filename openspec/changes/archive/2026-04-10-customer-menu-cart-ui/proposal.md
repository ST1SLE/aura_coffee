## Why

Phase 2 of the MVP ("Menu & Cart", PDD §7.1) requires a customer-facing UI so a logged-in user can browse the menu, pick sizes and modifiers, and build a cart before checkout. The backend schemas (`cart-schema`, `menu-schema`, `menu-admin-crud`) and the empty customer shell (`HomePage`, `CartPage`) already exist, but `web/customer/src/api/menu.ts`, `web/customer/src/api/cart.ts`, `web/customer/src/store/cart.ts`, and the real `Menu` / `Cart` pages are not yet implemented. Without them the customer SPA cannot exercise the menu or cart endpoints, blocking Phase 3 (Order & Payment).

## What Changes

- Add a customer menu browsing page (`web/customer/src/pages/Menu/`) with the category list, per-category item grid, and an item-detail card that lets the user pick one `size_option` and zero-or-more `modifiers` before adding to cart.
- Add a customer cart page (`web/customer/src/pages/Cart/`) that renders `CartResponse`: items with bilingual name, selected size/modifier snapshot, unit price, line total, quantity controls (increment/decrement/remove), and a `subtotal` line pinned to the bottom of the viewport.
- Add typed API client wrappers `web/customer/src/api/menu.ts` and `web/customer/src/api/cart.ts` built on the existing `client.ts` (`authenticatedFetch`), mirroring the `MenuItemResponse` / `CartResponse` contracts from `core_api.schemas.menu` and `core_api.schemas.cart`.
- Add a client-side cart store `web/customer/src/store/cart.ts` that holds the last `CartResponse` returned by the server, exposes `addItem`, `updateQuantity`, `removeItem`, and `refresh` actions, and keeps `subtotal` derived from the server response (never recomputed on the client, per INV-006).
- Wire the new pages into `frontend-routing` under `/menu`, `/menu/:categoryId`, and `/cart`; replace the existing `HomePage`/`CartPage` placeholders.
- Add i18n keys under `menu.*` and `cart.*` for RU + EN.

## Capabilities

### New Capabilities
- `customer-menu-ui`: Customer-facing menu browsing — category list, item grid, item detail with size/modifier selection, stop-list handling, add-to-cart action.
- `customer-cart-ui`: Customer-facing cart — list items from `CartResponse`, change quantity, remove items, display server-computed `subtotal`, handle empty state and expired cart.

### Modified Capabilities
<!-- None — backend specs (cart-schema, menu-schema, menu-admin-crud) are not touched. -->

## Impact

- **Affected code**: `web/customer/src/pages/Menu/**`, `web/customer/src/pages/Cart/**`, `web/customer/src/api/menu.ts`, `web/customer/src/api/cart.ts`, `web/customer/src/store/cart.ts`, `web/customer/src/App.tsx` (routes), `web/customer/src/i18n/` (RU/EN resource files).
- **Dependencies**: Consumes (but does not define) `GET /api/v1/menu/categories`, `GET /api/v1/menu/items`, `GET /api/v1/cart`, `POST /api/v1/cart/items`, `PATCH /api/v1/cart/items/{id}`, `DELETE /api/v1/cart/items/{id}`. Contracts come from `core_api.schemas.menu` / `core_api.schemas.cart`. Tests stub the network via MSW/fetch mocks — the UI does not block on the backend router implementation.
- **Infra / backend**: none. No migrations, no new env vars, no worker changes.
- **MVP phase**: Phase 2 — Menu & Cart (PDD §7.1).
- **Inviolable rules touched**: INV-006 (stop list — hide or disable unavailable items; never trust client-side prices), INV-010 (customer role only — the pages live behind `requireAuth`).

## Non-Goals

- Implementing the backend `menu_public` and `cart` routers. They stay empty stubs in this change; a separate backend change will implement them against the existing schemas. The UI is built and tested against MSW/fetch mocks.
- Checkout, address picker, payment, promocodes, loyalty points. Those are Phase 3+ and belong to `CheckoutPage` work.
- Admin menu editing. Covered by `menu-admin-crud`.
- Persisting the cart across devices or merging anonymous and authenticated carts. The cart follows the server's `session_id`-keyed Redis entry from `cart-schema`; client storage is memory-only.
- Offline mode, optimistic mutations, or client-side price recomputation. Every mutation round-trips to the server and the UI re-renders from the returned `CartResponse` (INV-006).
- Image upload, image optimization, or a CDN strategy for `menu_items.image_url`. The UI consumes whatever URL the API returns.
