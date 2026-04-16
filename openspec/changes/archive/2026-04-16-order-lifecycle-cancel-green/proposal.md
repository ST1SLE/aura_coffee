## Why

Phase 3 currently has only the order persistence schema. Orders can be created and paid, but once the payment webhook flips them to PAID there is no code path that advances them through PREPARING → READY → IN_DELIVERY → COMPLETED, or that cancels them with full financial rollback. The RED cycle (`order-lifecycle-cancel-red`, archived 2026-04-16) published 84 failing tests over two service modules and one HTTP router that are still unimplemented. GREEN implements exactly those modules so the operational lifecycle of a real order can happen end-to-end.

## What Changes

- Add `core_api.services.order_lifecycle` with `transition_order(order_id, new_status, actor_role, db_session)` and `OrderTransitionError(reason)` per PDD §6.1, including the READY→COMPLETED loyalty accrual side effect (INV-003).
- Add `core_api.services.order_cancel` with `cancel_order(order_id, cancelled_by, reason, db_session)` and `OrderCancelError(reason)` implementing the five-step cancellation chain from PDD §7.6 atomically (INV-004).
- Add `core_api.services.order_notifications` thin module exposing `send_order_notification(order, new_status)` that enqueues an sms-worker task (stub-friendly — tests patch it).
- Add a `core_api.celery_app` module exposing a `celery_app` instance with `.send_task`, usable from `order_cancel` to enqueue the `payment_worker.initiate_refund` task.
- Add `core_api.routers.order_actions` with `PATCH /api/v1/orders/{order_id}/status` and `POST /api/v1/orders/{order_id}/cancel` endpoints; register on `app` in `main.py` with RBAC matrix entries (INV-010).
- Extend `rbac_matrix.ROUTE_MATRIX` to allow BARISTA/COURIER/ADMIN on status and CUSTOMER/ADMIN on cancel; the cancel endpoint performs owner-check for CUSTOMER callers in-handler.
- Map domain errors to HTTP: `reason="order_not_found"` → 404; every other `OrderTransitionError` / `OrderCancelError` reason → 409 JSON body `{"detail": {"reason": "..."}}`.

## Capabilities

### New Capabilities
- `order-lifecycle`: service module that owns the order state machine, role gating, and loyalty accrual at completion.
- `order-cancel`: service module that owns the atomic cancellation chain (promo return, points reversal, refund enqueue, order update, notification).
- `order-actions-api`: HTTP router exposing status-transition and cancel endpoints with role-based access and error mapping.

### Modified Capabilities
- `rbac`: adds two new routes to `ROUTE_MATRIX` — `PATCH /api/v1/orders/{order_id}/status` (barista/courier/admin) and `POST /api/v1/orders/{order_id}/cancel` (customer/admin). No architectural changes.

## Non-Goals

- Does not implement the actual Celery task `payment_worker.initiate_refund` (lives in services/payment-worker, separate change).
- Does not implement the actual SMS body / sms-worker task for order status notifications — `send_order_notification` is intentionally a thin pass-through; its concrete implementation ships with Phase 5 notifications work.
- Does not add WebSocket / SSE for live order-status updates — polling via `GET /orders/{id}` is sufficient for MVP.
- Does not touch the YuKassa webhook (CREATED→PAID transition is already handled by the payment-worker webhook-handler change from Phase 3).

## MVP Phase

Phase 3 — Order & Payment (PDD §7.1). Part of the lifecycle/cancel vertical: follows the schema-only slice (`2026-04-16-phase3-schema-green`) and unlocks Phase 4 Delivery + Phase 5 Loyalty downstream.

## Impact

- Code added: `services/core-api/src/core_api/services/order_lifecycle.py`, `services/core-api/src/core_api/services/order_cancel.py`, `services/core-api/src/core_api/services/order_notifications.py`, `services/core-api/src/core_api/celery_app.py`, `services/core-api/src/core_api/routers/order_actions.py`.
- Code modified: `services/core-api/src/core_api/main.py` (router registration), `services/core-api/src/core_api/rbac_matrix.py` (two new entries).
- Tests turned green: 84 new tests from the RED cycle in `test_order_lifecycle.py`, `test_order_cancel.py`, `test_route_order_actions.py`.
- Runtime dependencies: relies on existing Celery/Redis infrastructure (no new packages). `send_task` uses the existing broker URL.
- Invariants upheld: INV-003 (loyalty from money only), INV-004 (atomic financials), INV-005 (customer cancel only if PAID), INV-010 (role isolation), INV-016 (exhaustive state machine).
