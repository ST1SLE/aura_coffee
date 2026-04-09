## ADDED Requirements

### Requirement: Auth API client interface
The system SHALL provide an auth API client module at `src/api/auth.ts` exporting functions: `sendCode(phone: string)`, `verifyCode(phone: string, code: string)`, `refreshTokens(refreshToken: string)`, `logout()`. Each function SHALL call the backend at `/api/v1/auth/*` via `fetch` and return a typed Promise. The module SHALL map backend snake_case responses to camelCase frontend types.

#### Scenario: sendCode request
- **WHEN** `sendCode` is called with a valid E.164 phone string
- **THEN** it sends `POST /api/v1/auth/send-code` with `{ phone }` and returns `{ message, phone_hash }`

#### Scenario: verifyCode success
- **WHEN** `verifyCode` is called with a valid phone and correct code
- **THEN** it sends `POST /api/v1/auth/verify-code` with `{ phone, code }`, decodes the JWT `access_token` to extract user `{ id, role }`, and returns `{ accessToken, refreshToken, user }`

#### Scenario: verifyCode failure — wrong code
- **WHEN** the backend returns 401 with detail containing "Wrong code" or "Too many failed"
- **THEN** the client throws `AuthError` with code `INVALID_CODE`

#### Scenario: verifyCode failure — expired code
- **WHEN** the backend returns 410
- **THEN** the client throws `AuthError` with code `CODE_EXPIRED`

#### Scenario: refreshTokens
- **WHEN** `refreshTokens` is called with a valid refresh token
- **THEN** it sends `POST /api/v1/auth/refresh` with `{ refresh_token }` and returns `{ accessToken, refreshToken }`

#### Scenario: logout
- **WHEN** `logout` is called
- **THEN** it sends `POST /api/v1/auth/logout` with `Authorization: Bearer <accessToken>` header from in-memory token storage. Network errors are silently ignored.

### Requirement: HTTP error mapping
The auth API client SHALL map backend HTTP error responses to typed `AuthError` instances using the following rules:

- 429 → `RATE_LIMITED` (with `retryAfter` from `retry_after` field)
- 410 → `CODE_EXPIRED`
- 401 with "Wrong code" or "Too many failed" in detail → `INVALID_CODE`
- Network failure (fetch throws) → `NETWORK_ERROR`
- Any other error → `UNKNOWN_ERROR`

#### Scenario: Rate limit error
- **WHEN** the API returns a 429 response with `{ detail, retry_after }`
- **THEN** the client throws `AuthError` with code `RATE_LIMITED` and `retryAfter` set to the `retry_after` value in seconds

#### Scenario: Network failure
- **WHEN** `fetch` throws (no connectivity, DNS failure, etc.)
- **THEN** the client throws `AuthError` with code `NETWORK_ERROR`

### Requirement: Mock auth implementation for tests
The system SHALL provide a mock implementation at `src/api/mocks/auth.ts` for use in unit tests. The mock SHALL simulate API behavior with predictable responses: code `000000` succeeds, any other code fails.

#### Scenario: Mock verifyCode success
- **WHEN** `verifyCode` is called in mock with code `000000`
- **THEN** it returns mock tokens and user object

### Requirement: Auth error types
The system SHALL define typed error codes: `INVALID_CODE`, `CODE_EXPIRED`, `RATE_LIMITED`, `NETWORK_ERROR`, `UNKNOWN_ERROR`. The `AuthError` class SHALL include optional `retryAfter` field for rate-limit scenarios.

#### Scenario: AuthError construction
- **WHEN** an `AuthError` is created with code `RATE_LIMITED` and retryAfter 60
- **THEN** `error.code` is `RATE_LIMITED`, `error.retryAfter` is 60

### Requirement: Vite proxy for API calls
The Vite dev server SHALL proxy requests matching `/api` to the backend at `http://localhost:8000` to avoid CORS issues during development.

#### Scenario: API request proxied
- **WHEN** frontend makes a `fetch('/api/v1/auth/send-code', ...)`
- **THEN** Vite proxies the request to `http://localhost:8000/api/v1/auth/send-code`
