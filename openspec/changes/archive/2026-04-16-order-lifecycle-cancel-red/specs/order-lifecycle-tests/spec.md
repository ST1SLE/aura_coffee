## ADDED Requirements

### Requirement: RED suite pins allowed Order Lifecycle transitions (PDD §6.1, INV-016)

The system SHALL provide pytest tests that exercise `core_api.services.order_lifecycle.transition_order(order_id, new_status, actor_role, db_session)` for every PDD §6.1 transition that is OWNED by this router. Each allowed transition SHALL have a dedicated test that:
- Seeds an `Order` in the source status (and with the correct `type` when the transition requires one).
- Calls `transition_order` with the specified `new_status` and an allowed `actor_role`.
- Asserts that the returned `Order.status` equals `new_status`.
- Asserts that `send_order_notification` (monkey-patched on `core_api.services.order_notifications`) was called exactly once with the order and the new status.

The covered allow-list is: `PAID→PREPARING`, `PAID→CANCELLED`, `PREPARING→READY`, `PREPARING→CANCELLED`, `READY→IN_DELIVERY` (requires `type=DELIVERY`), `READY→COMPLETED` (requires `type=PICKUP`), `READY→CANCELLED`, `IN_DELIVERY→COMPLETED`.

#### Scenario: transition_order module does not exist yet
- **WHEN** the test file attempts `from core_api.services.order_lifecycle import transition_order`
- **THEN** the import MUST fail with `ModuleNotFoundError` or `ImportError`, and every test in the module SHALL report that failure (RED state).

#### Scenario: barista moves PAID → PREPARING
- **WHEN** `transition_order` is called with `actor_role="barista"`, source order in `PAID`, and `new_status=OrderStatus.PREPARING`
- **THEN** the order row's `status` SHALL be updated to `PREPARING`
- **AND** the notification mock SHALL be called once with that order and status.

#### Scenario: courier drives READY → IN_DELIVERY only for delivery orders
- **WHEN** `transition_order` is called with `actor_role="courier"`, source order in `READY` with `type=PICKUP`, and `new_status=OrderStatus.IN_DELIVERY`
- **THEN** the call SHALL raise `OrderTransitionError` with `reason="wrong_order_type_for_transition"`
- **AND** no notification SHALL be sent.

### Requirement: RED suite pins forbidden Order Lifecycle transitions (INV-016)

The system SHALL provide a parametrised pytest test over the Cartesian product of `(from_status, to_status)` pairs NOT in the allow-list declared in PDD §6.1. For each forbidden pair the test SHALL assert that `transition_order` raises `OrderTransitionError` with `reason="forbidden_transition"` and that the order row's `status` is unchanged after the raise.

The explicit-forbid list MUST include at minimum: any `COMPLETED → *`, any `CANCELLED → *`, every backward transition (`PREPARING→PAID`, `READY→PREPARING`, `READY→PAID`, `IN_DELIVERY→READY`, `IN_DELIVERY→PAID`, `IN_DELIVERY→PREPARING`), `IN_DELIVERY→CANCELLED`, and both `CREATED→PAID` / `CREATED→CANCELLED` (those are payment-webhook territory and MUST be rejected here per PDD §6.1).

#### Scenario: CREATED → PAID is rejected by the staff router
- **WHEN** `transition_order` is called with any staff `actor_role`, order in `CREATED`, and `new_status=OrderStatus.PAID`
- **THEN** the call SHALL raise `OrderTransitionError(reason="forbidden_transition")`
- **AND** the order row's `status` SHALL remain `CREATED`.

#### Scenario: any transition out of COMPLETED is rejected
- **WHEN** `transition_order` is called with ADMIN role, order in `COMPLETED`, and any non-`COMPLETED` target
- **THEN** the call SHALL raise `OrderTransitionError(reason="forbidden_transition")`.

### Requirement: RED suite pins role gating per INV-010

The system SHALL provide pytest tests asserting that each actor role may drive only the transitions it is authorised for:
- `barista`: PAID→PREPARING, PREPARING→READY, READY→COMPLETED (pickup only).
- `courier`: READY→IN_DELIVERY (delivery only), IN_DELIVERY→COMPLETED.
- `admin`: any transition in the allow-list.
- `customer`: no transitions — every call raises.

#### Scenario: barista cannot drive READY → IN_DELIVERY
- **WHEN** `transition_order` is called with `actor_role="barista"`, order in `READY` (`type=DELIVERY`), and `new_status=OrderStatus.IN_DELIVERY`
- **THEN** the call SHALL raise `OrderTransitionError(reason="role_not_allowed")`.

#### Scenario: customer cannot drive any lifecycle transition
- **WHEN** `transition_order` is called with `actor_role="customer"` and any allow-listed `(from, to)` pair
- **THEN** the call SHALL raise `OrderTransitionError(reason="role_not_allowed")`.

### Requirement: RED suite pins loyalty accrual at COMPLETED (PDD §7.2, INV-003)

The system SHALL provide pytest tests that cover the READY→COMPLETED (pickup) and IN_DELIVERY→COMPLETED (delivery) transitions and assert:
- A new `LoyaltyTransaction` row of `type=ACCRUAL` is inserted for `order.user_id` with `amount = floor((order.total - order.delivery_fee) * shop_settings.loyalty_percent / 100)`.
- `LoyaltyAccount.balance` is incremented by that accrual.
- For an order with `total == delivery_fee` (everything paid for goods was zero), `amount == 0` and no ledger row is created (optional strict form: ledger row with `amount=0` is acceptable — the test asserts balance delta == 0 either way).

#### Scenario: pickup COMPLETED accrues floor of post-delivery-fee total at loyalty_percent
- **GIVEN** `shop_settings.loyalty_percent = 5`, `order.total = 123_45`, `order.delivery_fee = 0`, `order.type=PICKUP`, status=READY
- **WHEN** `transition_order(new_status=COMPLETED, actor_role="barista", ...)` is called
- **THEN** a new `LoyaltyTransaction(type=ACCRUAL, amount=617)` row SHALL be present for the order's user
- **AND** `LoyaltyAccount.balance` SHALL be increased by 617.

#### Scenario: delivery COMPLETED excludes delivery_fee from the accrual base (INV-003)
- **GIVEN** `shop_settings.loyalty_percent = 10`, `order.total = 1_000_00`, `order.delivery_fee = 150_00`, `order.type=DELIVERY`, status=IN_DELIVERY
- **WHEN** `transition_order(new_status=COMPLETED, actor_role="courier", ...)` is called
- **THEN** the inserted `LoyaltyTransaction.amount` SHALL equal `floor((1_000_00 - 150_00) * 10 / 100)` = `8500`.

### Requirement: RED suite pins the §7.6 cancellation chain

The system SHALL provide pytest tests that exercise `core_api.services.order_cancel.cancel_order(order_id, cancelled_by, reason, db_session)` and cover every step of PDD §7.6 in order:

1. Rights check (INV-005): customer may cancel only a `PAID` order; admin may cancel `PAID`, `PREPARING`, `READY` orders; admin MUST NOT cancel `IN_DELIVERY`, `COMPLETED`, `CANCELLED` orders.
2. Promocode return: if the order had a promocode, `promocodes.current_uses` is decremented by 1 and the matching `promocode_usages` row is deleted.
3. Loyalty reversal: if `order.points_used > 0`, a `LoyaltyTransaction(type=REVERSAL, amount=+points_used)` row is inserted and `LoyaltyAccount.balance` is incremented by `points_used`.
4. Refund enqueue: if `payment.amount > 0`, `celery_app.send_task` is called with task name `"payment_worker.initiate_refund"` and args `[str(payment_id), amount]`. If `payment.amount == 0`, the call MUST NOT happen.
5. Order update: `order.status=CANCELLED`, `order.cancelled_by=cancelled_by`, `order.cancelled_at` is a recent timestamp.
6. Notification: `send_order_notification` is called exactly once with the order, new status `CANCELLED`, and the cancellation `reason`.

#### Scenario: cancel_order module does not exist yet
- **WHEN** the test file attempts `from core_api.services.order_cancel import cancel_order`
- **THEN** the import MUST fail (RED state).

#### Scenario: customer cancels a PAID order — full chain fires
- **GIVEN** an order with `status=PAID`, `points_used=200`, `promocode_id` set with a matching usage row, `payment.amount=500_00`
- **WHEN** `cancel_order(order_id, "customer", reason=None, db_session)` is called
- **THEN** `promocode.current_uses` SHALL decrement by 1
- **AND** the `promocode_usages` row for this order SHALL be deleted
- **AND** a `LoyaltyTransaction(type=REVERSAL, amount=+200)` SHALL be inserted
- **AND** `LoyaltyAccount.balance` SHALL increase by 200
- **AND** `celery_app.send_task` SHALL be called once with `"payment_worker.initiate_refund"` and args `[str(payment_id), 50000]`
- **AND** `order.status` SHALL equal `CANCELLED` with `cancelled_by="customer"` and a non-null `cancelled_at`
- **AND** `send_order_notification` SHALL be called once with the cancelled order, `OrderStatus.CANCELLED`, and the propagated reason.

#### Scenario: customer cannot cancel a PREPARING order (INV-005)
- **GIVEN** an order with `status=PREPARING`
- **WHEN** `cancel_order(order_id, "customer", reason=None, db_session)` is called
- **THEN** the call SHALL raise `OrderCancelError(reason="customer_cannot_cancel_in_this_status")`
- **AND** the order row SHALL be untouched.

#### Scenario: admin cannot cancel an IN_DELIVERY order
- **GIVEN** an order with `status=IN_DELIVERY`
- **WHEN** `cancel_order(order_id, "admin", reason="courier issue", db_session)` is called
- **THEN** the call SHALL raise `OrderCancelError(reason="not_cancellable_in_this_status")`.

#### Scenario: zero-total order does not enqueue a refund task
- **GIVEN** a PAID order with `payment.amount == 0` (fully paid by points)
- **WHEN** `cancel_order(order_id, "customer", reason=None, db_session)` is called
- **THEN** `celery_app.send_task` SHALL NOT be called
- **AND** the order SHALL still transition to CANCELLED and the other steps still run.

### Requirement: RED suite pins INV-004 atomicity of the cancellation chain

The system SHALL provide pytest tests that force a failure mid-chain and assert that NO partial state persists:
- Patch `core_api.services.order_cancel.celery_app.send_task` to raise. After the raise, the order SHALL remain in its original status, the promocode MUST NOT be decremented, the `promocode_usages` row MUST still exist, no `REVERSAL` row MUST be inserted, and `LoyaltyAccount.balance` MUST be unchanged.
- Patch `core_api.services.order_cancel.send_order_notification` to raise. After the raise, the same rollback contract holds AND `celery_app.send_task` MUST NOT have been called (the task enqueue happens only on the fully-successful path).

#### Scenario: celery_app.send_task raises mid-chain — no partial state
- **GIVEN** an order that satisfies every cancellation precondition, with a promocode applied and `points_used > 0`
- **WHEN** `celery_app.send_task` is patched to raise `RuntimeError` and `cancel_order` is called
- **THEN** the raise SHALL propagate to the test
- **AND** re-reading the order, promocode, loyalty account, and ledger from the DB SHALL show exactly the pre-call state.

### Requirement: RED suite pins the staff-action HTTP surface

The system SHALL provide pytest tests for the router `core_api.routers.order_actions` covering the following endpoints and behaviours:

- `PATCH /api/v1/orders/{order_id}/status` accepts body `OrderStatusUpdate(new_status)`, returns `200` with an `OrderResponse`-shaped payload on success, `409` for forbidden transitions / role violations inside the service, `404` when the order is not found, `422` for an unknown `new_status`.
- `POST /api/v1/orders/{order_id}/cancel` accepts body `CancelOrderRequest(reason)`, returns `200` with the cancelled order on success, `409` when the service rejects, `404` on missing order.
- Router is registered in `services/core-api/src/core_api/main.py` so both paths appear in `app.router.routes`.
- RBAC matrix rejects every unauthorised role with `403` (enforced by `RBACMiddleware`):
  - `PATCH /api/v1/orders/{order_id}/status` → allowed for `BARISTA`, `COURIER`, `ADMIN`; `CUSTOMER` is rejected with 403.
  - `POST /api/v1/orders/{order_id}/cancel` → allowed for `CUSTOMER`, `ADMIN`; `BARISTA` and `COURIER` are rejected with 403.
- The customer cancel path additionally requires JWT `sub == order.user_id`. A CUSTOMER calling cancel on someone else's order SHALL receive `403`.

#### Scenario: order_actions router does not exist yet
- **WHEN** the test file attempts `from core_api.routers.order_actions import router`
- **THEN** the import MUST fail (RED state).

#### Scenario: main.py registers both staff-action paths
- **WHEN** the test imports `core_api.main.app` and enumerates `app.router.routes`
- **THEN** both `/api/v1/orders/{order_id}/status` and `/api/v1/orders/{order_id}/cancel` SHALL appear with the correct HTTP methods.

#### Scenario: customer is rejected from the status endpoint with 403
- **WHEN** a CUSTOMER bearer token calls `PATCH /api/v1/orders/{order_id}/status` with any valid body
- **THEN** the response status SHALL be `403` (INV-010).

#### Scenario: customer cancelling another user's order gets 403
- **GIVEN** an order owned by user A
- **WHEN** customer user B sends `POST /api/v1/orders/{order_id}/cancel`
- **THEN** the response status SHALL be `403`
- **AND** the cancel service SHALL NOT be called (monkey-patch asserts zero invocations).

#### Scenario: barista driving PAID → PREPARING via HTTP
- **GIVEN** a seeded order in `PAID` and `transition_order` monkey-patched to return a canned updated-order stub
- **WHEN** barista sends `PATCH /api/v1/orders/{order_id}/status` with `{"new_status": "preparing"}`
- **THEN** the response status SHALL be `200`
- **AND** the monkey-patched `transition_order` SHALL be called with `actor_role="barista"` and `new_status=OrderStatus.PREPARING`.
