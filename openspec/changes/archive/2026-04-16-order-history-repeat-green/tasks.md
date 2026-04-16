## 1. GREEN — DTOs

- [x] 1.1 [core-api] GREEN: Create `services/core-api/src/core_api/schemas/order_history.py` with Pydantic v2 models `OrderItemResponse`, `OrderResponse`, `OrderListResponse`, `RepeatOrderSkippedEntry`, `RepeatOrderResult`. `OrderResponse` and `OrderItemResponse` SHALL use `model_config = ConfigDict(from_attributes=True)`. `RepeatOrderSkippedEntry.reason` SHALL be `Literal["menu_item_unavailable", "menu_item_archived", "menu_item_deleted", "size_unavailable", "modifier_unavailable"]`. `RepeatOrderResult.model_fields` SHALL equal exactly `{"added_to_cart", "skipped"}`.

## 2. GREEN — `list_orders` service

- [x] 2.1 [core-api] GREEN: Create `services/core-api/src/core_api/services/order_history.py` with `list_orders(user_id, page=1, per_page=20, db_session) -> OrderListResponse`. Use `select(Order).where(Order.user_id == user_id).options(selectinload(Order.items)).order_by(Order.created_at.desc()).offset((page-1)*per_page).limit(per_page)` and a separate `select(func.count()).select_from(Order).where(Order.user_id == user_id)` for `total_count`. Build `OrderListResponse.model_validate` from scalar rows.

## 3. GREEN — `repeat_order` service

- [x] 3.1 [core-api] GREEN: Create `services/core-api/src/core_api/services/order_repeat.py` exporting `OrderNotFoundError`, `NoItemsAvailableError`, and `repeat_order(order_id, user_id, redis, db_session) -> RepeatOrderResult`.
- [x] 3.2 [core-api] GREEN: Implement ownership check — load `Order.items` eagerly; if absent or `order.user_id != user_id`, raise `OrderNotFoundError`.
- [x] 3.3 [core-api] GREEN: Implement per-item resolution exactly per PDD §7.7 (deleted / archived / stop-listed → entire skip; size unavailable → entire skip; modifier unavailable → drop-only with notification; survivor → `CartService.add_item(CartItemCreate(...))` with NO price fields and `quantity=order_item.quantity`).
- [x] 3.4 [core-api] GREEN: `modifiers_snapshot` parse rule — per entry: if `isinstance(entry, dict)` use `entry["id"]`; else `int(entry)`. Unknown shapes raise `ValueError`.
- [x] 3.5 [core-api] GREEN: Emit `RepeatOrderSkippedEntry` with the EXACT PDD `message_ru` strings asserted by RED tests 3.4–3.8.
- [x] 3.6 [core-api] GREEN: If `added_to_cart == 0`, raise `NoItemsAvailableError("Ни одна позиция из этого заказа сейчас недоступна")` BEFORE returning — `CartService.add_item` MUST NOT be called when the final accepted count is 0 (the test expects zero calls when every item is unavailable; but once any survivor would be added, the "add_item" call happens — RED test asserts 0 calls only in the all-unavailable scenario).
- [x] 3.7 [core-api] GREEN: Instantiate CartService as `CartService(session=db_session, redis_client=redis, user_id=user_id, ttl_seconds=settings.cart_ttl_seconds)`. Import `get_settings()` lazily inside the function if needed to avoid circular imports.

## 4. GREEN — Router + wiring

- [x] 4.1 [core-api] GREEN: Create `services/core-api/src/core_api/routers/order_history.py` with `router = APIRouter(prefix="/api/v1/orders", tags=["orders-history"])`. Declare `GET ""` returning `OrderListResponse` (query params `page: int = Query(1, ge=1)`, `per_page: int = Query(20, ge=1, le=50)`) and `POST "/{order_id}/repeat"` returning `RepeatOrderResult`. Both endpoints SHALL depend on `get_current_user` and on `get_db` + `get_redis` as usual.
- [x] 4.2 [core-api] GREEN: In the POST handler, `try/except OrderNotFoundError → raise HTTPException(404, detail="order_not_found")` and `except NoItemsAvailableError as e → raise HTTPException(422, detail=str(e))`.
- [x] 4.3 [core-api] GREEN: Register the router in `services/core-api/src/core_api/main.py` via `app.include_router(order_history.router)` alongside the existing routers.
- [x] 4.4 [core-api] GREEN: Add to `services/core-api/src/core_api/rbac_matrix.py`:
  - `("GET", "/api/v1/orders"): {"customer"}`
  - `("POST", "/api/v1/orders/{order_id}/repeat"): {"customer"}`

## 5. GREEN — XFAIL handling for single-order-detail test

- [x] 5.1 [core-api] GREEN: Mark `test_single_order_detail_is_not_duplicated` in `services/core-api/tests/test_route_order_history.py` with `@pytest.mark.xfail(strict=True, reason="GET /api/v1/orders/{order_id} is owned by feat/order-checkout; this worktree does not register that route. XFAIL clears at merge time.")`. This is the ONLY test mutation in GREEN.

## 6. REFACTOR

- [x] 6.1 [core-api] REFACTOR: Add type hints and short module docstrings in the new files. No comment noise — the comments SHALL only explain non-obvious logic (e.g., `modifiers_snapshot` dual-shape parsing; XFAIL rationale inline as a one-line note referencing the order-checkout feature).

## 7. VERIFY

- [x] 7.1 [core-api] VERIFY: Run the three new test files together:
  ```
  docker compose exec core-api pytest \
    services/core-api/tests/test_order_history_service.py \
    services/core-api/tests/test_order_repeat_service.py \
    services/core-api/tests/test_route_order_history.py \
    -v
  ```
  Confirm: all 30 previously-red tests now PASS, and `test_single_order_detail_is_not_duplicated` is reported as XFAIL (expected failure). Record the pass count in the apply log.
- [x] 7.2 [core-api] VERIFY: Run the repo-wide suite (outside the three new files) to confirm no regressions: `docker compose exec core-api pytest services/core-api/tests/ --ignore services/core-api/tests/test_order_history_service.py --ignore services/core-api/tests/test_order_repeat_service.py --ignore services/core-api/tests/test_route_order_history.py -q`. Accept pre-existing failures documented in the RED VERIFY log; do NOT fix those — out of scope.
