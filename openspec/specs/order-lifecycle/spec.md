# order-lifecycle Specification

## Purpose
TBD - created by archiving change order-lifecycle-cancel-green. Update Purpose after archive.
## Requirements
### Requirement: transition_order service function
The system SHALL provide `core_api.services.order_lifecycle.transition_order(order_id, new_status, actor_role, db_session)` that applies a single state transition on an `Order` row. The function MUST enforce the PDD §6.1 state machine as an allow-list and MUST raise `OrderTransitionError(reason)` with a short machine-readable reason string for any rejected call. Ref: PDD §6.1, INV-016.

#### Scenario: Allowed transition with allowed role
- **WHEN** `transition_order(order_id, OrderStatus.PREPARING, "barista", db)` is called on an order whose current status is `PAID`
- **THEN** `order.status` equals `PREPARING` after the call AND the function returns the updated order

#### Scenario: Forbidden transition (not in allow-list)
- **WHEN** `transition_order(order_id, OrderStatus.COMPLETED, "admin", db)` is called on an order whose current status is `PAID` (PAID→COMPLETED is not listed in §6.1)
- **THEN** the function raises `OrderTransitionError(reason="forbidden_transition")` AND `order.status` is unchanged

#### Scenario: Allowed transition but disallowed role
- **WHEN** `transition_order(order_id, OrderStatus.PREPARING, "customer", db)` is called on a PAID order
- **THEN** the function raises `OrderTransitionError(reason="role_not_allowed")` AND `order.status` is unchanged

#### Scenario: Allowed transition, correct role, wrong order type
- **WHEN** `transition_order(order_id, OrderStatus.IN_DELIVERY, "courier", db)` is called on a READY order whose `type == PICKUP`
- **THEN** the function raises `OrderTransitionError(reason="wrong_order_type_for_transition")` AND `order.status` is unchanged

#### Scenario: Unknown order id
- **WHEN** `transition_order(unknown_uuid, OrderStatus.PREPARING, "admin", db)` is called with an id that has no row
- **THEN** the function raises `OrderTransitionError(reason="order_not_found")`

### Requirement: Loyalty accrual at COMPLETED
When and only when the transition results in `OrderStatus.COMPLETED`, the system SHALL accrue loyalty points computed as `floor((order.total - order.delivery_fee) * shop_settings.loyalty_percent / 100)`, record a `LoyaltyTransaction(type=ACCRUAL)` row for the order's user, and increment the user's `LoyaltyAccount.balance`. Ref: PDD §6.1, INV-003.

#### Scenario: Pickup completion accrues from goods total
- **WHEN** READY→COMPLETED fires on a pickup order with `total=12345`, `delivery_fee=0`, and `loyalty_percent=5`
- **THEN** exactly one `LoyaltyTransaction(type=ACCRUAL, amount=617)` row exists for the user AND `LoyaltyAccount.balance` increased by `617`

#### Scenario: Delivery completion excludes delivery fee
- **WHEN** IN_DELIVERY→COMPLETED fires on an order with `total=100000`, `delivery_fee=15000`, and `loyalty_percent=10`
- **THEN** the accrual row has `amount=8500`

#### Scenario: Zero-goods-total completion accrues nothing
- **WHEN** the transition fires on an order where `total == delivery_fee` (goods total is zero)
- **THEN** the user's loyalty-account balance delta is exactly zero

### Requirement: Notification side effect
Every successful status transition SHALL call `send_order_notification(order, new_status)` exactly once. Ref: PDD §6.1.

#### Scenario: Notification fires on successful transition
- **WHEN** a successful transition completes
- **THEN** `core_api.services.order_notifications.send_order_notification` was invoked exactly once with the updated order and the new status

