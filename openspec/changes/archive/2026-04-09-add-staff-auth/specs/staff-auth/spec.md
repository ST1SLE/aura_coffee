## ADDED Requirements

### Requirement: Staff login endpoint
The system SHALL provide `POST /api/v1/staff/auth/login` accepting JSON body `{login: string, password: string}`. On valid credentials, the endpoint SHALL return `{access_token, refresh_token, token_type: "bearer", role}` with HTTP 200. On invalid credentials, it SHALL return HTTP 401 with `{detail: "Invalid credentials"}`. The endpoint MUST NOT reveal whether the login or password is incorrect. Ref: PDD §7.1 Phase 1, step 4; INV-002.

#### Scenario: Successful staff login
- **WHEN** `POST /api/v1/staff/auth/login` with valid login and password for an active staff account
- **THEN** response is HTTP 200 with `access_token` (JWT, HS256, 15 min TTL, payload: `{sub: staff_id, role: staff_role}`), `refresh_token` (opaque UUID stored in Redis with key `staff_refresh:{token}`, 7 day TTL), and `role` matching the staff account's role

#### Scenario: Invalid password
- **WHEN** `POST /api/v1/staff/auth/login` with valid login but wrong password
- **THEN** response is HTTP 401 with `{detail: "Invalid credentials"}`

#### Scenario: Non-existent login
- **WHEN** `POST /api/v1/staff/auth/login` with a login that does not exist
- **THEN** response is HTTP 401 with `{detail: "Invalid credentials"}`

#### Scenario: Inactive staff account
- **WHEN** `POST /api/v1/staff/auth/login` with valid credentials but `is_active = false`
- **THEN** response is HTTP 401 with `{detail: "Invalid credentials"}`

### Requirement: Staff token refresh endpoint
The system SHALL provide `POST /api/v1/staff/auth/refresh` accepting JSON body `{refresh_token: string}`. On valid token, it SHALL rotate the refresh token (delete old, create new) and return new `{access_token, refresh_token, token_type: "bearer"}`. On invalid/expired token, it SHALL return HTTP 401. Ref: PDD §7.1 Phase 1, step 4.

#### Scenario: Successful token refresh
- **WHEN** `POST /api/v1/staff/auth/refresh` with a valid, non-expired refresh token
- **THEN** old refresh token is deleted from Redis, new refresh token is stored in Redis with key `staff_refresh:{new_token}` and 7 day TTL, response is HTTP 200 with new access and refresh tokens

#### Scenario: Expired refresh token
- **WHEN** `POST /api/v1/staff/auth/refresh` with an expired refresh token
- **THEN** response is HTTP 401 with `{detail: "Invalid or expired refresh token"}`

#### Scenario: Already-used refresh token (replay)
- **WHEN** `POST /api/v1/staff/auth/refresh` with a refresh token that was already rotated
- **THEN** response is HTTP 401 with `{detail: "Invalid or expired refresh token"}`

### Requirement: Staff logout endpoint
The system SHALL provide `POST /api/v1/staff/auth/logout` requiring a valid staff JWT in Authorization header. It SHALL delete the staff's refresh token from Redis and return HTTP 200 with `{detail: "Logged out"}`. Ref: PDD §7.1 Phase 1, step 4.

#### Scenario: Successful logout
- **WHEN** `POST /api/v1/staff/auth/logout` with valid staff JWT and `{refresh_token}` body
- **THEN** refresh token is deleted from Redis, response is HTTP 200

#### Scenario: Logout without auth
- **WHEN** `POST /api/v1/staff/auth/logout` without Authorization header
- **THEN** response is HTTP 401

### Requirement: Staff password hashing
The system SHALL hash staff passwords using bcrypt before storing in `staff_accounts.password_hash`. Plaintext passwords MUST NOT be stored or logged. Ref: INV-015.

#### Scenario: Password stored as bcrypt hash
- **WHEN** a staff account is created with a password
- **THEN** `password_hash` column contains a bcrypt hash (prefix `$2b$`), not the plaintext password

#### Scenario: Password verification
- **WHEN** login attempt provides a password
- **THEN** system verifies by comparing bcrypt hash, not by string equality
