## Affected Modules

[web-customer]

Backend modules ([core-api], [redis], [database]) are NOT touched by this change. The implementation of the `menu_public` and `cart` routers is explicitly deferred — see Non-Goals and the `backend integration` risk below.

## Context

Phase 2 of the MVP is "Menu & Cart" (PDD §7.1). The backend side of Phase 2 is partially in place:

- `menu-schema` / `menu-admin-crud` define the menu tables and the admin-facing CRUD.
- `cart-schema` defines `CartItemCreate`, `CartItemResponse`, and `CartResponse` DTOs in `core_api.schemas.cart`.
- The public customer routers `services/core-api/src/core_api/routers/menu_public.py` and `.../cart.py` exist as **empty stubs** mounted under `/api/v1/menu` and `/api/v1/cart`.

The customer SPA shell from `vite-react-scaffold` / `frontend-routing` / `tailwind-shadcn-setup` is also in place:

- `web/customer/src/pages/{HomePage,CartPage,CheckoutPage,ProfilePage,OrdersPage}.tsx` — current placeholder pages.
- `web/customer/src/api/client.ts` — `authenticatedFetch` wrapper with token refresh.
- `web/customer/src/i18n/` — RU + EN resources via `react-i18next`.
- `web/customer/src/auth/` — auth state, `requireAuth` guard.

What is missing and in scope for this change:

- `web/customer/src/api/menu.ts`, `web/customer/src/api/cart.ts` — typed API clients.
- `web/customer/src/store/cart.ts` — cart state store.
- `web/customer/src/pages/Menu/**` — category list, item grid, item-detail selection.
- `web/customer/src/pages/Cart/**` — cart lines, quantity controls, subtotal.
- Route wiring and i18n keys.

Constraint anchors: PDD §4 (Frontend — web/customer), PDD §5.3 (Redis cart key and TTL), PDD §7.1 Phase 2, INV-006 (stop list / prices computed server-side), INV-010 (customer role isolation).

## Goals / Non-Goals

**Goals:**

- Deliver a Phase-2 customer menu browsing UI and a cart UI that together let a logged-in customer build a cart end-to-end against the cart and menu HTTP contracts defined in `core_api.schemas.{menu,cart}`.
- Keep all price and total computation on the server. The UI MUST read `unit_price`, `line_total`, and `subtotal` from `CartResponse` exclusively (INV-006).
- Make the UI testable in isolation from the backend router implementation by depending only on the response shapes and on a mocked `fetch` layer (MSW or a lightweight fetch mock).
- Provide a single place per endpoint for URL and request shape (`api/menu.ts`, `api/cart.ts`), so that switching to the auto-generated OpenAPI client later is a one-file swap per endpoint group.

**Non-Goals:**

- Implementing the backend `menu_public` and `cart` routers. They remain stubs in this change and MUST be implemented in a separate backend change.
- Checkout flow, delivery address picker, payment, promocodes, loyalty points. Those are Phase 3+.
- Admin menu editing — covered by `menu-admin-crud`.
- Optimistic updates, offline mode, anonymous-cart merge, or multi-device cart sync.
- Image hosting, CDN, or `image_url` transforms.
- Switching to the auto-generated OpenAPI TypeScript client. That migration is a separate chore; this change writes thin hand-typed wrappers that mirror the Pydantic schemas exactly and can be replaced 1:1 later.

## Decisions

### D1. State management: a dedicated cart store, not React Query cache

The cart store lives at `web/customer/src/store/cart.ts` and holds exactly one `CartResponse` plus a `status` field (`idle | loading | ready | error`). Every mutation (`addItem`, `updateQuantity`, `removeItem`) delegates to the cart API client and replaces the stored `CartResponse` with the server response.

**Alternatives considered:**

- *React Query / TanStack Query cache as the source of truth.* Rejected for this change because the project has not yet introduced React Query anywhere else — `auth.ts`, `profile.ts`, and `client.ts` all use plain `authenticatedFetch`. Introducing React Query as a side effect of this change would exceed scope and force a scaffolding decision that belongs in its own proposal.
- *`useState` inside `CartPage`.* Rejected because the menu page also needs to call `addItem` and observe the updated cart (header badge, "added to cart" toast), so the cart state MUST live above both pages.

**Library choice:** Zustand is the default when the surrounding code has no existing store library. If `package.json` already pulls in a store library (Redux Toolkit, Jotai, Zustand), the tasks file reuses it. Rationale: avoid adding a second store library to the customer app.

**Why the store MUST NOT recompute totals locally:** INV-006 puts price authority on the server. A local recompute would silently diverge from the server any time a stop-list, size-price, or modifier change lands. The store's selectors read fields straight from the response; there are no local reducers over `items`.

### D2. API client wrappers are hand-typed, not generated

`api/menu.ts` and `api/cart.ts` export plain async functions over `authenticatedFetch`. The TypeScript response types are hand-typed to mirror `core_api.schemas.menu` and `core_api.schemas.cart` exactly (bilingual names, kopecks as `number`, `expires_at` as ISO string).

**Alternatives considered:**

- *Generate TypeScript types from the FastAPI OpenAPI spec (openapi-typescript or orval).* This is the stated long-term plan (config.yaml "API client: auto-generated from FastAPI OpenAPI spec"), but the backend routers are still stubs, so the generated spec would not yet contain menu or cart operations. Running the generator now would either produce empty types or require running it again after the backend change lands.
- *Define types in `api/types.ts` alongside auth types.* Rejected — the existing `api/types.ts` is auth-scoped. Menu and cart have enough surface area (categories, items, sizes, modifiers, cart items, snapshots) that colocating each group with its client is cleaner.

**Migration escape hatch:** each exported function is a single round-trip with no business logic. When the OpenAPI client is introduced, swapping the body of each function to call the generated client is mechanical and does not change call sites.

### D3. Item-detail view is a component inside `MenuPage`, not a separate route

The item-detail card is a drawer/modal rendered by `MenuPage` when the user taps an available item. The visual form (shadcn `Sheet` on mobile, shadcn `Dialog` on desktop) is chosen by the task author; what matters for the spec is that it is a child of `MenuPage` and not a separate route.

**Alternatives considered:**

- *Separate `/menu/item/:id` route.* Rejected — it would add a router entry, a separate loading state, and a back-button story on mobile for no new behavior. A contained component gives the same UX with less surface.

### D4. Route topology

Routes added by this change (all under `requireAuth`, customer role only):

- `GET /menu` → `MenuPage` (category list + item grid + detail card). PDD §4, INV-010.
- `GET /menu/:categoryId` → `MenuPage` with category preselected. Optional deep-link target.
- `GET /cart` → `CartPage`.

`HomePage.tsx` may redirect to `/menu` or keep a splash — that decision is left to the task list and does not affect the spec. `CheckoutPage.tsx` and `OrdersPage.tsx` are untouched by this change.

### D5. Price formatting lives in one helper

A single helper `web/customer/src/lib/formatPrice.ts` (or the existing equivalent if present) converts integer kopecks to a locale-aware string via `Intl.NumberFormat`. Every price label in the menu and cart UI calls this helper. Rationale: price rendering bugs are a recurring INV-006 hazard, and having one helper lets us assert the rendering once in a unit test.

### D6. Tests use MSW over the real backend

Page and store tests stub `fetch` via MSW handlers that return canned `CategoryResponse[]`, `MenuItemResponse[]`, and `CartResponse` payloads. No backend process runs during frontend tests. This matches the existing pattern in `web/customer/src/api/mocks/` (if present) and keeps the frontend test suite independent of the backend router implementation.

### D7. Error and loading states are per-page, not global

Loading and error states are owned by `MenuPage` and `CartPage` individually. No global error boundary is introduced in this change. Rationale: a global error boundary is a separate architectural decision, and forcing one through this change would exceed scope.

## Risks / Trade-offs

- **Backend integration risk → mitigation:** The backend `menu_public` and `cart` routers are empty stubs. This change builds and tests the UI against MSW mocks, so it can land before the backend routers. When the backend change lands, a smoke test (manual or Playwright) is required against a real docker-compose stack to verify the contract match. Tracked as an Open Question.
- **Contract drift risk → mitigation:** Because the TypeScript types are hand-typed, any rename or field change in `core_api.schemas.{menu,cart}` will silently pass the frontend tests until a runtime mismatch happens. Mitigation: the backend change that ships the routers MUST rerun any integration/contract test that exercises the customer endpoints, and the long-term fix is D2's migration to generated types.
- **Cart TTL / expiry risk → mitigation:** `CartResponse.expires_at` exists but this change does not render it as a live countdown and does not auto-refresh on expiry. If the user leaves the cart page open past TTL, the next mutation returns an error and the UI shows a "cart expired" toast, then calls `refresh()`. A full countdown UX is out of scope and belongs to Phase 3 (checkout).
- **i18n coverage risk → mitigation:** Every user-visible string added by this change MUST have a key in both RU and EN resource files. The task list enforces this by making "add keys" its own step and keeping it blocking for the page tasks. Missing-key fallbacks are visible in dev but silent in prod, so this is a review-time check, not a runtime one.
- **Store library choice risk → mitigation:** If `package.json` already includes Zustand or another store, D1's "Zustand by default" can reopen the decision. The first task in the store group checks the existing dependencies and locks the choice before writing any code.

## Migration Plan

- No database migrations. No alembic changes. No environment variables added.
- Forward-only. Rollback = revert the commit; no data to clean up because the customer cart is stored server-side in Redis under `cart:{session_id}` and is untouched by this change.
- Deployment: the customer SPA is rebuilt and served by nginx. There is no staged rollout — the change is gated by `requireAuth` and only a logged-in customer can reach it.
- Deploy order relative to the backend routers: the UI can land first (users see loading spinners and a friendly error because the stub routers return 404/405). Landing the backend routers first is also safe. There is no hard ordering requirement.

## Open Questions

- Which store library to use if `package.json` has none yet — Zustand is the default (see D1), to be confirmed in the first store task.
- Whether `HomePage` should redirect to `/menu` or remain a splash. Left to the task list; does not affect the spec.
- Whether the item-detail card should support picking quantity > 1 on first add or always add with `quantity = 1` and let the user adjust from the cart. Default in the spec is `quantity = 1` on first add; a higher-initial-quantity picker would be a scope extension.
