## 1. Test module scaffolding

- [x] 1.1 [core-api] PREREQ: create empty test module `services/core-api/tests/test_delivery_addresses_api.py` with module docstring describing the RED contract (CRUD router under `/api/v1/profile/addresses`, Haversine at POST, atomic default-flip at PATCH, 404-on-foreign). Imports: `pytest`, `uuid`, `from unittest.mock import patch`, `from fastapi.testclient import TestClient`, `from core_api.main import app`, `from core_api.services.auth import AuthService`. Define module-level `client = TestClient(app)`, `TEST_SECRET = "test-secret-for-delivery-addresses-tests"`, and copy `_make_token`, `_auth_header`, `_patch_jwt` helpers from `test_profile_endpoints.py`. No top-level imports from `core_api.routers.delivery_addresses` or `shared.models.delivery_address` — all target imports live inside each test body so each test fails independently with `ImportError`/`ModuleNotFoundError`, not collection error.
- [x] 1.2 [core-api] PREREQ: create empty test module `services/core-api/tests/test_checkout_delivery_address_id.py` with module docstring, imports `pytest`, `uuid`, `json`, `from datetime import datetime, timezone`, `from unittest.mock import patch, MagicMock, call`, `from fastapi.testclient import TestClient`, `from tests.conftest import _TEST_DB_URL as TEST_DB_URL`, module-level `_IS_SQLITE = TEST_DB_URL.startswith("sqlite")`. Copy the `_JWT_SECRET`, `_make_token`, `_auth`, `_patch_jwt` helpers from `test_route_orders.py`. No top-level imports from `core_api.services.checkout` or `shared.models.delivery_address`.
- [x] 1.3 [core-api] PREREQ: add `_addresses_user(db_session)` fixture to `test_delivery_addresses_api.py` — inserts a `User` + `UserProfile` into `db_session`, flushes to get the UUID, yields `(user_id, jwt_token)`. Use `shared.models.User`, `shared.models.UserProfile`. Seed `ShopSettings(id=1, shop_lat=55.7558, shop_lon=37.6173, delivery_radius_km=5.0, ...)` so Haversine checks have a reference.
- [x] 1.4 [core-api] PREREQ: add `_saved_address(db_session, user_id, **overrides)` helper to both test files that inserts a `DeliveryAddress` row into `db_session` and returns the model. Import statement `from shared.models import DeliveryAddress` lives INSIDE the helper so RED-time import failure surfaces in the test using the helper, not at collection.
- [x] 1.5 [core-api] PREREQ: add `_checkout_user(db_session)` fixture to `test_checkout_delivery_address_id.py` — inserts `User` + `UserProfile` + `LoyaltyAccount(balance=0)`; yields `(user_id, user, token)`. Copy-paste from `test_checkout_service.py` is acceptable for RED (REFACTOR in GREEN may extract to a shared fixture).
- [x] 1.6 [core-api] PREREQ: add `_seed_cart(cart_redis, user_id, items: list[dict])` helper to `test_checkout_delivery_address_id.py` that writes `{"items": items, "updated_at": ...}` into `cart:{user_id}` with TTL 300.

## 2. RED: model exists in shared package

- [x] 2.1 [core-api] RED: add `test_delivery_address_model_importable` in `test_delivery_addresses_api.py` — imports `from shared.models import DeliveryAddress`, asserts `DeliveryAddress.__tablename__ == "delivery_addresses"` and that the class has mapped columns `id`, `user_id`, `label`, `address_text`, `lat`, `lon`, `apartment`, `entrance`, `floor`, `comment`, `is_default`, `created_at`, `updated_at`. MUST fail in RED with `ImportError`.
- [x] 2.2 [core-api] RED: add `test_delivery_address_model_has_user_cascade_delete` — reads `DeliveryAddress.__table__.foreign_keys`, asserts the FK to `users.id` has `ondelete == "CASCADE"` (INV-013). MUST fail with `ImportError`.
- [x] 2.3 [core-api] RED: add `test_delivery_address_has_partial_unique_default_index` — introspects `DeliveryAddress.__table__.indexes`, asserts at least one index is `unique=True` with a `postgresql_where` clause referencing `is_default`. MUST fail with `ImportError`.

## 3. RED: router wiring — mounting and RBAC matrix

- [x] 3.1 [core-api] RED: add `test_delivery_addresses_router_is_mounted` in `test_delivery_addresses_api.py` — uses `client.get("/openapi.json")`, asserts `paths["/api/v1/profile/addresses"]` contains `get` and `post` keys, AND `paths["/api/v1/profile/addresses/{address_id}"]` contains `patch` and `delete` keys. MUST fail (router not registered).
- [x] 3.2 [core-api] RED: add `test_delivery_addresses_rbac_matrix_entries` — imports `ROUTE_MATRIX` from `core_api.rbac_matrix`; asserts the four expected keys are present AND each maps to exactly `{"customer"}`. MUST fail (matrix entries absent).
- [x] 3.3 [core-api] RED: add `test_delivery_addresses_not_in_public_routes` — imports `PUBLIC_ROUTES`; asserts none of the four routes appear. MUST fail in RED ONLY if a developer mis-adds them; until then this test passes trivially. Mark with `pytest.mark.redundant_once_mounted` comment so GREEN can keep it as a regression guard.

## 4. RED: authentication and role gates

- [x] 4.1 [core-api] RED: add `test_list_addresses_requires_auth` — GETs `/api/v1/profile/addresses` without Authorization; asserts `401`. MUST fail until the route exists; for now `RBACMiddleware` returns `401` on any unmounted path only if RBAC runs first — acceptable as "passes" only on real mount.
- [x] 4.2 [core-api] RED: add `test_list_addresses_forbidden_for_staff` — GETs with `_auth_header("barista")`, `_auth_header("admin")`, `_auth_header("courier")` in turn; asserts `403` for all three. MUST fail.
- [x] 4.3 [core-api] RED: add `test_create_address_requires_auth` — POSTs `/api/v1/profile/addresses` without token; asserts `401`. MUST fail.
- [x] 4.4 [core-api] RED: add `test_create_address_forbidden_for_staff` — POSTs with a staff token; asserts `403`. MUST fail.
- [x] 4.5 [core-api] RED: add `test_patch_address_requires_auth` — PATCHes a random UUID without token; asserts `401`. MUST fail.
- [x] 4.6 [core-api] RED: add `test_patch_address_forbidden_for_staff` — PATCHes with a staff token; asserts `403`. MUST fail.
- [x] 4.7 [core-api] RED: add `test_delete_address_requires_auth` — DELETEs a random UUID without token; asserts `401`. MUST fail.
- [x] 4.8 [core-api] RED: add `test_delete_address_forbidden_for_staff` — DELETEs with a staff token; asserts `403`. MUST fail.

## 5. RED: GET list

- [x] 5.1 [core-api] RED: add `test_list_addresses_empty_returns_200_with_empty_list` — authenticated customer with no saved addresses; GETs; asserts `200` with body `[]`. MUST fail (route absent).
- [x] 5.2 [core-api] RED: add `test_list_addresses_returns_own_rows_only` — seeds 2 addresses for user A and 1 for user B; user A GETs; asserts exactly 2 items returned and none of them have `user_id` matching user B (or the `user_id` field is not leaked in the response payload — the test asserts `id` matches the two A-owned rows only). MUST fail.
- [x] 5.3 [core-api] RED: add `test_list_addresses_default_first_then_created_asc` — seeds 3 addresses for the user, exactly one with `is_default=true`, mixed `created_at`; GETs; asserts the default row is at index `0`. MUST fail.

## 6. RED: POST create

- [x] 6.1 [core-api] RED: add `test_create_address_happy_path_returns_201` — customer POSTs `{"label": "Дом", "address_text": "Тверская 1", "lat": 55.7600, "lon": 37.6200}` (within radius vs seeded `ShopSettings`); asserts `201` with response body containing `id` (UUID string), `label`, `address_text`, `lat`, `lon`, `is_default` (bool); asserts a matching row exists in `delivery_addresses`. MUST fail (route absent, model absent).
- [x] 6.2 [core-api] RED: add `test_create_address_rejects_out_of_radius_with_422` — `ShopSettings.delivery_radius_km = 5.0`; POST with `(lat=0.0, lon=0.0)` (thousands of km away); asserts `422` and no row is inserted. MUST fail.
- [x] 6.3 [core-api] RED: add `test_create_address_rejects_missing_fields_with_422` — POST body missing `lat`; asserts `422`. MUST fail.
- [x] 6.4 [core-api] RED: add `test_create_address_persists_optional_fields` — POST body includes `apartment=12`, `entrance=2`, `floor=3`, `comment="код 1234"`; asserts `201` and stored row has those values. MUST fail.
- [x] 6.5 [core-api] RED: add `test_create_address_first_for_user_not_automatically_default` — POST a single address; assert body `is_default` is `False` unless the body explicitly sent `true`. (Product decision: default is opt-in; if the developer prefers "first becomes default" they must update both RED and spec.) MUST fail in RED.
- [x] 6.6 [core-api] RED: add `test_create_address_with_is_default_true_persists_flag` — POST with `is_default=true`; asserts response body has `is_default=true` and the DB row has it too. MUST fail.

## 7. RED: PATCH update

- [x] 7.1 [core-api] RED: add `test_patch_address_updates_label` — seed a row; PATCH `{"label": "Дача"}`; asserts `200` and DB row's `label == "Дача"`. MUST fail.
- [x] 7.2 [core-api] RED: add `test_patch_address_updates_optional_fields` — seed a row; PATCH `{"apartment": "42", "entrance": null}`; asserts `200` and fields updated (including setting a nullable field back to null). MUST fail.
- [x] 7.3 [core-api] RED: add `test_patch_is_default_true_demotes_previous_default` — seed TWO addresses for user A: X (`is_default=true`) and Y (`is_default=false`); PATCH Y with `{"is_default": true}`; reload both rows; assert `X.is_default == False`, `Y.is_default == True`, and a DB-level COUNT of rows with `user_id=A AND is_default=true` equals exactly `1`. MUST fail.
- [x] 7.4 [core-api] RED: add `test_patch_is_default_false_does_not_touch_other_rows` — seed X (default) and Y (not); PATCH X with `{"is_default": false}`; assert X has `is_default=False` and Y still has `is_default=False`. MUST fail.
- [x] 7.5 [core-api] RED: add `test_patch_foreign_address_returns_404` — seed address Z for user B; user A PATCHes Z with `{"label": "hack"}`; assert `404` AND row Z in DB unchanged (label not mutated). MUST fail.
- [x] 7.6 [core-api] RED: add `test_patch_unknown_address_returns_404` — user A PATCHes a random UUID; assert `404`. MUST fail.
- [x] 7.7 [core-api] RED: add `test_patch_returns_updated_body` — seed row; PATCH label; assert response body has the new label (not the old). MUST fail.

## 8. RED: DELETE remove

- [x] 8.1 [core-api] RED: add `test_delete_own_address_returns_204` — seed row; DELETE; assert `204` with empty body and row removed from DB. MUST fail.
- [x] 8.2 [core-api] RED: add `test_delete_foreign_address_returns_404_and_row_persists` — seed Z for user B; user A DELETEs Z; assert `404` AND Z still exists in DB. MUST fail.
- [x] 8.3 [core-api] RED: add `test_delete_unknown_address_returns_404` — DELETE a random UUID; assert `404`. MUST fail.
- [x] 8.4 [core-api] RED: add `test_delete_does_not_mutate_past_order_snapshot` — seed row W and an `orders` row with `delivery_address_snapshot = {"text": "...", "lat": ..., "lon": ...}` copied from W; DELETE W via the API; read the order row; assert `orders.delivery_address_snapshot` is byte-identical to the pre-delete value (INV-014). MUST fail (pre-Postgres — SQLite JSON compare is fine if the fixture writes a dict directly).

## 9. RED: CreateOrderRequest schema — delivery_address_id field

- [x] 9.1 [core-api] RED: add `test_create_order_request_accepts_delivery_address_id` in `test_checkout_delivery_address_id.py` — imports `CreateOrderRequest`; calls `CreateOrderRequest.model_validate({"type": "delivery", "delivery_address_id": str(uuid.uuid4())})`; asserts the returned instance has `delivery_address_id` set to a `UUID` and `delivery_address is None`. MUST fail (field does not exist yet; Pydantic will raise on `extra="forbid"`).
- [x] 9.2 [core-api] RED: add `test_create_order_request_accepts_inline_delivery_address_legacy_path` — `model_validate` with `{"type": "delivery", "delivery_address": {"text": "A", "lat": 55.76, "lon": 37.61}}`; asserts `.delivery_address_id is None` and `.delivery_address is not None`. MUST fail in RED solely on `.delivery_address_id` attribute access (`AttributeError`).
- [x] 9.3 [core-api] RED: add `test_create_order_request_both_set_raises_validation_error` — `model_validate` with `{"type": "delivery", "delivery_address": {...}, "delivery_address_id": "<uuid>"}`; expects `pydantic.ValidationError`. MUST fail.
- [x] 9.4 [core-api] RED: add `test_create_order_request_neither_set_for_delivery_raises` — `model_validate` with `{"type": "delivery"}`; expects `pydantic.ValidationError`. MUST fail.
- [x] 9.5 [core-api] RED: add `test_create_order_request_pickup_without_address_is_valid` — `model_validate` with `{"type": "pickup"}`; asserts no error. This currently PASSES (pickup already works without address); it stays green through GREEN as a regression guard.
- [x] 9.6 [core-api] RED: add `test_post_orders_rejects_both_delivery_fields_with_422` — HTTP-level; POST `/api/v1/orders` with `{"type":"delivery", "delivery_address":{...}, "delivery_address_id":"..."}`; assert `422`. MUST fail.
- [x] 9.7 [core-api] RED: add `test_post_orders_rejects_neither_delivery_field_with_422` — HTTP-level; POST `{"type":"delivery"}` (no address fields); assert `422`. MUST fail.

## 10. RED: checkout service — load saved address and ownership

- [x] 10.1 [core-api] RED: add `test_checkout_loads_saved_address_when_id_provided` — patches `core_api.services.checkout.load_saved_address` with a MagicMock returning a fake address object (lat, lon, address_text, apartment, etc.); seeds cart; calls `create_order(user_id, CreateOrderRequest(type=DELIVERY, delivery_address_id=<uuid>), redis, db)`; asserts `load_saved_address` was called exactly once with `(<uuid>, user_id, db)`. MUST fail with `AttributeError`/`ImportError` (helper does not exist).
- [x] 10.2 [core-api] RED: add `test_checkout_foreign_address_id_returns_404` — HTTP POST `/api/v1/orders` with `delivery_address_id` referring to a row owned by another user; assert `404`. MUST fail.
- [x] 10.3 [core-api] RED: add `test_checkout_unknown_address_id_returns_404` — HTTP POST with a random UUID not present in `delivery_addresses`; assert `404`. MUST fail.
- [x] 10.4 [core-api] RED: add `test_checkout_does_not_call_geocoder_when_address_id_provided` — patches `core_api.services.checkout.geocode_address` with a MagicMock; calls `create_order` via `delivery_address_id`; asserts `geocode_address.called is False`. MUST fail with `AttributeError` (symbol absent).

## 11. RED: checkout service — immutable snapshot

- [x] 11.1 [core-api] RED: add `test_checkout_snapshots_saved_address_into_order_jsonb` — seeds a real `delivery_addresses` row for the user (via `_saved_address`); patches validators + pricing so total>0; calls `create_order` via `delivery_address_id`; reads the new `Order`; asserts `order.delivery_address_snapshot == {"text": <address_text>, "lat": <lat>, "lon": <lon>, "apartment": <...>, "entrance": <...>, "floor": <...>, "comment": <...>}` (omitting keys that were null on the saved row is acceptable — the test accepts either the full dict or the null-stripped subset via `assert set(order.delivery_address_snapshot.keys()) >= {"text", "lat", "lon"}`). MUST fail.
- [x] 11.2 [core-api] RED: add `test_checkout_snapshot_byte_identical_after_saved_address_deleted` — seeds a saved address W; calls `create_order` via `delivery_address_id=W.id`; captures `order.delivery_address_snapshot`; DELETEs W from `delivery_addresses`; re-reads the order; asserts the snapshot JSONB is unchanged. MUST fail.
- [x] 11.3 [core-api] RED: add `test_checkout_snapshot_shape_matches_inline_path` — exercises BOTH paths: one call with inline `delivery_address={"text":"A","lat":55.76,"lon":37.61}` and one call with `delivery_address_id` pointing to a row whose `address_text="A"`, `lat=55.76`, `lon=37.61`; asserts the two resulting `delivery_address_snapshot` values are structurally equal (same keys, same values). MUST fail.

## 12. RED: checkout service — Haversine re-check always fires

- [x] 12.1 [core-api] RED: add `test_checkout_calls_validate_delivery_address_on_saved_path` — patches `core_api.services.checkout.validate_delivery_address` with a MagicMock; calls `create_order` via `delivery_address_id`; asserts `validate_delivery_address.call_count >= 1` AND the first positional/keyword args include the SAVED row's `lat` and `lon` (not something else). MUST fail.
- [x] 12.2 [core-api] RED: add `test_checkout_calls_validate_delivery_address_on_inline_path` — regression guard: the inline path still calls the validator. Calls `create_order` with inline `delivery_address`; asserts `validate_delivery_address.call_count >= 1` with inline lat/lon. MUST fail or PASS depending on current wiring — if `test_checkout_service.py` already covers this, this test remains a cheap duplicate safety-net. Left as RED until GREEN verifies symbol parity between paths.
- [x] 12.3 [core-api] RED: add `test_checkout_rejects_saved_address_now_outside_radius` — seeds saved address W (within radius at save); patches `validate_delivery_address` to raise the existing `DeliveryRadiusError`; calls `create_order` via `delivery_address_id=W.id`; asserts the HTTP response is `409` AND no `orders` row is inserted. MUST fail.
- [x] 12.4 [core-api] RED: add `test_checkout_haversine_uses_saved_row_coords_not_request_body` — seeds saved row with lat=A_lat, lon=A_lon; patches `validate_delivery_address` as MagicMock; POSTs `{"type":"delivery", "delivery_address_id": W.id}`; asserts `validate_delivery_address` was called with `(A_lat, A_lon, ...)` — NOT some other coord pair. MUST fail.

## 13. VERIFY (RED)

- [x] 13.1 [core-api] VERIFY: run `docker compose exec core-api pytest services/core-api/tests/test_delivery_addresses_api.py services/core-api/tests/test_checkout_delivery_address_id.py -v` and confirm that every newly added test FAILS (with `ImportError`, `ModuleNotFoundError`, `AttributeError`, or `AssertionError`), OR is legitimately pre-mounted (e.g. 401/403 passing early due to RBAC default-deny) and documented. No test SHALL pass by accident beyond the explicit regression guards (`test_create_order_request_pickup_without_address_is_valid`, `test_delivery_addresses_not_in_public_routes`). **Confirmed:** 14 failed + 27 errors = 41 RED, 11 passed (8 RBAC default-deny guards [tasks 4.1–4.8], 1 `not_in_public_routes` guard, 1 `both_set_raises_validation_error` via current `extra="forbid"` — will become real XOR check in GREEN, 1 duplicate `validate_delivery_address_on_inline_path` safety-net per task 12.2 note).
- [x] 13.2 [core-api] VERIFY: run `docker compose exec core-api pytest services/core-api/tests/` and confirm all pre-existing tests still pass — the new test files MUST NOT regress collection, fixtures, or imports in the rest of the suite. **Confirmed:** with `--ignore` of new files, suite shows 19 failed + 636 passed + 1 skipped — identical counts to baseline taken with the files physically removed. Zero regressions caused by new files. (19 pre-existing failures in `test_route_order_actions.py` / `test_route_order_history.py` are unrelated to delivery-addresses and flow from main-branch state.)
