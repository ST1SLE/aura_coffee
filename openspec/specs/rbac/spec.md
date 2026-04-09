## ADDED Requirements

### Requirement: require_role dependency
The system SHALL provide a `require_role(*allowed_roles)` function that returns a FastAPI dependency. This dependency is an optional secondary guard — primary enforcement is handled by RBAC middleware (see `rbac-middleware` spec). Existing `Depends(require_role(...))` calls in routers are removed. The function remains available in `deps/rbac.py` for edge cases where endpoint logic needs the authenticated user dict with role validation. Ref: INV-002, INV-010.

#### Scenario: Authorized role (via middleware)
- **WHEN** a request with a valid JWT whose `role` is in the route matrix's allowed roles
- **THEN** the request reaches the endpoint handler without requiring `Depends(require_role(...))`

#### Scenario: Unauthorized role (via middleware)
- **WHEN** a request with a valid JWT whose `role` is NOT in the route matrix's allowed roles
- **THEN** the middleware returns HTTP 403 with `{"detail": "Insufficient permissions"}` before the endpoint handler runs

#### Scenario: require_role used as optional secondary guard
- **WHEN** an endpoint uses `Depends(require_role("admin"))` alongside middleware enforcement
- **THEN** the middleware checks role first; the dependency provides the `current_user` dict to the handler

### Requirement: Admin role isolation
Admin role SHALL have access to all staff endpoints. Ref: INV-010.

#### Scenario: Admin accesses admin-only endpoint
- **WHEN** request with JWT `role: "admin"` hits an endpoint protected by `require_role("admin")`
- **THEN** access is granted

#### Scenario: Admin accesses barista endpoint
- **WHEN** request with JWT `role: "admin"` hits an endpoint protected by `require_role("admin", "barista")`
- **THEN** access is granted

### Requirement: Barista role isolation
Barista role MUST NOT access menu management, users, promocodes, or settings. Barista SHALL only access order-related endpoints designated for barista use. Ref: INV-010.

#### Scenario: Barista denied access to admin-only endpoint
- **WHEN** request with JWT `role: "barista"` hits an endpoint protected by `require_role("admin")`
- **THEN** response is HTTP 403

#### Scenario: Barista accesses barista-allowed endpoint
- **WHEN** request with JWT `role: "barista"` hits an endpoint protected by `require_role("admin", "barista")`
- **THEN** access is granted

### Requirement: Courier role isolation
Courier role MUST NOT access anything except delivery order list and delivery status changes. Ref: INV-010.

#### Scenario: Courier denied access to non-delivery endpoint
- **WHEN** request with JWT `role: "courier"` hits an endpoint protected by `require_role("admin")`
- **THEN** response is HTTP 403

#### Scenario: Courier accesses delivery endpoint
- **WHEN** request with JWT `role: "courier"` hits an endpoint protected by `require_role("admin", "courier")`
- **THEN** access is granted

### Requirement: Customer role excluded from staff endpoints
Customer JWTs (role `"customer"`) MUST NOT be accepted by any staff endpoint. Staff endpoints SHALL use `require_role` with only staff roles. Ref: INV-010.

#### Scenario: Customer denied access to staff endpoint
- **WHEN** request with JWT `role: "customer"` hits an endpoint protected by `require_role("admin")`
- **THEN** response is HTTP 403
