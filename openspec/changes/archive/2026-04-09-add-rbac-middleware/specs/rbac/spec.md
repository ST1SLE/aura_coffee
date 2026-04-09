## MODIFIED Requirements

### Requirement: require_role dependency
Previously: `require_role` was the primary enforcement mechanism for role-based access control, applied per-endpoint via `Depends(require_role(...))`.
Now: `require_role` is demoted to an optional secondary guard. Primary enforcement is handled by RBAC middleware (see `rbac-middleware` spec). Existing `Depends(require_role(...))` calls in routers SHALL be removed. The `require_role` function SHALL remain available in `deps/rbac.py` for edge cases where endpoint logic needs the authenticated user dict with role validation. Ref: INV-002, INV-010.

#### Scenario: Authorized role (via middleware)
- **WHEN** a request with a valid JWT whose `role` is in the route matrix's allowed roles
- **THEN** the request reaches the endpoint handler without requiring `Depends(require_role(...))`

#### Scenario: Unauthorized role (via middleware)
- **WHEN** a request with a valid JWT whose `role` is NOT in the route matrix's allowed roles
- **THEN** the middleware returns HTTP 403 with `{"detail": "Insufficient permissions"}` before the endpoint handler runs

#### Scenario: require_role used as optional secondary guard
- **WHEN** an endpoint uses `Depends(require_role("admin"))` alongside middleware enforcement
- **THEN** the middleware checks role first; the dependency provides the `current_user` dict to the handler
