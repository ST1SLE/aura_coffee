## 1. Test file — Order Lifecycle state machine

- [x] 1.1 [core-api] RED: create `services/core-api/tests/test_order_lifecycle.py` with a module-level import probe `test_order_lifecycle_module_exists` that does `from core_api.services.order_lifecycle import transition_order, OrderTransitionError` and asserts both names; this MUST fail with `ModuleNotFoundError` until GREEN.
- [x] 1.2 [core-api] RED: add `test_paid_to_preparing_barista_happy_path` — seeds an `Order(status=PAID, type=PICKUP)`, a `LoyaltyAccount` for the user, monkey-patches `core_api.services.order_notifications.send_order_notification` with a `MagicMock`, calls `transition_order(order.id, OrderStatus.PREPARING, "barista", db)`, asserts `order.status == PREPARING`, asserts the notification mock was called exactly once with `(order, OrderStatus.PREPARING)` or equivalent positional signature.
- [x] 1.3 [core-api] RED: add `test_paid_to_cancelled_admin_happy_path` — seeds an `Order(status=PAID)`, calls `transition_order(..., OrderStatus.CANCELLED, "admin", db)`, asserts status transition and notification call (cancellation via the direct transition endpoint is allowed for ADMIN per D7; customers must use cancel endpoint).
- [x] 1.4 [core-api] RED: add `test_preparing_to_ready_barista_happy_path` — same shape, `PREPARING` → `READY` with `actor_role="barista"`.
- [x] 1.5 [core-api] RED: add `test_preparing_to_cancelled_admin_only` — assert ADMIN can do PREPARING→CANCELLED and BARISTA raises `OrderTransitionError(reason="role_not_allowed")`.
- [x] 1.6 [core-api] RED: add `test_ready_to_in_delivery_courier_happy_path` — seeds `Order(status=READY, type=DELIVERY)`, courier moves to IN_DELIVERY, asserts status + notification.
- [x] 1.7 [core-api] RED: add `test_ready_to_in_delivery_rejects_pickup_order` — seeds `Order(status=READY, type=PICKUP)`, courier call to IN_DELIVERY raises `OrderTransitionError(reason="wrong_order_type_for_transition")` and status unchanged.
- [x] 1.8 [core-api] RED: add `test_ready_to_completed_pickup_barista` — seeds `Order(status=READY, type=PICKUP)`, barista moves to COMPLETED, asserts status + notification.
- [x] 1.9 [core-api] RED: add `test_ready_to_completed_rejects_delivery_order` — seeds `Order(status=READY, type=DELIVERY)`, barista call to COMPLETED raises `OrderTransitionError(reason="wrong_order_type_for_transition")`.
- [x] 1.10 [core-api] RED: add `test_ready_to_cancelled_admin_only` — ADMIN allowed, BARISTA and COURIER raise `role_not_allowed`.
- [x] 1.11 [core-api] RED: add `test_in_delivery_to_completed_courier_happy_path` — courier, any order.type.
- [x] 1.12 [core-api] RED: add `test_completed_accrues_loyalty_pickup` — `shop_settings.loyalty_percent=5`, `order.total=12345`, `order.delivery_fee=0`; after READY→COMPLETED, a `LoyaltyTransaction(type=ACCRUAL, amount=617)` row exists for the user, and `LoyaltyAccount.balance` increased by 617.
- [x] 1.13 [core-api] RED: add `test_completed_accrues_loyalty_delivery_excludes_delivery_fee` — `loyalty_percent=10`, `order.total=100000`, `order.delivery_fee=15000`; after IN_DELIVERY→COMPLETED accrual amount is 8500.
- [x] 1.14 [core-api] RED: add `test_completed_zero_goods_total_accrues_nothing` — `order.total == order.delivery_fee` (100% points or free); after transition, the user's loyalty balance delta is exactly 0 (no ACCRUAL row OR a row with amount=0 — test asserts delta only).
- [x] 1.15 [core-api] RED: add parametrised `test_forbidden_transitions_raise` that iterates the Cartesian product of every `(from_status, to_status)` pair NOT in the allow-list from §6.1 (including every `COMPLETED→*`, every `CANCELLED→*`, every backward transition, `IN_DELIVERY→CANCELLED`, and `CREATED→PAID` / `CREATED→CANCELLED`) and asserts `OrderTransitionError(reason="forbidden_transition")` plus status unchanged. Use `pytest.mark.parametrize`.
- [x] 1.16 [core-api] RED: add `test_customer_role_cannot_transition` that iterates the allow-list and asserts every call with `actor_role="customer"` raises `OrderTransitionError(reason="role_not_allowed")`.
- [x] 1.17 [core-api] RED: add `test_order_not_found_raises` — calls `transition_order(uuid4(), OrderStatus.PREPARING, "admin", db)` on a non-existent id, asserts `OrderTransitionError(reason="order_not_found")`.

## 2. Test file — Order Cancellation Chain (§7.6)

- [x] 2.1 [core-api] RED: create `services/core-api/tests/test_order_cancel.py` with a module-level import probe `test_order_cancel_module_exists` that does `from core_api.services.order_cancel import cancel_order, OrderCancelError`; MUST fail with `ModuleNotFoundError` until GREEN.
- [x] 2.2 [core-api] RED: add `test_customer_cancels_paid_order_full_chain` — seeds order with promocode + promocode_usage, `points_used=200`, `payment.amount=50000`, patches `core_api.services.order_cancel.send_order_notification` and `core_api.services.order_cancel.celery_app.send_task`, calls `cancel_order(..., "customer", reason=None)`, asserts: promocode.current_uses decremented by 1, promocode_usages row gone, one new `LoyaltyTransaction(type=REVERSAL, amount=200)`, `LoyaltyAccount.balance += 200`, `celery_app.send_task` called once with `("payment_worker.initiate_refund", args=[str(payment_id), 50000])`, `order.status=CANCELLED`, `cancelled_by="customer"`, `cancelled_at` recent, notification called once with reason propagated.
- [x] 2.3 [core-api] RED: add `test_admin_cancels_preparing_order_full_chain` — same, source status PREPARING, cancelled_by="admin", reason="some reason"; reason flows into the notification call.
- [x] 2.4 [core-api] RED: add `test_admin_cancels_ready_order` — covers the READY source case per §7.6 / §6.1.
- [x] 2.5 [core-api] RED: add `test_customer_cannot_cancel_preparing` — INV-005: status=PREPARING, `cancel_order(..., "customer", ...)` raises `OrderCancelError(reason="customer_cannot_cancel_in_this_status")`, DB untouched.
- [x] 2.6 [core-api] RED: add parametrised `test_customer_cannot_cancel_non_paid_statuses` — iterates CREATED, PREPARING, READY, IN_DELIVERY, COMPLETED, CANCELLED and asserts raise.
- [x] 2.7 [core-api] RED: add parametrised `test_admin_cannot_cancel_terminal_or_in_delivery` — iterates IN_DELIVERY, COMPLETED, CANCELLED and asserts `OrderCancelError(reason="not_cancellable_in_this_status")`.
- [x] 2.8 [core-api] RED: add `test_no_promocode_skips_promo_step` — order without promocode_id, chain still runs, no error, promocode table untouched.
- [x] 2.9 [core-api] RED: add `test_no_points_used_skips_loyalty_step` — `points_used=0`, no new `LoyaltyTransaction(type=REVERSAL)` row, `LoyaltyAccount.balance` unchanged.
- [x] 2.10 [core-api] RED: add `test_zero_payment_amount_skips_refund` — `payment.amount=0` (full-points pickup), `celery_app.send_task` NOT called, every other step still happens.
- [x] 2.11 [core-api] RED: add `test_celery_send_task_failure_rolls_back_everything` — `celery_app.send_task` patched to raise `RuntimeError`; after the raise propagates, re-query all five artefacts (order, promocode, promocode_usages, loyalty_transactions, loyalty_account.balance) and assert pre-call state.
- [x] 2.12 [core-api] RED: add `test_notification_failure_rolls_back_and_no_task_enqueued` — patch notification to raise; asserts same rollback AND `celery_app.send_task` was never called (implies enqueue happens AFTER everything else in GREEN design).
- [x] 2.13 [core-api] RED: add `test_order_not_found_raises_cancel` — non-existent id raises `OrderCancelError(reason="order_not_found")`.

## 3. Test file — HTTP router & RBAC

- [x] 3.1 [core-api] RED: create `services/core-api/tests/test_route_order_actions.py` with an import probe `test_order_actions_router_module_exists` that does `from core_api.routers.order_actions import router`; MUST fail until GREEN.
- [x] 3.2 [core-api] RED: add `test_main_registers_order_actions_router` — imports `core_api.main.app`, collects `app.router.routes`, asserts that both `/api/v1/orders/{order_id}/status` (PATCH) and `/api/v1/orders/{order_id}/cancel` (POST) are present.
- [x] 3.3 [core-api] RED: add `test_status_endpoint_requires_auth` — no Authorization header → 401.
- [x] 3.4 [core-api] RED: add `test_status_endpoint_rejects_customer_with_403` — CUSTOMER bearer → 403 on `PATCH /api/v1/orders/{uuid}/status` with body `{"new_status": "preparing"}`.
- [x] 3.5 [core-api] RED: add `test_status_endpoint_barista_calls_service` — barista bearer, `transition_order` monkey-patched at `core_api.routers.order_actions.transition_order` to return a fake updated order; body `{"new_status": "preparing"}`; assert 200 + the patched function received `actor_role="barista"` and `new_status=OrderStatus.PREPARING`.
- [x] 3.6 [core-api] RED: add `test_status_endpoint_rejects_invalid_new_status_with_422` — body `{"new_status": "not-a-status"}`; returns 422 and the service is not called.
- [x] 3.7 [core-api] RED: add `test_status_endpoint_forwards_transition_error_as_409` — monkey-patched service raises `OrderTransitionError(reason="forbidden_transition")`; HTTP response is 409 with a JSON body containing the reason.
- [x] 3.8 [core-api] RED: add `test_status_endpoint_returns_404_for_not_found` — patched service raises `OrderTransitionError(reason="order_not_found")`; response is 404.
- [x] 3.9 [core-api] RED: add `test_cancel_endpoint_customer_own_order_happy_path` — seeds an order for user A; customer-A JWT; `cancel_order` patched at `core_api.routers.order_actions.cancel_order` returning a fake cancelled order; `POST /api/v1/orders/{id}/cancel` body `{"reason": "changed my mind"}`; assert 200 and `cancelled_by="customer"` passed to the patched function.
- [x] 3.10 [core-api] RED: add `test_cancel_endpoint_customer_foreign_order_403` — order owned by user A; customer-B JWT sends cancel → 403; patched `cancel_order` must NOT be invoked.
- [x] 3.11 [core-api] RED: add `test_cancel_endpoint_admin_allowed` — admin JWT, any order → 200, `cancelled_by="admin"`.
- [x] 3.12 [core-api] RED: add `test_cancel_endpoint_rejects_barista_and_courier_with_403` — parametrised over `barista_headers` / `courier_headers`, returns 403 per INV-010.
- [x] 3.13 [core-api] RED: add `test_cancel_endpoint_forwards_cancel_error_as_409` — patched service raises `OrderCancelError(reason="customer_cannot_cancel_in_this_status")`; response 409 with reason in the body.
- [x] 3.14 [core-api] RED: add `test_cancel_endpoint_returns_404_for_not_found` — patched service raises `OrderCancelError(reason="order_not_found")`; response 404.

## 4. Verify RED

- [x] 4.1 [core-api] VERIFY: run `pytest services/core-api/tests/test_order_lifecycle.py services/core-api/tests/test_order_cancel.py services/core-api/tests/test_route_order_actions.py -v` inside the core-api container and confirm every new test fails (import/attribute errors or assertion failures). Confirm no previously-green test regresses.
