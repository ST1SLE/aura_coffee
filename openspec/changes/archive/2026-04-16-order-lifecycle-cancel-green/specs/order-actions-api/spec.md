## ADDED Requirements

### Requirement: Status-transition HTTP endpoint
The system SHALL expose `PATCH /api/v1/orders/{order_id}/status` accepting `{"new_status": <OrderStatus>}` and returning the updated order as `OrderResponse`. The endpoint SHALL be registered on the FastAPI app and MUST route to `order_lifecycle.transition_order` under the hood, passing the caller's JWT role as `actor_role`. Ref: PDD §6.1, INV-002, INV-010.

#### Scenario: Unauthenticated request
- **WHEN** a PATCH request is sent without an Authorization header
- **THEN** the response status is 401

#### Scenario: Customer role is rejected
- **WHEN** a PATCH request with a `customer`-role JWT hits the endpoint
- **THEN** the response status is 403

#### Scenario: Barista performs an allowed transition
- **WHEN** a PATCH request with a `barista`-role JWT sends `{"new_status": "preparing"}` and the service stub returns a fake order
- **THEN** the response status is 200 AND the service stub received `actor_role="barista"` and `new_status=OrderStatus.PREPARING`

#### Scenario: Invalid status string is rejected by schema
- **WHEN** the request body is `{"new_status": "not-a-status"}`
- **THEN** the response status is 422 AND the service stub was not invoked

#### Scenario: Service forbidden-transition maps to 409
- **WHEN** the service raises `OrderTransitionError(reason="forbidden_transition")`
- **THEN** the response status is 409 AND the JSON body contains `"forbidden_transition"`

#### Scenario: Service order-not-found maps to 404
- **WHEN** the service raises `OrderTransitionError(reason="order_not_found")`
- **THEN** the response status is 404

### Requirement: Cancel HTTP endpoint
The system SHALL expose `POST /api/v1/orders/{order_id}/cancel` accepting `{"reason": <str|null>}` and returning the cancelled order as `OrderResponse`. The endpoint SHALL route to `order_cancel.cancel_order` with `cancelled_by` equal to the caller's JWT role. Only `customer` and `admin` roles MAY access the endpoint (RBAC); additionally, `customer` callers MUST only be permitted to cancel their own orders. Ref: PDD §7.6, INV-005, INV-010.

#### Scenario: Customer cancels own order
- **WHEN** a POST with a `customer`-role JWT whose `sub` matches the order's owner is sent and the service stub returns a fake cancelled order
- **THEN** the response status is 200 AND the service stub received `cancelled_by="customer"`

#### Scenario: Customer cannot cancel another customer's order
- **WHEN** a POST with a `customer`-role JWT whose `sub` does NOT match the order's owner is sent
- **THEN** the response status is 403 AND the service stub was not invoked

#### Scenario: Admin can cancel any order
- **WHEN** a POST with an `admin`-role JWT targets any order
- **THEN** the response status is 200 AND the service stub received `cancelled_by="admin"`

#### Scenario: Barista and courier are rejected at RBAC layer
- **WHEN** a POST with a `barista` or `courier` JWT is sent
- **THEN** the response status is 403

#### Scenario: Service cancel-error maps to 409
- **WHEN** the service raises `OrderCancelError(reason="customer_cannot_cancel_in_this_status")`
- **THEN** the response status is 409 AND the JSON body contains the reason string

#### Scenario: Service order-not-found maps to 404
- **WHEN** the service raises `OrderCancelError(reason="order_not_found")`
- **THEN** the response status is 404
