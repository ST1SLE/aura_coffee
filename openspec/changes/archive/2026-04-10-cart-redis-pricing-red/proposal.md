> **TDD phase: RED.** This is the first of a two-change pair (`cart-redis-pricing-red` → `cart-redis-pricing-green`). This change lands PREREQ setup and failing tests only. Implementation lands in the GREEN change. Both changes share identical proposal, design, and specs — only `tasks.md` differs.

## Why

Phase 2 (Menu & Cart, PDD §7.1) requires a working cart: customers must add menu items with a chosen size and modifiers, adjust quantities, remove lines, and see a subtotal computed **server-side** from fresh menu prices. Today `services/core-api/src/core_api/routers/cart.py` is an empty `APIRouter` stub (produced by `phase2-menu-foundation-green`) and there is no service, no Redis persistence, no pricing logic.

The cart is also the entry point for PDD §7.2 Order Pricing Chain — step 1 (`line_total = (size_price OR base_price + Σ modifier_prices) × quantity`, `subtotal = Σ line_total`) must exist before Phase 3 (Order & Payment) can consume it. Extracting the formula into a reusable `services/pricing.py` module avoids duplicating it in checkout.

Two inviolable rules constrain the design up front:
- **INV-006** — stop-list check is server-side; a `Menu Item` or `Modifier` with `available = false` MUST NOT be added to the cart.
- **INV-014** — cart snapshots are ephemeral display helpers; they do NOT seed `order_items`. Prices are re-read from the menu tables on every cart read.

## What Changes

- Add `services/core-api/src/core_api/services/cart.py` with a `CartService` that reads/writes the Redis cart, validates stop-list, merges identical lines, and hydrates responses via the pricing service.
- Add `services/core-api/src/core_api/services/pricing.py` with pure functions `compute_line_total(base_price, size_price, modifier_prices, quantity) -> int` and `compute_subtotal(line_totals) -> int`, implementing PDD §7.2 step 1.
- Populate `services/core-api/src/core_api/routers/cart.py` with four endpoints:
  - `GET /api/v1/cart` — return current `CartResponse` (recomputed from fresh menu prices).
  - `POST /api/v1/cart/items` — add a `CartItemCreate`; merge into an existing line if `(menu_item_id, size_option_id, sorted(modifier_ids))` matches.
  - `PATCH /api/v1/cart/items/{line_id}` — replace quantity / size / modifiers of an existing line.
  - `DELETE /api/v1/cart/items/{line_id}` — remove a single line. `DELETE /api/v1/cart` clears the whole cart.
- Define the Redis storage contract: key `cart:{user_id}`, value = JSON of `[{menu_item_id, size_option_id, modifier_ids, quantity}]` (raw input only — **no prices cached**, per PDD §5.3 and INV-014). TTL = 86 400 s (24 h) set on every write via `EXPIRE`.
- Add `CART_TTL_SECONDS` to `core_api.settings.Settings` (default `86400`) so tests and ops can override it via env.
- Extend `core_api.schemas.cart`:
  - Add `line_id: str` field to `CartItemResponse` — deterministic hash of `(menu_item_id, size_option_id, sorted(modifier_ids))`, used as the path parameter for PATCH/DELETE. The hash is pure and server-computed; clients never send it.
- Extend `core_api.rbac_matrix.ROUTE_MATRIX` with four new entries (all require `CUSTOMER` role per INV-002).
- Add `tests/test_pricing.py`, `tests/test_cart_service.py`, `tests/test_route_cart.py`, and extend `tests/test_schemas_cart.py` — all failing in this change.
- No Alembic migration. Cart lives in Redis only (PDD §5.3).

## Capabilities

### New Capabilities
- `cart-api`: HTTP endpoints for adding, updating, removing and reading cart lines for an authenticated Customer. Covers RBAC, Redis key layout, TTL semantics, stop-list rejection (INV-006), line merging, and response hydration from fresh menu data.
- `pricing`: pure, database-free functions implementing PDD §7.2 step 1 (line_total, subtotal). Re-used by cart read and future checkout (Phase 3). No dependency on FastAPI, Redis, or SQLAlchemy — only integers.

### Modified Capabilities
- `cart-schema`: `CartItemResponse` gains a server-computed `line_id: str` field (deterministic hash over `(menu_item_id, size_option_id, sorted(modifier_ids))`). `CartItemCreate`, `CartResponse` and all snapshot DTOs are unchanged.

## Impact

- **Code:**
  - New: `services/core-api/src/core_api/services/cart.py`, `services/core-api/src/core_api/services/pricing.py`, `services/core-api/tests/test_pricing.py`, `services/core-api/tests/test_cart_service.py`, `services/core-api/tests/test_route_cart.py`.
  - Modified: `services/core-api/src/core_api/routers/cart.py` (+4 endpoints), `services/core-api/src/core_api/schemas/cart.py` (+`line_id`, +`line_id` helper), `services/core-api/src/core_api/rbac_matrix.py` (+4 entries), `services/core-api/src/core_api/settings.py` (+`cart_ttl_seconds`), `services/core-api/tests/test_schemas_cart.py` (line_id assertions), `services/core-api/tests/test_rbac_matrix.py` (route coverage).
- **Database:** no migrations. Reads from `menu_items`, `size_options`, `modifiers`, `menu_item_modifiers` via SQLAlchemy models in `packages/shared/src/shared/models/menu.py` (created in `phase2-menu-foundation-green`).
- **Redis:** introduces the first `cart:{user_id}` keys per PDD §5.3. 24 h TTL. No other key namespaces touched.
- **APIs:** four new endpoints under `/api/v1/cart`. OpenAPI schema gains cart operations under the existing `cart` tag. Frontend generator will pick them up on next run — no manual TS wiring in this change.
- **Dependencies:** none added. Uses `redis-py` (already pinned), SQLAlchemy 2.0 sync, Pydantic v2, FastAPI — all present.
- **Phase unlocks:** Phase 3 (Order & Payment) checkout step 1 re-uses `services/pricing.py` directly; no copy-paste.
- **MVP Phase:** Phase 2 (Menu & Cart), PDD §7.1.
- **PDD alignment:** strict. §3 (Cart, Cart Item), §5.3 (Redis keys + TTL), §7.2 step 1 (pricing chain), INV-006 (stop list), INV-014 (no persisted snapshot), INV-002 (auth for mutations).

## Non-Goals

- **No checkout, no orders, no payments.** Creating a `PENDING_PAYMENT` order and hitting YuKassa is Phase 3. This change stops at the cart boundary.
- **No promocode, no loyalty points, no delivery fee.** PDD §7.2 steps 2–5 are out of scope; only step 1 (`subtotal`) is implemented.
- **No guest carts.** A valid Customer JWT is required for every cart endpoint (INV-002). Anonymous / pre-login cart is explicitly deferred.
- **No modifier grouping, no min/max selection constraints.** Modifiers are a flat list validated only against the M:N table `menu_item_modifiers`.
- **No frontend changes.** No React components, no Zustand stores, no generated API client updates land in this change. The customer SPA stays on whatever cart placeholder exists.
- **No persisted cart history.** Abandoned carts are not captured. Redis TTL expiry simply deletes them.
- **No admin / barista cart view.** RBAC restricts cart endpoints to `CUSTOMER` only.
- **No price caching, no `unit_price` stored in Redis.** Every cart read recomputes from DB — INV-014 + PDD §7.2 ("цены берутся из БД на момент расчёта").
- **No cart-merge-on-login.** Since guest carts are out of scope, there is no pre-login cart to merge.
- **No stop-list removal at read time.** If a line becomes unavailable after it was added, the cart read surfaces it with an `availability` flag in the snapshot; actual rejection happens at checkout (Phase 3). Add-time still rejects hard per INV-006.
