## ADDED Requirements

### Requirement: Staff auth tests use FastAPI dependency_overrides
Staff auth endpoint tests SHALL mock `get_db` and `get_redis` via `app.dependency_overrides`, NOT via `unittest.mock.patch()`. Patching module attributes does not intercept FastAPI's `Depends()` resolution — the DI container holds a reference to the original function, so `patch()` on the router module has no effect.

Reference: FastAPI testing docs, fix committed 2026-04-10 (6556c59).

#### Scenario: Mocked DB is used in test
- **WHEN** a staff auth test overrides `get_db` via `app.dependency_overrides[get_db]`
- **THEN** the endpoint receives the mock DB session, NOT a real database connection

#### Scenario: Overrides are cleaned up after each test
- **WHEN** a test completes (success or failure)
- **THEN** `app.dependency_overrides` SHALL have `get_db` and `get_redis` removed to prevent state leakage

### Requirement: Staff login endpoint tests
Tests SHALL verify all branches of `POST /api/v1/staff/auth/login` using mocked DB and Redis.

#### Scenario: Valid credentials return tokens
- **WHEN** `POST /api/v1/staff/auth/login` with login/password matching an active staff account
- **THEN** response is HTTP 200 with `access_token`, `refresh_token`, `token_type: "bearer"`, and `role`

#### Scenario: Wrong password returns 401
- **WHEN** `POST /api/v1/staff/auth/login` with correct login but wrong password
- **THEN** response is HTTP 401 with `{detail: "Invalid credentials"}`

#### Scenario: Non-existent login returns 401
- **WHEN** `POST /api/v1/staff/auth/login` with a login that does not exist (DB returns None)
- **THEN** response is HTTP 401 with `{detail: "Invalid credentials"}`

#### Scenario: Inactive account returns 401
- **WHEN** `POST /api/v1/staff/auth/login` with valid credentials but `is_active = false`
- **THEN** response is HTTP 401 with `{detail: "Invalid credentials"}`

### Requirement: Staff token refresh tests
Tests SHALL verify `POST /api/v1/staff/auth/refresh` with mocked Redis session data.

#### Scenario: Valid refresh token rotates and returns new pair
- **WHEN** `POST /api/v1/staff/auth/refresh` with a token whose session data exists in Redis
- **THEN** response is HTTP 200 with new `access_token` and `refresh_token`, and the old token is deleted from Redis

#### Scenario: Expired/missing refresh token returns 401
- **WHEN** `POST /api/v1/staff/auth/refresh` with a token not found in Redis
- **THEN** response is HTTP 401 with `{detail: "Invalid or expired refresh token"}`

#### Scenario: Replayed (already-rotated) token returns 401
- **WHEN** `POST /api/v1/staff/auth/refresh` with a token that was already consumed
- **THEN** response is HTTP 401

### Requirement: Staff logout tests
Tests SHALL verify `POST /api/v1/staff/auth/logout` requires authentication.

#### Scenario: Authenticated logout succeeds
- **WHEN** `POST /api/v1/staff/auth/logout` with valid staff JWT and refresh token in body
- **THEN** response is HTTP 200 with `{detail: "Logged out"}`

#### Scenario: Unauthenticated logout rejected
- **WHEN** `POST /api/v1/staff/auth/logout` without Authorization header
- **THEN** response is HTTP 401 or 403

### Requirement: RBAC integration via require_role
Tests SHALL verify the `require_role` dependency using a dedicated test FastAPI app with protected endpoints.

#### Scenario: Authorized role allowed
- **WHEN** a JWT with `role: "admin"` accesses an admin-only endpoint
- **THEN** response is HTTP 200

#### Scenario: Unauthorized role denied
- **WHEN** a JWT with `role: "barista"` accesses an admin-only endpoint
- **THEN** response is HTTP 403 with `{detail: "Insufficient permissions"}`

#### Scenario: No auth header denied
- **WHEN** request has no Authorization header
- **THEN** response is HTTP 401 or 403

#### Scenario: Customer role denied on staff endpoint
- **WHEN** a JWT with `role: "customer"` accesses a staff endpoint
- **THEN** response is HTTP 403

#### Scenario: Multi-role endpoint accepts any listed role
- **WHEN** a JWT with `role: "barista"` accesses an endpoint allowing `["admin", "barista"]`
- **THEN** response is HTTP 200
