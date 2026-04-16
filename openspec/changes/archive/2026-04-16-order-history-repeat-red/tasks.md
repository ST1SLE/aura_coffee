## 1. PREREQ — Test infrastructure

- [x] 1.1 [core-api] PREREQ: Add `seed_history_order` helper in `services/core-api/tests/_factories/orders.py` — creates a `User`, a `MenuItem`/`SizeOption`/`Modifier` graph, and one `Order` + `OrderItem` rows via passed `db_session`. Helper accepts flags to toggle availability / archived / deleted for each item, and a `price_delta` to ensure current menu prices differ from the snapshot. Returns a dataclass carrying all ids.
- [x] 1.2 [core-api] PREREQ: Add `_make_jwt_for_user(user_id, role="customer")` helper next to existing `_make_jwt` in `tests/conftest.py` (or in a new `tests/_helpers/jwt.py`) so tests can assert per-user isolation by using a deterministic `sub`.

## 2. RED — Order history service tests

- [x] 2.1 [core-api] RED: Create `services/core-api/tests/test_order_history_service.py::test_list_orders_module_missing` — imports `from core_api.services.order_history import list_orders` inside the test body; asserts the symbol exists and is callable. Expected RED: `ModuleNotFoundError`.
- [x] 2.2 [core-api] RED: Add `test_list_orders_empty_user_returns_zero_total` — seeds a user with no orders, calls `list_orders(user_id, db_session=session)`, asserts the result has `orders == []`, `total_count == 0`, `page == 1`, `per_page == 20`.
- [x] 2.3 [core-api] RED: Add `test_list_orders_sorts_desc_by_created_at` — seeds 3 orders at T1<T2<T3 for one user, asserts returned ids are `[T3, T2, T1]`.
- [x] 2.4 [core-api] RED: Add `test_list_orders_pagination_slice_and_total` — seeds 25 orders, calls `list_orders(..., page=2, per_page=10)`, asserts `total_count == 25` and the returned slice is the DESC-ranked 11..20.
- [x] 2.5 [core-api] RED: Add `test_list_orders_does_not_leak_across_users` — seeds user A with 3 orders and user B with 2, calls with A's id, asserts `total_count == 3` and every row has `user_id == A.id`.
- [x] 2.6 [core-api] RED: Add `test_list_orders_eagerly_loads_items` — using SQLAlchemy query-count tracking (e.g. `sqlalchemy.event.listens_for(engine, "before_cursor_execute")` counter), asserts that traversing `order.items` on every returned row does NOT fire additional `SELECT … FROM order_items` queries beyond the eager load.

## 3. RED — Order repeat service tests

- [x] 3.1 [core-api] RED: Create `services/core-api/tests/test_order_repeat_service.py::test_repeat_order_module_missing` — imports `from core_api.services.order_repeat import repeat_order`; asserts symbol exists. Expected RED: `ModuleNotFoundError`.
- [x] 3.2 [core-api] RED: Add `test_repeat_happy_path_adds_all_items_with_current_prices` — seeds a historical order where current menu prices were bumped after the order; monkeypatches `CartService.add_item` with a call-recorder; asserts `add_item` was called N times with `CartItemCreate` instances (no price fields), and `RepeatOrderResult.added_to_cart == N`, `skipped == []`.
- [x] 3.3 [core-api] RED: Add `test_repeat_rejects_other_users_order` — calls `repeat_order(order_id_of_B, user_id=A, ...)`; asserts the service raises a designated not-found/forbidden domain error AND `CartService.add_item` was NEVER called.
- [x] 3.4 [core-api] RED: Add `test_repeat_skips_stop_listed_item` — one of the order items maps to a `MenuItem` with `available=False`; asserts that specific item is not added, `skipped` contains an entry with `reason == "menu_item_unavailable"` and `message_ru == f"{menu_item.name_ru} сейчас недоступен"`.
- [x] 3.5 [core-api] RED: Add `test_repeat_skips_archived_item` — menu item has `archived=True`; asserts `skipped` entry `reason == "menu_item_archived"`, `message_ru == f"{menu_item.name_ru} больше не в меню"`.
- [x] 3.6 [core-api] RED: Add `test_repeat_skips_deleted_item` — `order_item.menu_item_id` points to a non-existent row; asserts `skipped` entry `reason == "menu_item_deleted"`, `message_ru == "Позиция больше не в меню"`.
- [x] 3.7 [core-api] RED: Add `test_repeat_size_unavailable_skips_entire_item` — menu item available but its `SizeOption.available == False`; asserts the item is NOT added (entire item skipped) and `skipped` entry `reason == "size_unavailable"`, `message_ru == f"Размер {order_item.size_label} для {menu_item.name_ru} недоступен"`.
- [x] 3.8 [core-api] RED: Add `test_repeat_modifier_unavailable_keeps_item` — item has two modifiers in snapshot, one unavailable; asserts the item IS added with only the available modifier id, AND `skipped` contains one `reason == "modifier_unavailable"` entry.
- [x] 3.9 [core-api] RED: Add `test_repeat_all_items_unavailable_raises` — every item skipped; asserts the service raises a domain error whose message equals `"Ни одна позиция из этого заказа сейчас недоступна"`, and `CartService.add_item` was NEVER called.
- [x] 3.10 [core-api] RED: Add `test_repeat_does_not_create_new_order_row` — wraps the call in a `SELECT count(*) FROM orders` before/after check; asserts count is unchanged whether the call succeeded or raised.
- [x] 3.11 [core-api] RED: Add `test_repeat_result_shape` — asserts `RepeatOrderResult` carries exactly the fields `added_to_cart: int` and `skipped: list[...]` (pydantic model_fields introspection or dataclass `fields()`), no extra fields.

## 4. RED — Router tests

- [x] 4.1 [core-api] RED: Create `services/core-api/tests/test_route_order_history.py::test_get_orders_route_not_registered` — inspects `app.routes` for a GET matching `/api/v1/orders`; asserts it is absent (fails once route lands in GREEN).
- [x] 4.2 [core-api] RED: Add `test_get_orders_requires_authorization` — sends `GET /api/v1/orders` with no Authorization header; asserts status 401. Expected RED: 404 (route missing) until GREEN.
- [x] 4.3 [core-api] RED: Add `test_get_orders_forbids_non_customer_role` — sends `GET /api/v1/orders` with `barista_headers`; asserts 403.
- [x] 4.4 [core-api] RED: Add `test_get_orders_rejects_per_page_over_50` — sends `GET /api/v1/orders?per_page=51` with customer JWT; asserts 422.
- [x] 4.5 [core-api] RED: Add `test_get_orders_returns_only_own_orders` — seeds orders for users A and B, sends request as A; asserts every returned `order.user_id == A.id` and `total_count` matches A's count.
- [x] 4.6 [core-api] RED: Add `test_get_orders_empty_returns_200_with_empty_list` — authenticated customer with no orders; asserts status 200 and body `{"orders": [], "total_count": 0, "page": 1, "per_page": 20}`.
- [x] 4.7 [core-api] RED: Add `test_post_repeat_route_not_registered` — inspects `app.routes` for POST matching `/api/v1/orders/{order_id}/repeat`; asserts absent.
- [x] 4.8 [core-api] RED: Add `test_post_repeat_requires_authorization` — sends POST with no auth; asserts 401 (post-GREEN expectation).
- [x] 4.9 [core-api] RED: Add `test_post_repeat_forbids_non_customer_role` — sends POST with `barista_headers`; asserts 403.
- [x] 4.10 [core-api] RED: Add `test_post_repeat_returns_404_for_other_users_order` — seeds order owned by B, sends POST as A; asserts 404 with `detail == "order_not_found"`.
- [x] 4.11 [core-api] RED: Add `test_post_repeat_success_populates_cart_and_returns_200` — owned order, all items available; asserts status 200, body parses into `RepeatOrderResult` with `added_to_cart >= 1`, AND the Redis key `cart:{user_id}` contains N items.
- [x] 4.12 [core-api] RED: Add `test_post_repeat_all_unavailable_returns_422` — owned order, every item unavailable; asserts status 422 and `response.json()["detail"] == "Ни одна позиция из этого заказа сейчас недоступна"`.
- [x] 4.13 [core-api] RED: Add `test_post_repeat_does_not_auto_checkout` — successful repeat; asserts `SELECT count(*) FROM orders` is unchanged and `SELECT count(*) FROM payments` is unchanged.
- [x] 4.14 [core-api] RED: Add `test_single_order_detail_is_not_duplicated` — collects routes matching GET `/api/v1/orders/{order_id}`; asserts exactly one such route exists (the one already registered by the order-checkout feature). Fails if the GREEN phase accidentally duplicates it.

## 5. VERIFY — RED suite is RED

- [x] 5.1 [core-api] VERIFY: Run `docker compose exec core-api pytest services/core-api/tests/test_order_history_service.py services/core-api/tests/test_order_repeat_service.py services/core-api/tests/test_route_order_history.py -v` and confirm ALL new tests fail (mix of `ModuleNotFoundError`, assertion, or 404) while every pre-existing test in the suite still passes. Record the failing test count in the apply log.
