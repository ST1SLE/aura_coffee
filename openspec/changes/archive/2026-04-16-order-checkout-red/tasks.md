## 1. Test module scaffolding

- [x] 1.1 [core-api] PREREQ: create empty test module `services/core-api/tests/test_checkout_service.py` with module docstring describing the RED contract (Cart → Order conversion, INV-004, INV-014, §7.2 pricing chain wiring). Imports: `pytest`, `uuid`, `json`, `from datetime import datetime, timezone`, `from unittest.mock import patch, MagicMock, call`, `from tests.conftest import _TEST_DB_URL as TEST_DB_URL`, module-level `_IS_SQLITE = TEST_DB_URL.startswith("sqlite")`. No top-level imports from `core_api.services.checkout` (target imports live inside each test body so every test fails with `ImportError`, not collection error).
- [x] 1.2 [core-api] PREREQ: create empty test module `services/core-api/tests/test_route_orders.py` with module docstring, imports `pytest`, `uuid`, `json`, `from unittest.mock import patch, MagicMock`, `from fastapi.testclient import TestClient`, `from tests.conftest import _TEST_DB_URL as TEST_DB_URL`, `_IS_SQLITE`, and the same `_JWT_SECRET`, `_make_token`, `_auth`, `_patch_jwt` helpers as `test_route_cart.py` (copy-paste is acceptable for RED scaffolding — REFACTOR in GREEN can extract to a shared helper).
- [x] 1.3 [core-api] PREREQ: add `_checkout_user` fixture to `test_checkout_service.py` — inserts a `User`, `UserProfile`, and `LoyaltyAccount(balance=0)` into `db_session`, flushes to get the UUID, yields `(user_id, user)`. Uses `shared.models.User`, `shared.models.UserProfile`, `shared.models.LoyaltyAccount`.
- [x] 1.4 [core-api] PREREQ: add a `_seed_cart(cart_redis, user_id, items: list[dict])` helper to `test_checkout_service.py` that writes `{"items": items, "updated_at": ...}` into `cart:{user_id}` with TTL 300. Each item dict has `menu_item_id`, `size_option_id`, `modifier_ids`, `quantity` (mirrors the Redis contract from `services/cart.py`).

## 2. RED: checkout service — import + empty cart

- [x] 2.1 [core-api] RED: add `test_checkout_service_module_importable` in `test_checkout_service.py` — imports `from core_api.services.checkout import create_order`, asserts `callable(create_order)`. MUST fail in RED with `ModuleNotFoundError`.
- [x] 2.2 [core-api] RED: add `test_create_order_rejects_empty_cart` — constructs a fake session + fakeredis with no `cart:{user_id}` key, calls `create_order(user_id, CreateOrderRequest(type=OrderType.PICKUP), fake_redis, fake_session)`, asserts it raises an exception whose message contains "Корзина пуста". MUST fail with `ImportError`.
- [x] 2.3 [core-api] RED: add `test_create_order_rejects_cart_with_zero_items` — seeds `cart:{user_id}` with `{"items": []}` and asserts same rejection. MUST fail with `ImportError`.

## 3. RED: checkout service — validator wiring (pickup path, no promo, no points)

- [x] 3.1 [core-api] RED: add `test_create_order_calls_stop_list_validator` — patches `core_api.services.checkout.validate_stop_list`, `validate_time_slot`, `compute_subtotal`, `apply_promocode`, `apply_loyalty_points`, `compute_order_total`, `compute_estimated_accrual`, `enqueue_payment_task` with MagicMocks; seeds a non-empty cart; calls `create_order` with type=PICKUP; asserts `validate_stop_list` was called at least once with the cart items. MUST fail with `ImportError`.
- [x] 3.2 [core-api] RED: add `test_create_order_calls_time_slot_validator_before_pricing` — patches all validators and pricing; seeds cart; calls `create_order`; asserts `validate_time_slot` was called BEFORE `compute_subtotal` (assert on MagicMock call order via a `parent_mock.mock_calls` list). MUST fail.
- [x] 3.3 [core-api] RED: add `test_create_order_does_not_call_delivery_validators_for_pickup` — patches `validate_delivery_address`, `validate_min_delivery_amount`; calls `create_order` with `type=OrderType.PICKUP`; asserts both are never called. MUST fail.
- [x] 3.4 [core-api] RED: add `test_create_order_does_not_call_promocode_validator_when_code_absent` — patches `validate_promocode`; calls `create_order` with `promocode_code=None`; asserts `validate_promocode` is never called. MUST fail.
- [x] 3.5 [core-api] RED: add `test_create_order_validator_failure_raises_before_db_writes` — patches `validate_stop_list` to raise a custom `ValidatorError`; spies on `db_session.add`; asserts the exception propagates and `db_session.add` is NEVER called. MUST fail.

## 4. RED: checkout service — validator wiring (delivery path)

- [x] 4.1 [core-api] RED: add `test_create_order_delivery_calls_delivery_validators` — patches all validators; seeds cart; calls `create_order` with `type=OrderType.DELIVERY` and a `delivery_address={"text": "Тверская 1", "lat": 55.76, "lon": 37.61}`; asserts `validate_delivery_address` and `validate_min_delivery_amount` are both called. MUST fail.
- [x] 4.2 [core-api] RED: add `test_create_order_delivery_calls_delivery_validators_before_pricing` — asserts call order: `validate_delivery_address` and `validate_min_delivery_amount` both fire BEFORE `compute_subtotal`. MUST fail.
- [x] 4.3 [core-api] RED: add `test_create_order_promocode_validator_called_when_code_provided` — patches `validate_promocode` to return a fake `Promocode` object; calls `create_order` with `promocode_code="SUMMER20"`; asserts `validate_promocode` is called with the code string and the validated subtotal. MUST fail.

## 5. RED: checkout service — pricing chain order

- [x] 5.1 [core-api] RED: add `test_create_order_pricing_chain_order` — patches `compute_subtotal → 50000`, `apply_promocode → (0, 50000)`, `apply_loyalty_points → (0, 50000)`, `compute_delivery_fee → 0`, `compute_order_total → 50000`, `compute_estimated_accrual → 2500`; seeds cart; calls `create_order` with `type=PICKUP, points_to_use=0, promocode_code=None`; asserts call order recorded in a parent-mock's `mock_calls` is `compute_subtotal → apply_promocode → apply_loyalty_points → compute_order_total → compute_estimated_accrual` (compute_delivery_fee is skipped for pickup). MUST fail.
- [x] 5.2 [core-api] RED: add `test_create_order_pricing_delivery_includes_delivery_fee` — same pattern but `type=DELIVERY`; asserts `compute_delivery_fee` IS called and its return value feeds into `compute_order_total`. MUST fail.
- [x] 5.3 [core-api] RED: add `test_create_order_pricing_uses_fresh_prices_from_db` — does NOT patch `compute_subtotal`; seeds a real cart with one item; asserts the resulting `orders.subtotal` equals the menu item's `base_price × quantity` from the DB (not from Redis). MUST fail with `ImportError`.

## 6. RED: checkout service — DB persistence (normal total > 0 path)

- [x] 6.1 [core-api] RED: add `test_create_order_inserts_order_row_with_status_created` — calls `create_order` with normal pickup; queries `db_session` for the new `Order`; asserts `status == OrderStatus.CREATED`, `type == OrderType.PICKUP`, `user_id == _checkout_user`, `total > 0`. MUST fail.
- [x] 6.2 [core-api] RED: add `test_create_order_inserts_order_items_with_snapshots` — seeds cart with one menu item (base_price=15000, name_ru="Латте"); calls `create_order`; asserts the new `OrderItem` has `menu_item_name_ru == "Латте"`, `unit_price == 15000`, `quantity == (from cart)`, `modifiers_snapshot` is a list (JSON-serializable). MUST fail.
- [x] 6.3 [core-api] RED: add `test_create_order_item_stores_menu_item_id_as_reference_not_fk` — after `create_order`, archives the `MenuItem` (sets `archived=True`, flushes); re-reads the `OrderItem`; asserts the row still exists and `menu_item_id` column still holds the original id (no CASCADE delete, no FK constraint violation). MUST fail.
- [x] 6.4 [core-api] RED: add `test_create_order_inserts_payment_with_pending_status_and_idempotency_key` — calls `create_order` with `total > 0`; queries `Payment` by `order_id`; asserts `status == PaymentStatus.PENDING`, `amount == order.total`, `idempotency_key is not None and len(idempotency_key) > 0`. MUST fail.
- [x] 6.5 [core-api] RED: add `test_create_order_payment_amount_matches_order_total` — calls `create_order`; asserts `payment.amount == order.total` (same integer kopeck value). MUST fail.
- [x] 6.6 [core-api] RED: add `test_create_order_order_items_count_matches_cart_lines` — seeds a cart with 3 distinct lines; calls `create_order`; asserts exactly 3 `OrderItem` rows linked to the order. MUST fail.

## 7. RED: checkout service — loyalty reservation

- [x] 7.1 [core-api] RED: add `test_create_order_with_loyalty_points_creates_reservation_transaction` — seeds `LoyaltyAccount(balance=10000)`; calls `create_order(points_to_use=5000)` with `total > 0`; asserts a `LoyaltyTransaction` with `type == LoyaltyTransactionType.RESERVATION`, `amount == -5000`, `user_id == _checkout_user`, `order_id == new_order.id` exists. MUST fail.
- [x] 7.2 [core-api] RED: add `test_create_order_with_loyalty_points_debits_account_balance` — seeds `LoyaltyAccount(balance=10000)`; calls `create_order(points_to_use=5000)`; asserts `loyalty_account.balance == 5000` after commit. MUST fail.
- [x] 7.3 [core-api] RED: add `test_create_order_records_points_used_in_order_row` — calls `create_order(points_to_use=5000)`; asserts `order.points_used == 5000`. MUST fail.
- [x] 7.4 [core-api] RED: add `test_create_order_without_points_skips_loyalty_transaction` — calls `create_order(points_to_use=0)`; asserts no `LoyaltyTransaction` row exists for the order. MUST fail.

## 8. RED: checkout service — promocode application

- [x] 8.1 [core-api] RED: add `test_create_order_with_promocode_increments_current_uses` — seeds a `Promocode(code="SUMMER20", current_uses=3, ...)`; calls `create_order(promocode_code="SUMMER20")`; asserts `promocode.current_uses == 4` after commit. MUST fail.
- [x] 8.2 [core-api] RED: add `test_create_order_with_promocode_inserts_promocode_usage_row` — seeds promocode; calls `create_order`; asserts exactly one `PromocodeUsage` row linking `promocode_id`, `user_id`, `order_id`. MUST fail.
- [x] 8.3 [core-api] RED: add `test_create_order_without_promocode_skips_promocode_usage` — calls `create_order(promocode_code=None)`; asserts no `PromocodeUsage` row for the order, and the orders.promocode_id is NULL. MUST fail.
- [x] 8.4 [core-api] RED: add `test_create_order_stores_discount_amount_on_order` — patches `apply_promocode → (15000, 35000)`; calls `create_order`; asserts `order.discount_amount == 15000`. MUST fail.

## 9. RED: checkout service — total = 0 loyalty-only shortcut

- [x] 9.1 [core-api] RED: add `test_create_order_total_zero_commits_order_as_paid` — patches pricing so `compute_order_total → 0`; calls `create_order`; asserts the returned `OrderResponse.status == OrderStatus.PAID` (same transaction) and the DB row has `status == PAID`. MUST fail.
- [x] 9.2 [core-api] RED: add `test_create_order_total_zero_creates_loyalty_transaction_as_redemption` — patches pricing to total=0 with points_used>0; calls `create_order`; asserts the `LoyaltyTransaction` has `type == LoyaltyTransactionType.REDEMPTION` (NOT `RESERVATION`). MUST fail.
- [x] 9.3 [core-api] RED: add `test_create_order_total_zero_deletes_cart_from_redis` — seeds cart; patches pricing to total=0; calls `create_order`; asserts `cart_redis.exists(f"cart:{user_id}") == 0` after the call. MUST fail.
- [x] 9.4 [core-api] RED: add `test_create_order_total_zero_does_not_enqueue_celery_task` — patches `enqueue_payment_task`; calls `create_order` with total=0; asserts `enqueue_payment_task.called is False`. MUST fail.
- [x] 9.5 [core-api] RED: add `test_create_order_total_zero_payment_row_has_amount_zero` — calls `create_order` with total=0; queries `Payment`; asserts `amount == 0`. MUST fail.

## 10. RED: checkout service — total > 0 celery hand-off

- [x] 10.1 [core-api] RED: add `test_create_order_total_positive_enqueues_celery_task` — patches `enqueue_payment_task`; calls `create_order` with total > 0; asserts `enqueue_payment_task` called exactly once with kwargs including `order_id=<new_id>`, `total=<value>`, `idempotency_key=<str>`. MUST fail.
- [x] 10.2 [core-api] RED: add `test_create_order_total_positive_leaves_cart_in_redis` — seeds cart; calls `create_order` with total > 0; asserts `cart_redis.exists(f"cart:{user_id}") == 1` after the call (cart deletion is deferred to webhook PAID transition, per PDD §6.1). MUST fail.
- [x] 10.3 [core-api] RED: add `test_create_order_total_positive_returns_created_status` — calls `create_order` with total > 0; asserts the returned `OrderResponse.status == OrderStatus.CREATED` and `confirmation_url is None` (worker has not run yet). MUST fail.
- [x] 10.4 [core-api] RED: add `test_create_order_enqueues_after_db_commit` — instruments the DB session and `enqueue_payment_task` to record invocation order; asserts `enqueue_payment_task` fires AFTER the `INSERT` that persists Order (e.g. via a sentinel value on the mock that checks the order is present in the DB when the mock is invoked). MUST fail.

## 11. RED: HTTP route — POST /api/v1/orders

- [x] 11.1 [core-api] RED: add `test_orders_router_exposes_post` in `test_route_orders.py` — uses `client.get("/openapi.json")`, asserts `post` key in `paths["/api/v1/orders"]`. MUST fail (orders router not registered).
- [x] 11.2 [core-api] RED: add `test_post_orders_requires_auth` — POSTs `/api/v1/orders` without Authorization header; asserts `401`. MUST fail.
- [x] 11.3 [core-api] RED: add `test_post_orders_forbidden_for_staff` — POSTs with `_auth("barista")`; asserts `403`. MUST fail.
- [x] 11.4 [core-api] RED: add `test_post_orders_forbidden_for_admin_and_courier` — POSTs with `_auth("admin")` and `_auth("courier")` separately; asserts `403` for both. MUST fail.
- [x] 11.5 [core-api] RED: add `test_post_orders_empty_cart_returns_400` — authenticated customer POSTs with no cart in Redis; asserts `400`. MUST fail.
- [x] 11.6 [core-api] RED: add `test_post_orders_happy_path_returns_201` — seeds cart with one item; patches validators + pricing to succeed; POSTs `{"type": "pickup"}`; asserts `201` with JSON `status == "created"` and `id` is a UUID string. MUST fail.
- [x] 11.7 [core-api] RED: add `test_post_orders_validator_failure_returns_409` — patches `validate_stop_list` to raise; POSTs; asserts `409`. MUST fail.
- [x] 11.8 [core-api] RED: add `test_post_orders_rejects_unknown_type_with_422` — POSTs `{"type": "takeaway"}`; asserts `422`. MUST fail.
- [x] 11.9 [core-api] RED: add `test_post_orders_rejects_negative_points_with_422` — POSTs `{"type": "pickup", "points_to_use": -1}`; asserts `422`. MUST fail.
- [x] 11.10 [core-api] RED: add `test_post_orders_total_zero_returns_paid_status` — patches pricing to total=0; POSTs; asserts `201` with JSON `status == "paid"`. MUST fail.

## 12. RED: HTTP route — GET /api/v1/orders/{order_id}

- [x] 12.1 [core-api] RED: add `test_orders_router_exposes_get_detail` — asserts `get` key in `paths["/api/v1/orders/{order_id}"]` in OpenAPI. MUST fail.
- [x] 12.2 [core-api] RED: add `test_get_order_detail_requires_auth` — GETs `/api/v1/orders/{random UUID}` without token; asserts `401`. MUST fail.
- [x] 12.3 [core-api] RED: add `test_get_order_detail_forbidden_for_staff` — GETs with `_auth("barista")`; asserts `403`. MUST fail.
- [x] 12.4 [core-api] RED: add `test_get_order_detail_returns_own_order` — seeds an Order owned by the authenticated customer; GETs; asserts `200` with body `id`, `status`, `items`, `total`. MUST fail.
- [x] 12.5 [core-api] RED: add `test_get_order_detail_foreign_order_returns_404` — creates an Order owned by user B; customer A GETs it; asserts `404` (do not leak existence). MUST fail.
- [x] 12.6 [core-api] RED: add `test_get_order_detail_unknown_id_returns_404` — GETs `/api/v1/orders/{random UUID}`; asserts `404`. MUST fail.
- [x] 12.7 [core-api] RED: add `test_get_order_detail_includes_confirmation_url_when_set` — seeds an Order + Payment with `confirmation_url="https://yookassa.ru/..."`; GETs; asserts response body `confirmation_url` matches. MUST fail.
- [x] 12.8 [core-api] RED: add `test_get_order_detail_confirmation_url_null_while_worker_pending` — seeds an Order + Payment with `confirmation_url=None`; GETs; asserts response body `confirmation_url is None`. MUST fail.

## 13. RED: RBAC matrix coverage

- [x] 13.1 [core-api] RED: add `test_orders_routes_in_rbac_matrix` in `test_route_orders.py` — imports `ROUTE_MATRIX`; asserts `("POST", "/api/v1/orders") in ROUTE_MATRIX` with value `{"customer"}`, and `("GET", "/api/v1/orders/{order_id}") in ROUTE_MATRIX` with value `{"customer"}`. MUST fail.
- [x] 13.2 [core-api] RED: add `test_route_coverage_passes_for_orders` — calls the existing `_all_registered_routes` / `_is_covered` helpers from `test_route_coverage.py` (or replicates them inline), asserts both orders routes are covered without appearing in `PUBLIC_ROUTES`. MUST fail in RED until both the router is registered AND the matrix entries are added (latter fails first).

## 14. VERIFY (RED)

- [x] 14.1 [core-api] VERIFY: run `docker compose exec core-api pytest services/core-api/tests/test_checkout_service.py services/core-api/tests/test_route_orders.py -v` and confirm every new test FAILS (with `ImportError`, `ModuleNotFoundError`, or `AssertionError`) or is legitimately skipped on SQLite. No test SHALL pass by accident. **Result:** 52 failed, 5 passed. The 5 passing (401/403 auth+role tests) pass via default-deny RBAC middleware — the contract is genuinely enforced and will continue to pass in GREEN. Not "pass by accident".
- [x] 14.2 [core-api] VERIFY: run the full suite `docker compose exec core-api pytest services/core-api/tests/` and confirm all pre-existing tests still pass — the new files MUST NOT regress collection, fixtures, or imports. **Result:** no new regressions introduced by the RED files (pre-existing failures in test_menu_admin / test_route_cart are unrelated — reproduce without the new files present).
