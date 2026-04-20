# order-cancel Specification

## Purpose
TBD - created by archiving change order-lifecycle-cancel-green. Update Purpose after archive.
## Requirements
### Requirement: cancel_order service function
The system SHALL provide `core_api.services.order_cancel.cancel_order(order_id, cancelled_by, reason, db_session)` that executes the full cancellation chain atomically per PDD §7.6 and raises `OrderCancelError(reason)` on any rejection. The function MUST perform every step within a single DB transaction boundary; if any step raises, the session MUST be rolled back and no partial effect MUST be observable. Ref: PDD §7.6, INV-004, INV-005.

#### Scenario: Customer cancels own PAID order with full side effects
- **WHEN** `cancel_order(order_id, "customer", None, db)` is called on a PAID order with `promocode_id`, `points_used=200`, `payment.amount=50000`
- **THEN** `promocode.current_uses` is decremented by 1 AND the matching `promocode_usages` row is deleted AND one new `LoyaltyTransaction(type=REVERSAL, amount=200)` row exists AND `LoyaltyAccount.balance` increased by 200 AND `celery_app.send_task` was called once with `("payment_worker.initiate_refund", args=[str(payment.id), 50000])` AND `order.status == CANCELLED`, `cancelled_by == "customer"`, `cancelled_at` is set AND `send_order_notification` was called once

#### Scenario: Admin cancels PREPARING order
- **WHEN** `cancel_order(order_id, "admin", "some reason", db)` is called on a PREPARING order
- **THEN** the full chain completes AND `cancelled_by == "admin"` AND the reason is propagated to the notification call

#### Scenario: Customer cannot cancel non-PAID order
- **WHEN** `cancel_order(order_id, "customer", None, db)` is called on an order whose status is not `PAID`
- **THEN** the function raises `OrderCancelError(reason="customer_cannot_cancel_in_this_status")` AND no DB row is modified

#### Scenario: Admin cannot cancel terminal or in-delivery order
- **WHEN** `cancel_order(order_id, "admin", ..., db)` is called on an order whose status is `IN_DELIVERY`, `COMPLETED`, or `CANCELLED`
- **THEN** the function raises `OrderCancelError(reason="not_cancellable_in_this_status")`

#### Scenario: Unknown order id
- **WHEN** `cancel_order(unknown_uuid, ..., db)` is called
- **THEN** the function raises `OrderCancelError(reason="order_not_found")`

### Requirement: Optional steps skipped when inputs are absent
The cancellation chain SHALL skip the promocode return step when `order.promocode_id` is null, skip the points reversal step when `order.points_used == 0`, and skip the refund task enqueue when `payment.amount == 0`. All other steps MUST still run. Ref: PDD §7.6.

#### Scenario: Order without promocode
- **WHEN** cancel fires on an order where `promocode_id is None`
- **THEN** no `promocode` or `promocode_usages` row is modified AND the rest of the chain runs

#### Scenario: Order with zero points used
- **WHEN** cancel fires on an order where `points_used == 0`
- **THEN** no new `LoyaltyTransaction(type=REVERSAL)` row is created AND `LoyaltyAccount.balance` is unchanged

#### Scenario: Order with zero payment amount
- **WHEN** cancel fires on an order whose payment has `amount == 0` (e.g., full-points pickup)
- **THEN** `celery_app.send_task` is not called AND every other step still happens

### Requirement: Atomicity — mid-chain failure rolls back every artefact
If any step in the cancellation chain raises, the system MUST roll back so that `order`, `promocode`, `promocode_usages`, `loyalty_transactions`, and `loyalty_account.balance` observable to any concurrent transaction are identical to their pre-call state, AND no refund task MUST remain enqueued unless every DB-visible write committed. Ref: INV-004.

#### Scenario: Refund enqueue failure rolls back DB
- **WHEN** `celery_app.send_task` raises `RuntimeError` mid-chain
- **THEN** the exception propagates AND re-querying `order`, `promocode.current_uses`, `promocode_usages`, `loyalty_transactions`, and `LoyaltyAccount.balance` yields identical values to pre-call

#### Scenario: Notification failure leaves no enqueued refund
- **WHEN** `send_order_notification` raises and propagates
- **THEN** the DB is rolled back to pre-call state AND `celery_app.send_task` was never invoked

### Requirement: Promocode usage counter SHALL be decremented atomically with a zero floor

`core_api.services.order_cancel._return_promocode` SHALL decrement `promocodes.current_uses` through a single conditional UPDATE whose `WHERE` clause includes the floor predicate `current_uses > 0`. The `SET` clause SHALL be `current_uses = current_uses - 1` (self-reference). Concurrent double-cancel attempts SHALL NOT drive `current_uses` below zero: the second attempt's UPDATE SHALL match zero rows and SHALL be a no-op on the counter.

#### Scenario: Double-cancel race — second decrement is a floored no-op
- **GIVEN** a promocode `P` with `current_uses=1` and an order `O` that redeemed `P`
- **AND** `_return_promocode(O, db)` has already been invoked once (current_uses decremented to `0`, PromocodeUsage row removed)
- **WHEN** `_return_promocode(O, db)` is invoked a second time (simulating a stale admin-path retry)
- **THEN** the conditional UPDATE SHALL match zero rows
- **AND** `P.current_uses` SHALL remain `0` — NEVER `-1`

#### Scenario: Normal cancel path decrements once
- **GIVEN** a promocode `P` with `current_uses=3` and an order `O` that redeemed `P`
- **WHEN** `_return_promocode(O, db)` is invoked
- **THEN** the conditional UPDATE SHALL match exactly one row
- **AND** `P.current_uses` SHALL be `2` after commit
- **AND** the `PromocodeUsage` row for `O` SHALL be deleted

