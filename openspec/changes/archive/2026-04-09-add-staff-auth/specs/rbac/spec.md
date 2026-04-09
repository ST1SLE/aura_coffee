## ADDED Requirements

### Requirement: require_role dependency
The system SHALL provide a `require_role(*allowed_roles)` function that returns a FastAPI dependency. This dependency SHALL call `get_current_user` to extract the authenticated user, then check `user.role` against `allowed_roles`. If the role is not in the allowed set, the dependency SHALL raise HTTP 403 with `{detail: "Insufficient permissions"}`. Ref: INV-002, INV-010.

#### Scenario: Authorized role
- **WHEN** a request with a valid JWT whose `role` is in the endpoint's `allowed_roles` list
- **THEN** the dependency resolves successfully and the endpoint executes

#### Scenario: Unauthorized role
- **WHEN** a request with a valid JWT whose `role` is NOT in the endpoint's `allowed_roles` list
- **THEN** the dependency raises HTTP 403 with `{detail: "Insufficient permissions"}`

#### Scenario: No authentication
- **WHEN** a request without an Authorization header reaches a `require_role`-protected endpoint
- **THEN** `get_current_user` raises HTTP 401 before role check occurs

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
