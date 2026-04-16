## 1. Prerequisites & thin seams

- [x] 1.1 [core-api] PREREQ: create `services/core-api/src/core_api/celery_app.py` exposing a `celery_app` Celery instance bound to `settings.redis_url` (no task registrations needed — only `send_task` is invoked).
- [x] 1.2 [core-api] PREREQ: create `services/core-api/src/core_api/services/order_notifications.py` with `send_order_notification(order, new_status, reason=None)` that calls `celery_app.send_task("sms_worker.order_status_changed", args=[str(order.id), new_status.value, reason])`. Thin — tests monkey-patch it.

## 2. Order lifecycle service (core module)

- [x] 2.1 [core-api] GREEN: create `services/core-api/src/core_api/services/order_lifecycle.py` with `class OrderTransitionError(Exception)` (init takes `reason: str`, stored as `self.reason`), module-level imports of `send_order_notification` from the notifications module → satisfies RED 1.1.
- [x] 2.2 [core-api] GREEN: add `_ALLOWED_TRANSITIONS` set and `_ALLOWED_ROLES` dict per design D1 in the same module → enables 2.3-2.9.
- [x] 2.3 [core-api] GREEN: implement `transition_order(order_id, new_status, actor_role, db_session)` to: fetch the order (raise `reason="order_not_found"` if missing), reject unknown `(from,to)` pairs with `forbidden_transition`, reject disallowed roles with `role_not_allowed` → satisfies RED 1.15, 1.16, 1.17.
- [x] 2.4 [core-api] GREEN: in `transition_order`, apply the order-type guard for `(READY, IN_DELIVERY)` (must be `DELIVERY`) and `(READY, COMPLETED)` (must be `PICKUP`); raise `wrong_order_type_for_transition` and leave status unchanged → satisfies RED 1.7, 1.9.
- [x] 2.5 [core-api] GREEN: in `transition_order`, perform the `order.status = new_status` update and flush the session after all guards pass → satisfies RED 1.2, 1.3, 1.4, 1.6, 1.8, 1.11.
- [x] 2.6 [core-api] GREEN: in `transition_order`, when `new_status == OrderStatus.COMPLETED`, read `shop_settings.loyalty_percent` (fallback 0 if row missing), compute `accrual = (order.total - order.delivery_fee) * percent // 100`, and if `accrual > 0` insert `LoyaltyTransaction(type=ACCRUAL, amount=accrual, balance_after=new_balance)` + increment `LoyaltyAccount.balance` → satisfies RED 1.12, 1.13.
- [x] 2.7 [core-api] GREEN: ensure zero-goods case writes nothing (balance delta exactly 0) → satisfies RED 1.14.
- [x] 2.8 [core-api] GREEN: in `transition_order`, add the role-gate rejection for admin-only cells (PAID→CANCELLED, PREPARING→CANCELLED, READY→CANCELLED) and barista-only/courier-only cells → satisfies RED 1.5, 1.10.
- [x] 2.9 [core-api] GREEN: after every successful transition, call `send_order_notification(order, new_status)` exactly once → satisfies RED 1.2 (notification assertions) and the notification scenario in all happy-path tests.

## 3. Order cancellation service

- [x] 3.1 [core-api] GREEN: create `services/core-api/src/core_api/services/order_cancel.py` with `class OrderCancelError(Exception)` (init takes `reason: str`) and module-level imports of `celery_app`, `send_order_notification` → satisfies RED 2.1.
- [x] 3.2 [core-api] GREEN: implement the rights-check section of `cancel_order(order_id, cancelled_by, reason, db_session)`: load order (raise `order_not_found`); customer-not-PAID → `customer_cannot_cancel_in_this_status`; admin-in-{IN_DELIVERY,COMPLETED,CANCELLED} → `not_cancellable_in_this_status` → satisfies RED 2.5, 2.6, 2.7, 2.13.
- [x] 3.3 [core-api] GREEN: implement the promocode return step — if `order.promocode_id`, `UPDATE promocode SET current_uses = current_uses - 1` and delete the matching `promocode_usages` row → satisfies RED 2.2 (promocode assertions) and 2.8 (skip branch).
- [x] 3.4 [core-api] GREEN: implement the points reversal step — if `order.points_used > 0`, insert `LoyaltyTransaction(type=REVERSAL, amount=order.points_used, balance_after=new_balance)` and increment `LoyaltyAccount.balance` → satisfies RED 2.2 (loyalty assertions) and 2.9 (skip branch).
- [x] 3.5 [core-api] GREEN: implement the order update step — set `order.status=CANCELLED`, `cancelled_by=cancelled_by`, `cancelled_at=datetime.now(UTC)` → satisfies RED 2.2, 2.3, 2.4 (order-state assertions).
- [x] 3.6 [core-api] GREEN: implement the notification step BEFORE `send_task` per design D6 — call `send_order_notification(order, OrderStatus.CANCELLED, reason=reason)`; if it raises, propagate (do not catch) → satisfies RED 2.12.
- [x] 3.7 [core-api] GREEN: implement the refund enqueue step — if `payment.amount > 0`, call `celery_app.send_task("payment_worker.initiate_refund", args=[str(payment.id), payment.amount])`; if it raises, propagate → satisfies RED 2.2 (task assertion), 2.10 (skip branch), 2.11 (rollback).
- [x] 3.8 [core-api] GREEN: finalise the chain by calling `db_session.commit()` after all prior steps succeed, then return the updated order. Wrap the entire chain in the caller's session context — on any raise, the session is rolled back by the caller (no internal try/except) → satisfies RED 2.11, 2.12 atomicity tests.

## 4. HTTP router

- [x] 4.1 [core-api] GREEN: create `services/core-api/src/core_api/routers/order_actions.py` with `router = APIRouter(prefix="/api/v1/orders", tags=["order-actions"])`, module-level imports of `transition_order`, `cancel_order`, and their domain errors → satisfies RED 3.1.
- [x] 4.2 [core-api] GREEN: implement `PATCH /{order_id}/status` handler — accepts `OrderStatusUpdate`, injects `db` via `Depends(get_session)` and claims via the existing JWT dependency, calls `transition_order(order_id, body.new_status, claims.role, db)`, returns `OrderResponse`; map `OrderTransitionError(reason="order_not_found")` to 404 and any other reason to 409 with `{"detail": {"reason": reason}}` → satisfies RED 3.5, 3.6, 3.7, 3.8.
- [x] 4.3 [core-api] GREEN: implement `POST /{order_id}/cancel` handler — accepts `CancelOrderRequest`, injects db + claims, calls `cancel_order(order_id, claims.role, body.reason, db)`, returns `OrderResponse`; for CUSTOMER callers, fetch the order first and return 403 if `order.user_id != claims.sub`; map `OrderCancelError` reasons to 404/409 same as status endpoint → satisfies RED 3.9, 3.10, 3.11, 3.13, 3.14.
- [x] 4.4 [core-api] GREEN: extend `core_api.rbac_matrix.ROUTE_MATRIX` with two new entries: `("PATCH", "/api/v1/orders/{order_id}/status")` → `{BARISTA, COURIER, ADMIN}` and `("POST", "/api/v1/orders/{order_id}/cancel")` → `{CUSTOMER, ADMIN}` → satisfies RED 3.3, 3.4, 3.12.
- [x] 4.5 [core-api] GREEN: register `order_actions.router` in `core_api.main.app` via `app.include_router(order_actions.router)` → satisfies RED 3.2.

## 5. Verify GREEN

- [x] 5.1 [core-api] VERIFY: run `pytest services/core-api/tests/test_order_lifecycle.py services/core-api/tests/test_order_cancel.py services/core-api/tests/test_route_order_actions.py -v` inside the core-api container and confirm every new test passes (or the single `test_status_endpoint_requires_auth` test that already passed in RED remains green).
- [x] 5.2 [core-api] VERIFY: run the full core-api suite and confirm no pre-existing green test regresses versus baseline.
