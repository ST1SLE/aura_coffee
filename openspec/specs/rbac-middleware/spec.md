## ADDED Requirements

### Requirement: Route protection matrix
The system SHALL maintain a declarative route protection matrix in a single Python module (`rbac_matrix.py`). The matrix SHALL map `(HTTP method, path pattern)` pairs to sets of allowed roles. The matrix SHALL be the single source of truth for route-level authorization. Ref: INV-002, INV-010.

#### Scenario: Matrix entry for staff-only endpoint
- **WHEN** the matrix contains entry `("GET", "/api/v1/staff/orders") → {"admin", "barista"}`
- **THEN** only requests with JWT role `admin` or `barista` SHALL be allowed to reach that endpoint

#### Scenario: Matrix entry with path parameter
- **WHEN** the matrix contains entry `("PATCH", "/api/v1/menu/{item_id}") → {"admin"}`
- **THEN** requests to `/api/v1/menu/123e4567-e89b-...` with role `admin` SHALL be allowed

### Requirement: Public routes whitelist
The matrix module SHALL define a `PUBLIC_ROUTES` set of `(HTTP method, path pattern)` tuples. Requests matching a public route SHALL bypass authentication and role checks entirely. Ref: INV-002.

#### Scenario: Health check is public
- **WHEN** a request to `GET /health` is received without an Authorization header
- **THEN** the middleware SHALL allow the request through without auth checks

#### Scenario: Auth endpoints are public
- **WHEN** a request to `POST /api/v1/auth/send-code` is received without an Authorization header
- **THEN** the middleware SHALL allow the request through without auth checks

### Requirement: RBAC middleware enforcement
The system SHALL register a Starlette `BaseHTTPMiddleware` that intercepts every incoming HTTP request. For non-public routes, the middleware SHALL extract and validate the JWT from the `Authorization: Bearer <token>` header, read the `role` claim, and check it against the matrix. Ref: INV-002, INV-010.

#### Scenario: Valid role for protected route
- **WHEN** a request with a valid JWT (`role: "customer"`) hits a route mapped to `{"customer"}`
- **THEN** the middleware SHALL pass the request to the endpoint handler

#### Scenario: Invalid role for protected route
- **WHEN** a request with a valid JWT (`role: "courier"`) hits a route mapped to `{"admin"}`
- **THEN** the middleware SHALL return HTTP 403 with `{"detail": "Insufficient permissions"}`

#### Scenario: Missing Authorization header on protected route
- **WHEN** a request without an Authorization header hits a non-public route
- **THEN** the middleware SHALL return HTTP 401 with `{"detail": "Not authenticated"}`

#### Scenario: Invalid or expired JWT
- **WHEN** a request with an invalid or expired JWT hits a non-public route
- **THEN** the middleware SHALL return HTTP 401 with `{"detail": "Not authenticated"}`

### Requirement: Default-deny policy
Any route NOT present in the route protection matrix AND NOT in the public routes whitelist SHALL be denied. The middleware SHALL return HTTP 403 with `{"detail": "Insufficient permissions"}` for such routes. Ref: INV-002.

#### Scenario: Unlisted route is denied
- **WHEN** a new endpoint `/api/v1/secret` exists in FastAPI but is not in the matrix or public list
- **THEN** any authenticated request to it SHALL receive HTTP 403

#### Scenario: Unlisted route without auth is denied
- **WHEN** a request without Authorization hits an unlisted route
- **THEN** the middleware SHALL return HTTP 401

### Requirement: Longest-prefix matching
When multiple matrix entries could match a request path, the middleware SHALL use the longest (most specific) matching pattern. Ref: INV-010.

#### Scenario: Specific route takes precedence over prefix
- **WHEN** the matrix contains both `("GET", "/api/v1/menu") → {"customer", "admin"}` and `("GET", "/api/v1/menu/{item_id}") → {"admin"}`
- **THEN** a request to `GET /api/v1/menu/abc` SHALL match the `{item_id}` pattern and require `admin` role

### Requirement: CORS preflight bypass
The middleware SHALL allow `OPTIONS` requests to pass through without auth checks, so that CORS preflight requests succeed. Ref: CORS middleware compatibility.

#### Scenario: OPTIONS request bypasses auth
- **WHEN** an `OPTIONS` request is received on any path
- **THEN** the middleware SHALL pass it through without authentication or role checks

### Requirement: Route coverage test
The test suite SHALL include a test that compares all registered FastAPI route paths against the union of the matrix and public routes whitelist. Any route not covered SHALL fail the test. Ref: INV-002.

#### Scenario: All routes covered
- **WHEN** every registered route in the FastAPI app exists in either the matrix or public whitelist
- **THEN** the route coverage test SHALL pass

#### Scenario: Uncovered route detected
- **WHEN** a new route is added to a router but not to the matrix or public whitelist
- **THEN** the route coverage test SHALL fail with a message listing the uncovered route(s)
