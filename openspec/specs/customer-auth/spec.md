## ADDED Requirements

### Requirement: JWT access token issuance
The system SHALL issue a JWT access token upon successful OTP verification. The token SHALL be signed with HS256 using `JWT_SECRET_KEY` from env (INV-015). Payload SHALL contain `{sub: user_id, role: "customer", iat, exp}`. TTL SHALL be 15 minutes.

#### Scenario: Access token issued after OTP verification
- **WHEN** OTP transitions to VERIFIED
- **THEN** system returns JSON response with `access_token` (JWT) and `refresh_token` (opaque UUID)

#### Scenario: Access token contains correct claims
- **WHEN** access token is decoded
- **THEN** it contains `sub` (user UUID), `role` ("customer"), `iat` (issued at), `exp` (iat + 15 min)

### Requirement: Refresh token issuance and storage
The system SHALL issue an opaque UUID refresh token alongside the access token. The refresh token SHALL be stored in Redis at key `session:{refresh_token}` with TTL 7 days (§5.3). Value SHALL contain `{user_id, issued_at}`.

#### Scenario: Refresh token stored in Redis
- **WHEN** tokens are issued after OTP verification
- **THEN** refresh token is stored in Redis with TTL 604800 seconds (7 days)

### Requirement: Token refresh with rotation
The system SHALL provide `POST /api/v1/auth/refresh` endpoint that accepts a refresh token, validates it against Redis, and returns a new access+refresh token pair. The old refresh token SHALL be deleted (rotation).

#### Scenario: Valid refresh token
- **WHEN** client sends `POST /api/v1/auth/refresh` with a valid refresh token present in Redis
- **THEN** system deletes the old refresh token from Redis, creates a new refresh token, stores it in Redis, and returns new `access_token` + `refresh_token`

#### Scenario: Expired or invalid refresh token
- **WHEN** client sends refresh request with a token not found in Redis (expired or invalid)
- **THEN** system returns HTTP 401 indicating re-authentication required

#### Scenario: Reuse of rotated refresh token
- **WHEN** client attempts to use a refresh token that was already rotated (deleted)
- **THEN** system returns HTTP 401

### Requirement: Logout
The system SHALL provide `POST /api/v1/auth/logout` endpoint (authenticated) that deletes the user's refresh token from Redis, effectively ending the session.

#### Scenario: Successful logout
- **WHEN** authenticated client sends `POST /api/v1/auth/logout`
- **THEN** system deletes the refresh token from Redis and returns HTTP 200

#### Scenario: Unauthenticated logout attempt
- **WHEN** unauthenticated client sends `POST /api/v1/auth/logout`
- **THEN** system returns HTTP 401

### Requirement: User account creation on first OTP request
The system SHALL create a user account (status=PENDING_VERIFICATION) upon the first OTP request for an unknown phone number (§6.5). It SHALL create `users` record with `phone_hash` and `user_profiles` record with encrypted `phone`. `loyalty_accounts` SHALL NOT be created at this stage.

#### Scenario: First OTP request for new phone number
- **WHEN** `POST /api/v1/auth/send-code` is called with a phone number that has no matching `phone_hash` in `users`
- **THEN** system creates `users` (status=PENDING_VERIFICATION) and `user_profiles` (phone=encrypted) records, then proceeds with OTP creation

#### Scenario: OTP request for existing PENDING_VERIFICATION user
- **WHEN** `POST /api/v1/auth/send-code` is called for a phone with existing PENDING_VERIFICATION user
- **THEN** system proceeds with OTP creation without creating new records

#### Scenario: OTP request for existing ACTIVE user
- **WHEN** `POST /api/v1/auth/send-code` is called for a phone with existing ACTIVE user
- **THEN** system proceeds with OTP creation (session resumption flow)

#### Scenario: OTP request for BLOCKED user
- **WHEN** `POST /api/v1/auth/send-code` is called for a phone with BLOCKED user (§6.5)
- **THEN** system returns HTTP 403 indicating account is blocked

### Requirement: User activation on first successful verification
The system SHALL transition user status from PENDING_VERIFICATION to ACTIVE upon first successful OTP verification (§6.5). At this point, system SHALL create `loyalty_accounts` with balance=0.

#### Scenario: First verification activates account
- **WHEN** OTP is verified for a PENDING_VERIFICATION user
- **THEN** system transitions user to ACTIVE and creates `loyalty_accounts` (balance=0) in a single database transaction

#### Scenario: Verification for already ACTIVE user
- **WHEN** OTP is verified for an ACTIVE user
- **THEN** system issues tokens without changing user status (session resumption)

### Requirement: User account state machine enforcement
The system SHALL enforce the user account state machine (§6.5) exhaustively. Only transitions listed in §6.5 are permitted (INV-016). In this change scope: only PENDING_VERIFICATION → ACTIVE is implemented.

#### Scenario: Forbidden transition attempt
- **WHEN** any operation attempts a user status transition not in §6.5
- **THEN** system rejects the operation
