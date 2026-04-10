> **TDD phase: RED.** All tasks in this file produce failing tests or add PREREQ scaffolding. No behavior code. The companion change `cart-redis-pricing-green` turns these tests green.

## 1. Prerequisites (no tests)

- [x] 1.1 **PREREQ** [core-api] Confirm that `phase2-menu-foundation-green` is merged on the base branch: `packages/shared/src/shared/models/menu.py` exports `Category, MenuItem, SizeOption, Modifier, menu_item_modifiers`; `core_api.schemas.cart` exposes `CartItemCreate, CartItemResponse, CartResponse, MenuItemCartSnapshot, SizeSnapshot, ModifierSnapshot`; `core_api.routers.cart.router` exists as an empty `APIRouter(prefix="/api/v1/cart", tags=["cart"])`; `core_api.deps.redis.get_redis` yields a sync `redis.Redis`. Document the verified state at the top of `design.md` if any drift is found.
- [x] 1.2 **PREREQ** [core-api] Add stub module `services/core-api/src/core_api/services/pricing.py` containing only a module docstring and `from __future__ import annotations`. This makes subsequent RED tests fail with `AttributeError` (symbol missing) instead of `ModuleNotFoundError`, which is a clearer red signal.
- [x] 1.3 **PREREQ** [core-api] Add stub module `services/core-api/src/core_api/services/cart.py` with only a module docstring. Same rationale as 1.2.
- [x] 1.4 **PREREQ** [core-api] Register `cart_ttl_seconds: int = 86400` in `core_api.settings.Settings`. Do NOT touch any handler code yet — this is a field-only change.
- [x] 1.5 **PREREQ** [core-api] Add `CART_TTL_SECONDS=86400` to `.env.example` with a comment referencing PDD §5.3 (24 h cart TTL).
- [x] 1.6 **PREREQ** [core-api] Ensure `services/core-api/tests/conftest.py` exposes a `fakeredis`-backed fixture usable by cart tests. If one already exists from `test-infra-fakeredis` spec, reuse it; otherwise add `cart_redis` that monkeypatches `core_api.deps.redis.get_redis` to yield a `fakeredis.FakeRedis` per test and flushes it in teardown. (No behavior tests yet; this is fixture-only.)
- [x] 1.7 **PREREQ** [core-api] Add a test helper `services/core-api/tests/_factories/menu.py` (or extend the existing one) with `make_menu_item(session, *, available=True, archived=False, base_price=15000, sizes=None, modifiers=None)` and matching helpers for `SizeOption` and `Modifier`. This is PREREQ (no assertions); used by every downstream RED test.

## 2. Pricing module (RED)

- [x] 2.1 **RED** [core-api] Add failing test `services/core-api/tests/test_pricing.py::test_compute_line_total_base_price_only` asserting `compute_line_total(base_price=15000, size_price=None, modifier_prices=[], quantity=1) == 15000`. MUST fail with `ImportError` or `AttributeError` (`compute_line_total` not defined in `core_api.services.pricing`).
- [x] 2.2 **RED** [core-api] Add failing test `test_pricing.py::test_compute_line_total_size_overrides_base` asserting `compute_line_total(15000, 20000, [], 1) == 20000`.
- [x] 2.3 **RED** [core-api] Add failing test `test_pricing.py::test_compute_line_total_size_zero_overrides_base` asserting `compute_line_total(15000, 0, [], 1) == 0` (explicit zero is not None).
- [x] 2.4 **RED** [core-api] Add failing test `test_pricing.py::test_compute_line_total_modifiers_sum` asserting `compute_line_total(15000, None, [3000, 5000], 1) == 23000`.
- [x] 2.5 **RED** [core-api] Add failing test `test_pricing.py::test_compute_line_total_quantity_multiplies` asserting `compute_line_total(15000, 20000, [3000], 4) == 92000`.
- [x] 2.6 **RED** [core-api] Add failing test `test_pricing.py::test_compute_line_total_zero_modifiers_no_change` asserting `compute_line_total(10000, None, [0, 0, 0], 2) == 20000`.
- [x] 2.7 **RED** [core-api] Add failing test `test_pricing.py::test_compute_line_total_rejects_negative_base` asserting `compute_line_total(-1, None, [], 1)` raises `ValueError`.
- [x] 2.8 **RED** [core-api] Add failing test `test_pricing.py::test_compute_line_total_rejects_negative_modifier` asserting `compute_line_total(1, None, [-1], 1)` raises `ValueError`.
- [x] 2.9 **RED** [core-api] Add failing test `test_pricing.py::test_compute_line_total_rejects_zero_quantity` asserting `compute_line_total(1, None, [], 0)` raises `ValueError`.
- [x] 2.10 **RED** [core-api] Add failing test `test_pricing.py::test_compute_subtotal_empty_is_zero` asserting `compute_subtotal([]) == 0`.
- [x] 2.11 **RED** [core-api] Add failing test `test_pricing.py::test_compute_subtotal_sums_values` asserting `compute_subtotal([10000, 25000, 5000]) == 40000`.
- [x] 2.12 **RED** [core-api] Add failing test `test_pricing.py::test_compute_subtotal_rejects_negative` asserting `compute_subtotal([10000, -1])` raises `ValueError`.
- [x] 2.13 **RED** [core-api] Add failing test `test_pricing.py::test_pricing_module_has_no_framework_imports` that parses the AST of `services/core-api/src/core_api/services/pricing.py` and asserts no `ImportFrom` node references `sqlalchemy`, `redis`, `fastapi`, `pydantic`, `core_api.models`, `shared.models`.

## 3. cart-schema: line_id helper (RED)

- [x] 3.1 **RED** [core-api] Extend `services/core-api/tests/test_schemas_cart.py` with `test_cart_item_response_has_line_id` asserting `"line_id"` is in `CartItemResponse.model_fields` with type `str`. MUST fail (field does not exist yet).
- [x] 3.2 **RED** [core-api] Add `test_schemas_cart.py::test_cart_item_response_compute_line_id_is_deterministic` asserting that `CartItemResponse.compute_line_id(1, 3, [5, 7]) == CartItemResponse.compute_line_id(1, 3, [5, 7])` and both are 16-char lowercase hex strings.
- [x] 3.3 **RED** [core-api] Add `test_schemas_cart.py::test_cart_item_response_compute_line_id_modifier_order_independent` asserting `compute_line_id(1, 3, [5, 7]) == compute_line_id(1, 3, [7, 5])`.
- [x] 3.4 **RED** [core-api] Add `test_schemas_cart.py::test_cart_item_response_compute_line_id_size_sensitive` asserting `compute_line_id(1, 3, [5]) != compute_line_id(1, 4, [5])`.
- [x] 3.5 **RED** [core-api] Add `test_schemas_cart.py::test_cart_item_response_compute_line_id_modifier_sensitive` asserting `compute_line_id(1, 3, [5]) != compute_line_id(1, 3, [5, 7])`.
- [x] 3.6 **RED** [core-api] Add `test_schemas_cart.py::test_cart_item_response_compute_line_id_size_option_none_stable` asserting `compute_line_id(1, None, []) == compute_line_id(1, None, [])` and both are valid 16-char hex strings.
- [x] 3.7 **RED** [core-api] Add `test_schemas_cart.py::test_cart_item_create_has_no_line_id_field` asserting `"line_id" not in CartItemCreate.model_fields`.
- [x] 3.8 **RED** [core-api] Add `test_schemas_cart.py::test_full_cart_item_response_round_trip_with_line_id` constructing a valid `CartItemResponse` dict including `line_id`, `unit_price=15000`, `quantity=3`, `line_total=45000`, and asserting `.line_id` equals the value returned by `compute_line_id`.

## 4. Cart service: contract (RED)

- [x] 4.1 **RED** [core-api] Add failing test `services/core-api/tests/test_cart_service.py::test_cart_service_importable_with_expected_methods` importing `CartService` from `core_api.services.cart` and asserting it exposes the callables `get`, `add_item`, `update_item`, `delete_item`, `clear`. MUST fail with `ImportError` or `AttributeError`.
- [x] 4.2 **RED** [core-api] Add `test_cart_service.py::test_cart_service_constructor_takes_session_and_redis` asserting `CartService(session=<sqlalchemy.Session>, redis_client=<redis.Redis>, user_id=42, ttl_seconds=60)` constructs without raising.
- [x] 4.3 **RED** [core-api] Add `test_cart_service.py::test_cart_validation_error_exception_exists` asserting `CartValidationError` is importable from `core_api.services.cart` and is a subclass of `Exception`.

## 5. Cart service: get (RED)

- [x] 5.1 **RED** [core-api] Add `test_cart_service.py::test_get_returns_empty_cart_when_no_key` — inject a fakeredis, assert `CartService.get()` returns a `CartResponse` with `items=[]`, `subtotal=0`, `currency="RUB"`, `expires_at > datetime.utcnow()`.
- [x] 5.2 **RED** [core-api] Add `test_cart_service.py::test_get_hydrates_line_with_fresh_prices` — seed DB with a `MenuItem(base_price=15000)`, seed Redis with `{"items": [{"menu_item_id": <id>, "size_option_id": null, "modifier_ids": [], "quantity": 2}], "updated_at": "..."}`; call `get()`; assert `items[0].unit_price == 15000`, `items[0].line_total == 30000`, `subtotal == 30000`, and `items[0].menu_item_snapshot.name_ru` matches the seeded value.
- [x] 5.3 **RED** [core-api] Add `test_cart_service.py::test_get_reflects_updated_menu_price` — seed DB with `base_price=15000`, seed Redis, then update DB to `17000`, call `get()`, assert `unit_price == 17000`.
- [x] 5.4 **RED** [core-api] Add `test_cart_service.py::test_get_refreshes_ttl_on_read` — seed Redis with a key whose TTL is 10 s, call `get()`, assert `fake_redis.ttl("cart:{user_id}")` is now ≈ `ttl_seconds` passed to the service (use `>= ttl_seconds - 2`).
- [x] 5.5 **RED** [core-api] Add `test_cart_service.py::test_get_surfaces_stop_listed_item_without_removing` — seed DB with an available menu item, seed Redis, flip `MenuItem.available = False`, call `get()`, assert the line is still present and `items[0].menu_item_snapshot.availability == MenuItemAvailability.STOP_LIST`.
- [x] 5.6 **RED** [core-api] Add `test_cart_service.py::test_get_surfaces_archived_item_as_archived` — same as 5.5 but with `archived = True` → `availability == ARCHIVED`.

## 6. Cart service: add_item (RED)

- [x] 6.1 **RED** [core-api] Add `test_cart_service.py::test_add_item_creates_new_line` — seed DB, call `add_item(CartItemCreate(menu_item_id=1, size_option_id=3, modifier_ids=[5,7], quantity=2))`, assert Redis key exists, deserialized content has exactly one item with the same fields, and TTL > 0.
- [x] 6.2 **RED** [core-api] Add `test_cart_service.py::test_add_item_persists_no_prices_in_redis` — after a successful add, read raw Redis payload, parse JSON, assert none of `unit_price`, `line_total`, `price`, `subtotal`, `menu_item_snapshot`, `size_snapshot`, `modifiers_snapshot` are keys anywhere in the blob (INV-014).
- [x] 6.3 **RED** [core-api] Add `test_cart_service.py::test_add_item_sets_ttl_atomically` — after a successful add, assert the TTL equals `ttl_seconds` (within 2 s) and that the value was set via a command that includes EX (inspect via `fakeredis` if possible, otherwise assert TTL is not -1).
- [x] 6.4 **RED** [core-api] Add `test_cart_service.py::test_add_item_merges_into_existing_line_same_shape` — add `(menu_item_id=1, size=3, mods=[5,7], qty=2)` then `(1, 3, [5,7], 1)`; assert the cart contains exactly one item with `quantity == 3`.
- [x] 6.5 **RED** [core-api] Add `test_cart_service.py::test_add_item_merges_ignoring_modifier_order` — add `(1, 3, [5, 7], 1)` then `(1, 3, [7, 5], 1)`; assert one item with `quantity == 2`.
- [x] 6.6 **RED** [core-api] Add `test_cart_service.py::test_add_item_rejects_stop_listed_menu_item` — seed `MenuItem.available=False`; assert `add_item(...)` raises `CartValidationError`; assert Redis was not written (`fake_redis.exists("cart:{user_id}") == 0`).
- [x] 6.7 **RED** [core-api] Add `test_cart_service.py::test_add_item_rejects_archived_menu_item` — seed `MenuItem.archived=True`; assert `CartValidationError`.
- [x] 6.8 **RED** [core-api] Add `test_cart_service.py::test_add_item_rejects_stop_listed_size_option` — seed `SizeOption.available=False`; assert `CartValidationError`.
- [x] 6.9 **RED** [core-api] Add `test_cart_service.py::test_add_item_rejects_stop_listed_modifier` — seed one available + one unavailable modifier; pass both in `modifier_ids`; assert `CartValidationError`.
- [x] 6.10 **RED** [core-api] Add `test_cart_service.py::test_add_item_rejects_size_from_different_menu_item` — pass a `size_option_id` belonging to another `MenuItem`; assert `CartValidationError`.
- [x] 6.11 **RED** [core-api] Add `test_cart_service.py::test_add_item_rejects_modifier_not_linked_to_menu_item` — pass a `modifier_id` that exists but is not in `menu_item_modifiers` for this item; assert `CartValidationError`.
- [x] 6.12 **RED** [core-api] Add `test_cart_service.py::test_add_item_rejects_unknown_menu_item_id` — pass a non-existent id; assert `CartValidationError` (distinguished from stop-list; GREEN decides exact subclass or `reason` string).
- [x] 6.13 **RED** [core-api] Add `test_cart_service.py::test_add_item_rejects_merge_exceeding_cap` — seed line `quantity=95`; call `add_item(..., quantity=10)`; assert `CartValidationError`; assert stored quantity still 95.
- [x] 6.14 **RED** [core-api] Add `test_cart_service.py::test_add_item_no_partial_write_on_rejection` — mock a `MenuItem` where stop-list check fails mid-way; assert Redis key state before and after the call is identical.

## 7. Cart service: update_item, delete_item, clear (RED)

- [x] 7.1 **RED** [core-api] Add `test_cart_service.py::test_update_item_changes_quantity` — add a line; compute its `line_id`; call `update_item(line_id, CartItemCreate(...quantity=4))`; assert the stored quantity is 4, not merged with the previous state.
- [x] 7.2 **RED** [core-api] Add `test_cart_service.py::test_update_item_recomputes_line_id_when_modifiers_change` — add `(1, 3, [5])`; update with `(1, 3, [5, 7])`; assert the old `line_id` no longer exists and exactly one line is present.
- [x] 7.3 **RED** [core-api] Add `test_cart_service.py::test_update_item_rejects_unknown_line_id` — call `update_item("deadbeefdeadbeef", ...)`; assert `CartValidationError` with a marker indicating "not found" (GREEN may choose a subclass).
- [x] 7.4 **RED** [core-api] Add `test_cart_service.py::test_update_item_rejects_stop_listed_target_state` — add a valid line; flip the `SizeOption.available` to False; call `update_item(line_id, ...)` with a payload that still references that size; assert `CartValidationError` and stored state unchanged.
- [x] 7.5 **RED** [core-api] Add `test_cart_service.py::test_update_item_refreshes_ttl` — after update, assert TTL ≈ `ttl_seconds`.
- [x] 7.6 **RED** [core-api] Add `test_cart_service.py::test_delete_item_removes_one_line` — add two distinct lines; delete by the first `line_id`; assert only the second remains.
- [x] 7.7 **RED** [core-api] Add `test_cart_service.py::test_delete_item_rejects_unknown_line_id` — call `delete_item("deadbeef...")`; assert `CartValidationError` (not found) and no state mutation.
- [x] 7.8 **RED** [core-api] Add `test_cart_service.py::test_delete_last_item_yields_empty_cart_read` — add one line; delete it; call `get()`; assert `items == []` and `subtotal == 0`. (Implementation may delete the key or store an empty items list; test asserts only the observable `get()` behavior.)
- [x] 7.9 **RED** [core-api] Add `test_cart_service.py::test_clear_deletes_redis_key` — add two lines; call `clear()`; assert `fake_redis.exists("cart:{user_id}") == 0`.
- [x] 7.10 **RED** [core-api] Add `test_cart_service.py::test_clear_is_idempotent_on_empty` — with no key present, call `clear()`; assert no exception and subsequent `get()` returns an empty cart.

## 8. Router endpoints (RED)

- [x] 8.1 **RED** [core-api] Add failing test `services/core-api/tests/test_route_cart.py::test_cart_router_now_has_five_operations` reading `/openapi.json` and asserting that `paths["/api/v1/cart"]` contains `get` and `delete`, `paths["/api/v1/cart/items"]` contains `post`, and `paths["/api/v1/cart/items/{line_id}"]` contains `patch` and `delete`. MUST fail: currently the router stub has zero operations.
- [x] 8.2 **RED** [core-api] Add `test_route_cart.py::test_get_cart_requires_auth` — `TestClient.get("/api/v1/cart")` without a JWT → `401`.
- [x] 8.3 **RED** [core-api] Add `test_route_cart.py::test_get_cart_forbidden_for_staff` — send a barista-role JWT → `403`.
- [x] 8.4 **RED** [core-api] Add `test_route_cart.py::test_get_cart_returns_empty_for_fresh_customer` — authenticated customer; `GET /api/v1/cart` → `200` with `items=[]`, `subtotal=0`.
- [x] 8.5 **RED** [core-api] Add `test_route_cart.py::test_post_cart_item_creates_line_and_returns_full_cart` — seed DB; POST a valid `CartItemCreate`; assert the response body contains one line with the expected `line_id`, `unit_price`, `line_total`.
- [x] 8.6 **RED** [core-api] Add `test_route_cart.py::test_post_cart_item_rejects_stop_listed_with_409` — seed an unavailable menu item; POST → `409` and `detail` describes the reason.
- [x] 8.7 **RED** [core-api] Add `test_route_cart.py::test_post_cart_item_merges_same_line` — POST twice; assert single line with summed quantity.
- [x] 8.8 **RED** [core-api] Add `test_route_cart.py::test_post_cart_item_merge_cap_409` — POST with quantity that would push total over 99; expect `409`, stored quantity unchanged.
- [x] 8.9 **RED** [core-api] Add `test_route_cart.py::test_post_cart_item_unknown_menu_item_404` — POST a non-existent `menu_item_id`; expect `404`.
- [x] 8.10 **RED** [core-api] Add `test_route_cart.py::test_patch_cart_item_updates_quantity` — POST a line, PATCH `/api/v1/cart/items/{line_id}` with `quantity=4`; assert updated.
- [x] 8.11 **RED** [core-api] Add `test_route_cart.py::test_patch_cart_item_unknown_line_id_404` — PATCH an unknown `line_id`; expect `404`.
- [x] 8.12 **RED** [core-api] Add `test_route_cart.py::test_delete_cart_item_removes_line` — POST, DELETE `/api/v1/cart/items/{line_id}`; assert remaining cart matches expectation.
- [x] 8.13 **RED** [core-api] Add `test_route_cart.py::test_delete_cart_item_unknown_line_id_404` — DELETE unknown; expect `404`.
- [x] 8.14 **RED** [core-api] Add `test_route_cart.py::test_delete_cart_clears_all` — POST two lines, `DELETE /api/v1/cart`; assert subsequent GET returns empty.
- [x] 8.15 **RED** [core-api] Add `test_route_cart.py::test_delete_cart_idempotent_on_empty` — fresh user, `DELETE /api/v1/cart` → `200`, empty cart.
- [x] 8.16 **RED** [core-api] Add `test_route_cart.py::test_cart_ttl_env_override_respected` — monkeypatch `settings.cart_ttl_seconds = 60`, POST, inspect fakeredis TTL ≤ 60.

## 9. RBAC matrix coverage (RED)

- [x] 9.1 **RED** [core-api] Extend `services/core-api/tests/test_rbac_matrix.py` (or add a new test file) with `test_cart_routes_are_in_route_matrix` asserting each of the five cart routes is keyed in `ROUTE_MATRIX` with exactly `{CUSTOMER}` as the allowed role set. MUST fail — current matrix has no cart entries.
- [x] 9.2 **RED** [core-api] Add `test_rbac_matrix.py::test_cart_routes_absent_from_public_routes` asserting no cart route appears in `PUBLIC_ROUTES`.
- [x] 9.3 **RED** [core-api] Extend `tests/test_route_coverage.py` so it discovers the five new `/api/v1/cart*` routes and still passes its "every authenticated route is covered" assertion. (In RED state this either fails because the routes do not exist yet, or fails because routes exist without matrix coverage — both are valid red signals; document which one in the task output.)

## 10. Red-state verification

- [x] 10.1 **VERIFY** [core-api] Run `docker compose exec core-api pytest tests/test_pricing.py tests/test_cart_service.py tests/test_route_cart.py tests/test_schemas_cart.py tests/test_rbac_matrix.py tests/test_route_coverage.py -q` and confirm every new test is collected and fails with either `ImportError`, `AttributeError`, or `AssertionError`. No green new tests are allowed in this change. Existing Phase 1 / Phase 2-foundation tests MUST remain green.
- [x] 10.2 **VERIFY** [core-api] Confirm `core_api.settings.Settings().cart_ttl_seconds == 86400` when `CART_TTL_SECONDS` is unset and `== 60` when the env var is set to `60`. (Settings field PREREQ; not a new behavior test.)
- [x] 10.3 **VERIFY** [core-api] Confirm the stub files `services/pricing.py` and `services/cart.py` exist and contain only docstrings and `from __future__ import annotations`, so every RED test fails on symbol lookup rather than module import.
