## 1. PREREQ — Test infrastructure

- [x] 1.1 [core-api] PREREQ: Extend `services/core-api/tests/_factories/orders.py` with `seed_orders_across_statuses(session, *, user, counts)` helper — `counts` is a dict mapping `(OrderStatus, OrderType)` tuples to integer counts. Each row gets a controllable `created_at`/`updated_at`. Returns a dataclass with per-`(status, type)` id buckets. No tests yet — helper is reused by admin-orders test modules.

## 2. RED — list_orders_for_staff service tests

- [x] 2.1 [core-api] RED: Create `services/core-api/tests/test_admin_orders_list.py::test_list_orders_for_staff_symbol_absent` — imports `from core_api.services.order_history import list_orders_for_staff` inside the test body; asserts the symbol is callable. Expected RED: `ImportError`.
- [x] 2.2 [core-api] RED: Add `test_list_orders_for_staff_active_excludes_finalized` — seeds orders in every status (CREATED, PAID, PREPARING, READY, IN_DELIVERY, COMPLETED, CANCELLED) across two users; calls the service with `status_filter="active"`; asserts returned statuses form a subset of {PENDING_PAYMENT, PAID, COOKING, READY} and neither COMPLETED nor CANCELLED appears.
- [x] 2.3 [core-api] RED: Add `test_list_orders_for_staff_explicit_status_filters_exact` — seeds orders across statuses; calls with `status_filter=OrderStatus.PREPARING`; asserts every returned row has `status == PREPARING`.
- [x] 2.4 [core-api] RED: Add `test_list_orders_for_staff_type_filter_combines_with_status` — seeds PREPARING rows with both `PICKUP` and `DELIVERY`; calls with `status_filter=OrderStatus.PREPARING, type_filter=OrderType.DELIVERY`; asserts every row has `status == PREPARING` AND `type == DELIVERY`.
- [x] 2.5 [core-api] RED: Add `test_list_orders_for_staff_active_orders_by_created_at_desc` — seeds three active orders at T1 < T2 < T3 (explicit `created_at`); calls with `status_filter="active"`; asserts the returned id sequence is `[T3, T2, T1]`.
- [x] 2.6 [core-api] RED: Add `test_list_orders_for_staff_finalized_orders_by_updated_at_desc` — seeds three CANCELLED orders with `updated_at` at U1 < U2 < U3 (and `created_at` in reverse order to prove the service uses `updated_at`); calls with `status_filter=OrderStatus.CANCELLED`; asserts the returned id sequence is `[U3, U2, U1]`.
- [x] 2.7 [core-api] RED: Add `test_list_orders_for_staff_pagination_slice_and_total` — seeds 25 active orders; calls with `status_filter="active", page=2, per_page=10`; asserts `total_count == 25` and `orders` is the DESC-rank slice 11..20.
- [x] 2.8 [core-api] RED: Add `test_list_orders_for_staff_sees_all_users` — seeds 2 active orders for user A and 3 for user B; calls with `status_filter="active"`; asserts `total_count == 5` and the set of `user_id` values in the returned rows equals `{A.id, B.id}`.

## 3. RED — get_order_for_staff service tests

- [x] 3.1 [core-api] RED: Add to `services/core-api/tests/test_admin_orders_detail.py::test_get_order_for_staff_symbol_absent` — imports `from core_api.services.order_history import get_order_for_staff` inside the test body; asserts callable. Expected RED: `ImportError`.
- [x] 3.2 [core-api] RED: Add `test_get_order_for_staff_returns_other_users_order` — seeds an order for user B; calls `get_order_for_staff(order_id_of_B, db_session=session)`; asserts the result has `user_id == B.id` and parses into `OrderResponse` from `schemas.order_history`.
- [x] 3.3 [core-api] RED: Add `test_get_order_for_staff_raises_on_unknown_id` — generates a fresh `uuid.uuid4()` that is not seeded; calls the service; asserts a designated "order not found" domain error is raised.

## 4. RED — GET /api/v1/admin/orders router tests

- [x] 4.1 [core-api] RED: Add `test_admin_orders_list_route_not_registered` to `test_admin_orders_list.py` — inspects `app.routes` for a GET matching exactly `/api/v1/admin/orders`; asserts the match count is 1 (GREEN target). Expected RED: count is 0.
- [x] 4.2 [core-api] RED: Add `test_admin_orders_list_requires_authorization` — sends `GET /api/v1/admin/orders` with no Authorization header; asserts status 401 (post-GREEN).
- [x] 4.3 [core-api] RED: Add `test_admin_orders_list_rejects_customer` — sends `GET /api/v1/admin/orders` with `customer_headers`; asserts status 403.
- [x] 4.4 [core-api] RED: Add `test_admin_orders_list_rejects_courier` — sends `GET /api/v1/admin/orders` with `courier_headers`; asserts status 403.
- [x] 4.5 [core-api] RED: Add `test_admin_orders_list_rejects_per_page_over_100` — sends `GET /api/v1/admin/orders?per_page=101` with `admin_headers`; asserts status 422.
- [x] 4.6 [core-api] RED: Add `test_admin_orders_list_defaults_to_active_filter` — seeds a mix of active and finalized orders under two users; sends `GET /api/v1/admin/orders` with `admin_headers`; asserts 200 and every returned `status` is in {CREATED, PAID, PREPARING, READY, IN_DELIVERY}.
- [x] 4.7 [core-api] RED: Add `test_admin_orders_list_type_filter` — seeds active orders with both `type=pickup` and `type=delivery`; sends `GET /api/v1/admin/orders?type=delivery` with `admin_headers`; asserts every returned row has `type == "delivery"`.
- [x] 4.8 [core-api] RED: Add `test_admin_orders_list_barista_same_access_as_admin` — same seed as 4.6; sends the same request with `barista_headers`; asserts 200 and body shape matches the admin response.
- [x] 4.9 [core-api] RED: Add `test_admin_orders_list_sees_multiple_users_orders` — seeds 2 orders for user A and 3 for user B; sends `GET /api/v1/admin/orders` with `admin_headers`; asserts `total_count == 5` and the set of `user_id` strings in `orders[*].user_id` equals `{str(A.id), str(B.id)}`.

## 5. RED — GET /api/v1/admin/orders/{order_id} router tests

- [x] 5.1 [core-api] RED: Add `test_admin_orders_detail_route_not_registered` to `test_admin_orders_detail.py` — inspects `app.routes` for a GET matching `/api/v1/admin/orders/{order_id}`; asserts the match count is 1 (GREEN target). Expected RED: count is 0.
- [x] 5.2 [core-api] RED: Add `test_admin_orders_detail_requires_authorization` — sends `GET /api/v1/admin/orders/<uuid>` with no Authorization header; asserts 401.
- [x] 5.3 [core-api] RED: Add `test_admin_orders_detail_rejects_customer` — sends the same URL with `customer_headers`; asserts 403.
- [x] 5.4 [core-api] RED: Add `test_admin_orders_detail_returns_other_users_order` — seeds an order under user B; sends the request with `admin_headers`; asserts 200 and `response.json()["user_id"] == str(B.id)`.
- [x] 5.5 [core-api] RED: Add `test_admin_orders_detail_barista_sees_other_users_order` — seeds an order under user B; sends the request with `barista_headers`; asserts 200 and `user_id` matches.
- [x] 5.6 [core-api] RED: Add `test_admin_orders_detail_returns_404_on_unknown_id` — sends `GET /api/v1/admin/orders/<random-uuid>` with `admin_headers`; asserts status 404.

## 6. RED — RBAC matrix + route absence tests

- [x] 6.1 [core-api] RED: Create `services/core-api/tests/test_admin_orders_rbac.py::test_admin_orders_list_matrix_row_allows_admin_and_barista_only` — asserts `ROUTE_MATRIX[("GET", "/api/v1/admin/orders")] == {ADMIN, BARISTA}`. Expected RED: `KeyError` (row absent).
- [x] 6.2 [core-api] RED: Add `test_admin_orders_detail_matrix_row_allows_admin_and_barista_only` — asserts `ROUTE_MATRIX[("GET", "/api/v1/admin/orders/{order_id}")] == {ADMIN, BARISTA}`.
- [x] 6.3 [core-api] RED: Add `test_admin_orders_routes_not_public` — asserts neither `("GET", "/api/v1/admin/orders")` nor `("GET", "/api/v1/admin/orders/{order_id}")` is in `PUBLIC_ROUTES`.
- [x] 6.4 [core-api] RED: Add `test_existing_customer_list_orders_signature_has_user_id` — introspects `inspect.signature(list_orders)`; asserts a `user_id` parameter is present to guarantee the customer-scoped function is not renamed or refactored away.
- [x] 6.5 [core-api] RED: Add `test_existing_customer_order_detail_row_untouched` — asserts `CUSTOMER in ROUTE_MATRIX[("GET", "/api/v1/orders/{order_id}")]` remains true; guards against accidental edits to the customer-scoped detail route during GREEN.

## 7. VERIFY — RED suite is RED

- [x] 7.1 [core-api] VERIFY: Run `docker compose exec core-api pytest services/core-api/tests/test_admin_orders_list.py services/core-api/tests/test_admin_orders_detail.py services/core-api/tests/test_admin_orders_rbac.py -v` and confirm every new test fails (mix of `ImportError`, `KeyError`, assertion, or 403/404) while every pre-existing test in the suite still passes. Record the failing test count in the apply log.
