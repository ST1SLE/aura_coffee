## Context

**Affected modules:** [core-api], [redis], [shared].

`phase2-menu-foundation-green` merged first and produced:
- ORM models `Category`, `MenuItem`, `SizeOption`, `Modifier`, `menu_item_modifiers` (M:N) in `packages/shared/src/shared/models/menu.py`.
- Pydantic DTOs `CartItemCreate`, `CartItemResponse`, `CartResponse`, `MenuItemCartSnapshot`, `SizeSnapshot`, `ModifierSnapshot` in `services/core-api/src/core_api/schemas/cart.py`.
- Empty `APIRouter` stub at `services/core-api/src/core_api/routers/cart.py` with `prefix="/api/v1/cart"` and `tags=["cart"]`, registered in `main.py`.
- RBAC middleware and `ROUTE_MATRIX` declarative matrix in `core_api.rbac_matrix`, with the Phase 1 entries only.
- Sync Redis dependency `core_api.deps.redis.get_redis` returning a `redis.Redis` from a pool built from `settings.redis_url`.
- Sync DB dependency `core_api.deps.database.get_session` (Phase 1).
- Customer JWT auth + RBAC middleware. A request to an authenticated route has `request.state.user_id: int` populated.

There is no cart service, no pricing logic, and the router currently has zero endpoints. The cart is the last missing piece of Phase 2 and is a **hard blocker** for Phase 3 (Order & Payment), which re-uses the pricing formula and the cart-read path to build the checkout snapshot.

Authoritative sources: `docs/PRODUCT_DESIGN_DOCUMENT.md` §3 (Cart, Cart Item), §5.2 (menu schema), §5.3 (Redis keys, `cart:{session_id}` / 24 h TTL), §7.2 (Order Pricing Chain, step 1), INV-002 (auth for mutations), INV-006 (stop list), INV-014 (immutable order snapshots), INV-015 (secrets via env).

## Goals / Non-Goals

**Goals:**
- Deliver a working, server-authoritative cart for a single authenticated Customer: add, update, remove, read.
- Implement PDD §7.2 step 1 (`line_total`, `subtotal`) in a pure, reusable module so Phase 3 checkout re-uses it verbatim.
- Enforce INV-006 at add time: items with `available = false` (menu item, selected size, or any selected modifier) MUST be rejected with a descriptive error.
- Enforce INV-014: no price is ever stored in Redis. Every cart read recomputes from the live menu tables.
- Keep the Redis key layout, TTL, and serialization format exactly as PDD §5.3 prescribes so Phase 3 checkout can read and discard the key transactionally.
- Provide a deterministic `line_id` so PATCH/DELETE are idempotent and REST-friendly.
- Land as a **RED** change: PREREQ setup + failing tests only. All behavior code is in the companion GREEN change.

**Non-Goals:**
- Promocode, loyalty points, delivery fee, total — PDD §7.2 steps 2–5 are Phase 3+.
- Guest carts / pre-login cart merging — anonymous carts are not supported until a later change explicitly scopes them.
- Admin or Barista access to carts — RBAC is customer-only.
- Frontend changes — the React client is not touched in this change.
- Price caching, `unit_price` in Redis — explicitly forbidden by INV-014.
- Modifier group min/max constraints — flat modifier list only.

## Decisions

### D1. Redis key layout and serialization

**Decision:** key = `cart:{user_id}` (integer `user_id` from JWT `sub`, not a separate session id). Value = JSON string `{"items": [{"menu_item_id": int, "size_option_id": int|null, "modifier_ids": [int,...], "quantity": int}], "updated_at": "<ISO8601>"}`. TTL = `settings.cart_ttl_seconds` (default `86400`, i.e. 24 h per PDD §5.3). TTL is re-applied on **every write** (`SET ... EX` or `EXPIRE`).

**Why `user_id` and not a separate `session_id`?** INV-002 forbids anonymous state mutations. Every cart endpoint requires a valid Customer JWT, so the authenticated user identity is the only session concept the cart needs. Using `user_id` directly avoids a second session store and keeps the key scheme identical for the lifetime of the account.

**Alternatives considered:**
- **Separate `session_id` cookie** — rejected: introduces a second session store, requires guest-to-customer merge on login, and Phase 2 explicitly excludes guest carts.
- **Hash instead of JSON string** — rejected: we always read/write the full cart (there is no "delete one item" Redis operation that does not already need the whole state for price recomputation on the next GET), so a single JSON string is simpler and avoids partial-state bugs.
- **Caching prices in Redis** — rejected by INV-014: stale cached prices at checkout would drift from the menu and poison `order_items`.

### D2. Line identity: deterministic `line_id` hash

**Decision:** `line_id = sha1(f"{menu_item_id}|{size_option_id or 0}|{','.join(str(i) for i in sorted(modifier_ids))}").hexdigest()[:16]`. Computed purely from the client's request shape; stored only in the response DTO (`CartItemResponse.line_id`); never accepted from the client in POST/PATCH bodies (path parameter only).

**Why a hash and not an array index?** Array indices are fragile — any concurrent PATCH/DELETE shifts them and produces race conditions. A deterministic hash makes every PATCH and DELETE idempotent and safe under retries. It also lets POST **merge**: if the computed `line_id` already exists, quantities are summed instead of creating a duplicate line (standard e-commerce behavior).

**Alternatives considered:**
- **Array index** — rejected for the reason above.
- **UUID per line, stored in Redis** — rejected: unnecessary state; the hash is cheaper and equally stable.
- **Server-side counter** — rejected: introduces a second Redis key per cart.

### D3. `services/pricing.py` is pure and DB-free

**Decision:** `compute_line_total(base_price: int, size_price: int | None, modifier_prices: Iterable[int], quantity: int) -> int` and `compute_subtotal(line_totals: Iterable[int]) -> int` take plain integers. No SQLAlchemy, no Pydantic, no FastAPI imports. Formula is the verbatim PDD §7.2 step 1: `unit_price = (size_price if size_price is not None else base_price) + sum(modifier_prices); line_total = unit_price * quantity`.

**Why pure?** Phase 3 checkout re-uses the exact same arithmetic. Keeping it DB-free means both the cart read path and the order-creation path call the same function with the same inputs, and unit tests need zero fixtures.

**Alternatives considered:**
- **Method on `CartService`** — rejected: couples pricing to cart state and blocks reuse in checkout.
- **Pydantic validator on `CartItemResponse`** — rejected: the existing validator checks `line_total == unit_price * quantity`, it does not **compute** `unit_price`. Mixing computation into validation hides the formula behind schema machinery.

### D4. Stop-list validation (INV-006) rejects on add, tolerates on read

**Decision:** `CartService.add_item` loads `MenuItem`, the selected `SizeOption` (if any), and each `Modifier` by id in a single session, and raises `CartValidationError` with a list of `{item, reason}` entries if **any** of:
- `MenuItem.available is False` or `MenuItem.archived is True`
- `SizeOption.available is False` (when a size was selected)
- any `Modifier.available is False`
- `size_option_id` does not belong to this `menu_item_id`
- any `modifier_id` is not linked to this `menu_item_id` via `menu_item_modifiers`
- any of the ids do not exist

On read (`GET /cart`), the service re-fetches the same rows but **does not reject** lines whose components went into the stop list after add time: it surfaces `availability = STOP_LIST` / `ARCHIVED` in each snapshot so the UI can highlight them. Hard rejection for stop-listed lines is deferred to Phase 3 checkout, per PDD §7.2 step 1 ("Если позиция в стоп-листе — ОТКЛОНИТЬ заказ"). The cart read is intentionally non-destructive so a brief stop-list toggle does not silently wipe the customer's cart.

**Alternatives considered:**
- **Reject at read time too** — rejected: hostile UX for short stop-list blips; the rejection point contractually belongs to checkout.
- **Silently drop unavailable lines on read** — rejected: data loss without any user signal.

### D5. Cart merge semantics on POST

**Decision:** when `POST /api/v1/cart/items` receives a `CartItemCreate` whose `line_id` collides with an existing line, the existing line's `quantity` is incremented by the new request's `quantity`, capped at the schema upper bound (`99`). If the cap is exceeded the request is rejected with `409 Conflict` and the existing quantity is left unchanged. This matches typical e-commerce "add to cart" UX and keeps the cart free of near-duplicate lines.

### D6. RBAC matrix entries

**Decision:** add four entries to `core_api.rbac_matrix.ROUTE_MATRIX`, all restricted to `{CUSTOMER}`:

```python
("GET",    "/api/v1/cart"):                      {CUSTOMER},
("DELETE", "/api/v1/cart"):                      {CUSTOMER},
("POST",   "/api/v1/cart/items"):                {CUSTOMER},
("PATCH",  "/api/v1/cart/items/{line_id}"):      {CUSTOMER},
("DELETE", "/api/v1/cart/items/{line_id}"):      {CUSTOMER},
```

The existing `tests/test_route_coverage.py` asserts every authenticated route is either in `ROUTE_MATRIX` or `PUBLIC_ROUTES`; adding the endpoints without the matrix entries would break that test — which is the intended red signal.

**Why not allow staff?** Baristas/admins never act on a customer's cart directly; they operate on orders. Exposing cart endpoints to staff would violate INV-010 (role isolation) and expand the blast radius for no product value.

### D7. Settings: `cart_ttl_seconds`

**Decision:** add `cart_ttl_seconds: int = 86400` to `core_api.settings.Settings`. Tests override it via monkeypatch / env to verify TTL is applied without waiting 24 h. Per INV-015, no hard-coded secret; per convention, non-secret defaults live in `Settings` with env override.

### D8. Error contract

**Decision:** cart endpoints return:
- `400 Bad Request` — validation error from Pydantic (malformed body).
- `404 Not Found` — `line_id` does not exist in the cart (PATCH/DELETE), or referenced `menu_item_id` / `size_option_id` / `modifier_id` does not exist in the DB.
- `409 Conflict` — stop-list hit (INV-006), size/modifier not linked to the menu item, or `quantity` cap exceeded on merge.
- `401 Unauthorized` — no valid JWT (handled by existing auth middleware).
- `403 Forbidden` — authenticated but wrong role (handled by existing RBAC middleware).

Error body shape mirrors Phase 1 conventions (`{"detail": "..."}` or a structured `{"detail": [{"item": ..., "reason": ...}]}` for multi-cause stop-list rejections).

## Risks / Trade-offs

- **[Risk] Race on concurrent POST from the same user** — two browser tabs add items at the same instant; last-writer wins overwrites the other's addition. **Mitigation:** use `WATCH`/`MULTI`/`EXEC` (`redis.Redis.pipeline(transaction=True)`) around the read-modify-write cycle, retry up to 3 times on `WatchError`. Documented in GREEN tasks.
- **[Risk] Pricing drift between cart read and checkout** — price visible in the cart differs from the price charged if the menu changes between calls. **Mitigation:** this is intentional per INV-014. Phase 3 checkout recomputes and presents the price one more time before YuKassa redirect; the cart subtotal is never the authoritative number for payment.
- **[Risk] Stop-list blip wipes cart if we reject on read** — solved by D4.
- **[Risk] `line_id` collisions** — sha1 truncated to 16 hex chars (64 bits) has collision probability ≈ 10⁻¹⁰ within a single cart of ≤ 20 lines; acceptable and not cryptographic. No user-controlled input goes into the hash beyond ids that the server has already validated.
- **[Trade-off] No guest cart** — slightly worse conversion vs. immediate checkout, but aligns with INV-002 and removes a whole class of session-merge bugs. Can be revisited post-MVP.
- **[Trade-off] JSON blob vs. Redis hash** — JSON forces a full read/write each time. Cart size is ≤ 20 lines so payload is < 4 KB; the simpler code path wins.

## Migration Plan

- **Forward:** no DB migration. First deploy of GREEN creates no Redis keys; keys appear on first `POST /api/v1/cart/items` per user. TTL guarantees cleanup even if the service is rolled back before Phase 3 ships.
- **Rollback:** removing the endpoints is safe — the `cart:{user_id}` keys are ephemeral and will expire within 24 h. No DB state to undo.
- **Config:** `CART_TTL_SECONDS` env var is optional; default `86400` works for dev and prod. Document in `.env.example` as part of GREEN.

## Open Questions

- **Q1:** Should `DELETE /api/v1/cart` return `204 No Content` or the empty `CartResponse`? — Decision in GREEN: return empty `CartResponse` for consistency with GET, so the frontend never has to branch on status code.
- **Q2:** Should stale-availability lines surfaced by GET carry a dedicated flag besides the existing `availability` enum in the snapshot? — Defer; the `MenuItemAvailability` enum already distinguishes `AVAILABLE`/`STOP_LIST`/`ARCHIVED`, which is enough for the UI.
