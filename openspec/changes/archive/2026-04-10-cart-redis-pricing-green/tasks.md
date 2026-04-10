> **TDD phase: GREEN.** The RED change (`cart-redis-pricing-red`) landed all failing tests and PREREQ scaffolding. This change adds the minimum behavior to turn them green and refactors in the same pass. Each GREEN task references the RED tasks it satisfies.

## 1. Pricing module

- [x] 1.1 **GREEN** [core-api] In `services/core-api/src/core_api/services/pricing.py` add `compute_line_total(base_price: int, size_price: int | None, modifier_prices: Iterable[int], quantity: int) -> int`. Implementation: validate all integer inputs ≥ 0 (raise `ValueError` otherwise), validate `quantity >= 1` (raise `ValueError`), compute `unit_price = (size_price if size_price is not None else base_price) + sum(modifier_prices)`, return `unit_price * quantity`. → passes RED 2.1–2.9.
- [x] 1.2 **GREEN** [core-api] Add `compute_subtotal(line_totals: Iterable[int]) -> int`: raise `ValueError` on any negative element, return `sum(line_totals)` with a `0` default for empty iterables. → passes RED 2.10–2.12.
- [x] 1.3 **GREEN** [core-api] Ensure `pricing.py` imports only `from __future__ import annotations`, `from collections.abc import Iterable`, and nothing else. No `sqlalchemy`, `redis`, `fastapi`, `pydantic`, `core_api.models`, `shared.models`. → passes RED 2.13.
- [x] 1.4 **REFACTOR** [core-api] Extract the `unit_price` computation into a private helper `_compute_unit_price` shared between `compute_line_total` (single line) and any future multi-line helper, only if this improves clarity. Otherwise inline. Re-run `pytest tests/test_pricing.py` — all 13 tests must still pass.

## 2. cart-schema: line_id helper

- [x] 2.1 **GREEN** [core-api] Add a classmethod `CartItemResponse.compute_line_id(cls, menu_item_id: int, size_option_id: int | None, modifier_ids: list[int]) -> str` implementing `sha1(f"{menu_item_id}|{size_option_id or 0}|{','.join(str(i) for i in sorted(modifier_ids))}").hexdigest()[:16]`. → passes RED 3.2–3.6.
- [x] 2.2 **GREEN** [core-api] Add `line_id: str` field to `CartItemResponse` (required, no default). → passes RED 3.1, 3.8.
- [x] 2.3 **GREEN** [core-api] Confirm `CartItemCreate.model_fields` still contains only the four input fields; no `line_id`. → passes RED 3.7.
- [x] 2.4 **REFACTOR** [core-api] Move `compute_line_id` above `CartItemResponse`'s other methods and add a short Russian docstring pointing to design D2. No behavior change. Re-run `pytest tests/test_schemas_cart.py`.

## 3. Settings, env, fakeredis fixture

- [x] 3.1 **GREEN** [core-api] Verify `Settings.cart_ttl_seconds` (added in RED 1.4) is reachable via `settings.cart_ttl_seconds` at import time. No code change expected; this is a smoke check. → passes RED 10.2.
- [x] 3.2 **GREEN** [core-api] Verify `.env.example` contains `CART_TTL_SECONDS=86400`. → landed in RED PREREQ 1.5; GREEN just confirms it is present.
- [x] 3.3 **GREEN** [core-api] Confirm the `cart_redis` fixture from `conftest.py` (RED 1.6) overrides `core_api.deps.redis.get_redis` and returns a `fakeredis.FakeRedis`. Add a one-line smoke test `tests/test_cart_fixture_smoke.py::test_cart_redis_fixture_is_fakeredis` asserting the class. Keep this test passing in GREEN.

## 4. CartService: construction and errors

- [x] 4.1 **GREEN** [core-api] In `services/core-api/src/core_api/services/cart.py` declare `class CartValidationError(Exception)` with an optional `reason: str` attribute. → passes RED 4.3.
- [x] 4.2 **GREEN** [core-api] Declare `class CartService` with `__init__(self, *, session: Session, redis_client: redis.Redis, user_id: int, ttl_seconds: int)`. Store each argument. → passes RED 4.2.
- [x] 4.3 **GREEN** [core-api] Add method stubs `get`, `add_item`, `update_item`, `delete_item`, `clear` with proper signatures but raising `NotImplementedError` at first to satisfy RED 4.1. (Subsequent GREEN sub-tasks replace the `NotImplementedError` bodies.)
- [x] 4.4 **GREEN** [core-api] Define the private Redis key helper `_key = lambda self: f"cart:{self.user_id}"` and the private JSON (de)serialization helpers `_load() -> dict` and `_save(payload: dict) -> None` that use `SET <key> <json> EX <ttl_seconds>` in a single command. No behavior tests yet — this is internal scaffolding.

## 5. CartService.get

- [x] 5.1 **GREEN** [core-api] Implement `CartService.get() -> CartResponse`: if `_load()` returns no key, return `CartResponse(items=[], subtotal=0, currency="RUB", expires_at=utcnow + ttl_seconds)`. → passes RED 5.1.
- [x] 5.2 **GREEN** [core-api] For each stored raw item, re-fetch `MenuItem`, `SizeOption` (if any), and the referenced `Modifier` rows from `shared.models.menu`, build snapshots (bilingual names, `availability`), compute `unit_price` / `line_total` via `core_api.services.pricing`, populate `CartItemResponse` including `line_id` via `compute_line_id`. → passes RED 5.2, 5.3.
- [x] 5.3 **GREEN** [core-api] After a successful read, re-serialize and call `_save(...)` (or issue `EXPIRE <key> <ttl_seconds>`) so TTL is renewed. → passes RED 5.4.
- [x] 5.4 **GREEN** [core-api] Map `MenuItem` state to `MenuItemAvailability`: `archived=True → ARCHIVED`, `available=False → STOP_LIST`, else `AVAILABLE`. Surface in `menu_item_snapshot.availability`. Do **not** drop or reject stop-listed lines at read time (design D4). → passes RED 5.5, 5.6.
- [x] 5.5 **REFACTOR** [core-api] Extract `_hydrate_line(raw: dict) -> CartItemResponse` from `get()` so `add_item` / `update_item` can reuse it when they need to return a hydrated `CartResponse`. Re-run `pytest tests/test_cart_service.py::test_get_*` — all six tests still green.

## 6. CartService.add_item

- [x] 6.1 **GREEN** [core-api] Implement `add_item(item: CartItemCreate) -> CartResponse`: load `MenuItem` by id (raise `CartValidationError(reason="not_found")` on missing → passes RED 6.12); load `SizeOption` if `size_option_id` is not None; load all `Modifier` rows matching `item.modifier_ids`. → passes RED 4.1 for `add_item`.
- [x] 6.2 **GREEN** [core-api] Enforce INV-006 and link validation: reject if `MenuItem.available is False`, `MenuItem.archived is True`, the size is unavailable, any modifier is unavailable, the size does not belong to the menu item, or any modifier is not linked via `menu_item_modifiers`. Each rejection raises `CartValidationError` with a specific `reason` marker. → passes RED 6.6–6.11.
- [x] 6.3 **GREEN** [core-api] Compute `new_line_id = CartItemResponse.compute_line_id(...)`. Load current cart (`_load()`). If a line with the same `line_id` exists, increment its `quantity`; else append a new raw dict. Enforce the `quantity ≤ 99` cap; raise `CartValidationError(reason="quantity_cap")` if exceeded. → passes RED 6.4, 6.5, 6.13.
- [x] 6.4 **GREEN** [core-api] Persist via `_save(...)` — only the four raw fields per item plus `updated_at`. No prices stored. → passes RED 6.1, 6.2, 6.3.
- [x] 6.5 **GREEN** [core-api] Ensure that every rejection path returns **before** `_save(...)` is called; use a single load/validate/save sequence. → passes RED 6.14.
- [x] 6.6 **GREEN** [core-api] Return a fully hydrated `CartResponse` by calling `self.get()` at the end of `add_item` (which also refreshes TTL). All hydration invariants are already covered by section 5.
- [x] 6.7 **REFACTOR** [core-api] Extract `_validate_and_resolve(item: CartItemCreate) -> ResolvedItem` dataclass holding `(menu_item, size_option, modifiers)` so `add_item` and `update_item` share the exact same validation path. Re-run all `test_cart_service.py::test_add_item_*` tests — must remain green.

## 7. CartService.update_item / delete_item / clear

- [x] 7.1 **GREEN** [core-api] Implement `update_item(line_id: str, item: CartItemCreate) -> CartResponse`: load cart, find the entry whose `compute_line_id(...)` matches `line_id`; raise `CartValidationError(reason="not_found")` if absent. Re-use `_validate_and_resolve`. Replace the raw entry with the new payload; recompute its `line_id`. Save with TTL. → passes RED 7.1, 7.2, 7.3, 7.4, 7.5.
- [x] 7.2 **GREEN** [core-api] Implement `delete_item(line_id: str) -> CartResponse`: load, filter out the matching entry, raise `CartValidationError(reason="not_found")` if no entry was removed, save the remainder (or `DEL` key if empty). Return `self.get()` so the response shape matches. → passes RED 7.6, 7.7, 7.8.
- [x] 7.3 **GREEN** [core-api] Implement `clear() -> CartResponse`: issue `DEL cart:{user_id}` regardless of prior state and return an empty `CartResponse`. → passes RED 7.9, 7.10.
- [x] 7.4 **REFACTOR** [core-api] Collapse the three mutation methods' common "load → mutate → save → return get()" pattern into a private `_mutate(fn)` helper if it reduces duplication without hiding control flow. Otherwise leave as-is. Re-run `pytest tests/test_cart_service.py -q` — all tests green.

## 8. Router endpoints

- [x] 8.1 **GREEN** [core-api] In `services/core-api/src/core_api/routers/cart.py` import `CartService`, `CartValidationError`, the `get_redis` and `get_session` deps, the auth dep returning `user_id`, and Pydantic schemas from `core_api.schemas.cart`.
- [x] 8.2 **GREEN** [core-api] Implement `GET /` (on the router, so full path = `/api/v1/cart`) returning `CartResponse`. Construct `CartService(session=..., redis_client=..., user_id=..., ttl_seconds=settings.cart_ttl_seconds)` and return `service.get()`. → passes RED 8.1 (GET op), 8.2, 8.3, 8.4, 8.16 (TTL env respect via settings).
- [x] 8.3 **GREEN** [core-api] Implement `POST /items` accepting `CartItemCreate`, returning `CartResponse`. Map `CartValidationError` with `reason="not_found"` → `404`; every other `reason` → `409`. Return `201 Created` on success. → passes RED 8.1 (POST op), 8.5, 8.6, 8.7, 8.8, 8.9.
- [x] 8.4 **GREEN** [core-api] Implement `PATCH /items/{line_id}` accepting `CartItemCreate`, returning `CartResponse`. Map `CartValidationError(reason="not_found")` → `404`, others → `409`. → passes RED 8.1 (PATCH op), 8.10, 8.11.
- [x] 8.5 **GREEN** [core-api] Implement `DELETE /items/{line_id}` returning `CartResponse`. `reason="not_found"` → `404`. → passes RED 8.1 (DELETE op on items), 8.12, 8.13.
- [x] 8.6 **GREEN** [core-api] Implement `DELETE /` (= `/api/v1/cart`) returning an empty `CartResponse`. Idempotent. → passes RED 8.1 (DELETE op on /cart), 8.14, 8.15.
- [x] 8.7 **GREEN** [core-api] Add the five new entries to `core_api.rbac_matrix.ROUTE_MATRIX` all mapped to `{CUSTOMER}`, per design D6. → passes RED 9.1, 9.2, 9.3.
- [x] 8.8 **REFACTOR** [core-api] Extract an exception handler `_cart_error_to_http(exc: CartValidationError) -> HTTPException` that centralizes the `reason → status_code` mapping. Re-run `pytest tests/test_route_cart.py tests/test_rbac_matrix.py tests/test_route_coverage.py -q` — all tests green.

## 9. Concurrency hardening

- [x] 9.1 **GREEN** [core-api] Wrap every read-modify-write cycle (`add_item`, `update_item`, `delete_item`) in a `redis.Redis.pipeline(transaction=True)` block that `WATCH`es `cart:{user_id}`, reads, mutates in Python, then `MULTI/EXEC`s the `SET ... EX`. On `WatchError`, retry up to 3 times; on the 4th attempt raise `CartValidationError(reason="concurrent_modification")` → mapped to `409`.
- [x] 9.2 **GREEN** [core-api] Add a regression test `tests/test_cart_service.py::test_add_item_concurrent_modification_retries` that seeds a cart and mutates the key behind the service once between WATCH and EXEC to force a single retry; assert the final state reflects both mutations. This test is a GREEN-phase addition, not a RED carry-over, because concurrency semantics were too detailed to pin down in RED.

## 10. Migrations, docs, verification

- [x] 10.1 **VERIFY** [core-api] Run `docker compose exec core-api pytest tests/test_pricing.py tests/test_schemas_cart.py tests/test_cart_service.py tests/test_route_cart.py tests/test_rbac_matrix.py tests/test_route_coverage.py tests/test_main_includes_menu_routers.py -q`. Every test MUST pass.
- [x] 10.2 **VERIFY** [core-api] Run the full core-api test suite `docker compose exec core-api pytest -q` — no regressions in Phase 1 or Phase 2 foundation tests.
- [x] 10.3 **VERIFY** [core-api] Manually exercise the happy path with `curl` against a running stack: `POST /api/v1/auth/verify-code` → `POST /api/v1/cart/items` → `GET /api/v1/cart` → `PATCH /api/v1/cart/items/{line_id}` → `DELETE /api/v1/cart/items/{line_id}` → `DELETE /api/v1/cart`. Confirm status codes 200/201, response bodies match the schema, and `redis-cli TTL cart:{user_id}` returns a positive number after each mutation.
- [x] 10.4 **VERIFY** [core-api] Confirm `redis-cli GET cart:{user_id}` returns a JSON blob with only the four raw fields per item plus `updated_at`. Grep for `unit_price`, `line_total`, `snapshot`, `price`, `subtotal` in the payload — all absent (INV-014 guard).
- [x] 10.5 **VERIFY** [core-api] Regenerate the OpenAPI client if the frontend generator is wired into CI. If not, document the manual regeneration step in the PR description so the web-customer worktree can pull the updated cart client in a follow-up.
- [x] 10.6 **REFACTOR** [core-api] Final pass: grep the cart service and router for TODO/FIXME, ensure Russian docstrings on public methods, and confirm no imports of `core_api.schemas.cart` inside the pricing module (it must stay framework-free). Re-run the full suite once.
