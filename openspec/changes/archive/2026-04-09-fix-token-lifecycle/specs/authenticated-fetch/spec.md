## ADDED Requirements

### Requirement: Authenticated fetch function
The system SHALL provide an `authenticatedFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response>` function at `src/api/client.ts` that wraps the global `fetch` with automatic `Authorization: Bearer <accessToken>` header injection. The function SHALL merge the auth header into any existing headers provided via `init`. Implements auth-state spec requirement "Token management" (INV-002).

#### Scenario: Request with valid access token
- **WHEN** `authenticatedFetch` is called and an access token exists in memory
- **THEN** the request is sent with `Authorization: Bearer <token>` header merged into any existing headers

#### Scenario: Request without access token
- **WHEN** `authenticatedFetch` is called and no access token exists in memory
- **THEN** the request is sent without an `Authorization` header (server decides whether to reject)

#### Scenario: Caller-provided headers preserved
- **WHEN** `authenticatedFetch` is called with custom headers (e.g., `Content-Type`)
- **THEN** the auth header is merged with caller-provided headers; caller headers are NOT overwritten

### Requirement: Automatic 401 refresh and retry
The system SHALL intercept 401 responses from `authenticatedFetch` and attempt one silent token refresh before returning the error. This implements the auth-state spec scenario "Auto-refresh on 401". The refresh SHALL use the existing `refreshTokens()` function from `api/auth.ts`.

#### Scenario: 401 triggers refresh and successful retry
- **WHEN** a request returns 401 and a refresh token exists in localStorage
- **THEN** the system calls `refreshTokens(refreshToken)`, stores the new token pair via `setAccessToken`/`setRefreshToken`, and retries the original request with the new access token

#### Scenario: 401 with no refresh token available
- **WHEN** a request returns 401 and no refresh token exists in localStorage
- **THEN** the system calls the registered `onAuthFailure` callback and returns the original 401 response

#### Scenario: Refresh attempt fails
- **WHEN** the refresh request itself fails (network error, 401, etc.)
- **THEN** the system clears all tokens via `clearAllTokens`, calls the registered `onAuthFailure` callback, and returns the original 401 response

#### Scenario: Non-401 errors pass through
- **WHEN** a request returns a non-401 error (e.g., 400, 403, 500)
- **THEN** the response is returned as-is without interception

### Requirement: Concurrent 401 refresh deduplication
The system SHALL deduplicate concurrent refresh attempts. If multiple requests receive 401 simultaneously, only one refresh call SHALL be made. All waiting requests SHALL retry with the new token once the single refresh completes.

#### Scenario: Two concurrent 401 responses
- **WHEN** two in-flight requests both receive 401 at approximately the same time
- **THEN** only one `refreshTokens` call is made; both requests retry with the new access token

#### Scenario: Second 401 during failed refresh
- **WHEN** a second 401 arrives while a refresh attempt is already failing
- **THEN** the second request reuses the same failing refresh promise and both receive the auth failure signal

### Requirement: Auth failure callback registration
The system SHALL export a `registerAuthFailureHandler(handler: () => void): void` function that allows `AuthProvider` to register a callback invoked when token refresh fails. This keeps `client.ts` decoupled from React.

#### Scenario: AuthProvider registers failure handler
- **WHEN** `AuthProvider` mounts and calls `registerAuthFailureHandler` with a logout function
- **THEN** subsequent refresh failures invoke that handler to clear auth state

#### Scenario: No handler registered
- **WHEN** a refresh failure occurs and no handler has been registered
- **THEN** the system clears tokens via `clearAllTokens` but does not attempt to update React state
