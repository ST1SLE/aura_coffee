## ADDED Requirements

### Requirement: Order-actions RBAC matrix entries
The route matrix in `core_api.rbac_matrix.ROUTE_MATRIX` SHALL include entries for the two new order-actions endpoints so that the RBAC middleware enforces role boundaries before the handler runs. Ref: INV-002, INV-010.

#### Scenario: Status endpoint is matrix-protected
- **WHEN** any caller hits `PATCH /api/v1/orders/{order_id}/status`
- **THEN** the matrix allows only roles `{barista, courier, admin}` and the middleware returns 403 for every other role

#### Scenario: Cancel endpoint is matrix-protected
- **WHEN** any caller hits `POST /api/v1/orders/{order_id}/cancel`
- **THEN** the matrix allows only roles `{customer, admin}` and the middleware returns 403 for `barista` or `courier`
