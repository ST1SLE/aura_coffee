## ADDED Requirements

### Requirement: AuthProvider clears state on expired refresh token
The AuthProvider test suite SHALL verify that when a stored refresh token is expired (refresh API returns 401), the provider clears `isAuthenticated`, sets `user` to null, and removes the refresh token from storage.

Reference: Auth flow defined in Phase 1 (PDD section 7.1), INV-002 (server-side auth).

#### Scenario: Expired refresh token on mount
- **WHEN** AuthProvider mounts with a stored refresh token AND the refresh API returns 401
- **THEN** `isAuthenticated` SHALL be `false`, `user` SHALL be `null`, and the stored refresh token SHALL be removed

### Requirement: ProtectedRoute preserves returnUrl on redirect
The ProtectedRoute test suite SHALL verify that unauthenticated users are redirected to `/login` with the current path passed as `returnUrl` in router state.

Reference: Auth flow defined in Phase 1 (PDD section 7.1).

#### Scenario: Redirect with returnUrl state
- **WHEN** an unauthenticated user accesses a protected route at `/orders`
- **THEN** the user SHALL be redirected to `/login` with `state.returnUrl` equal to `/orders`

### Requirement: VerifyPage triggers resend via login callback
The VerifyPage test suite SHALL verify that the resend action calls the `login()` function from AuthProvider context with the current phone number.

Reference: OTP resend flow, Phase 1 (PDD section 7.1).

#### Scenario: User clicks resend button
- **WHEN** the resend timer expires and user clicks the resend button on VerifyPage
- **THEN** the `login()` function SHALL be called with the phone number from location state

#### Scenario: Resend error is displayed
- **WHEN** the resend `login()` call rejects with an error
- **THEN** VerifyPage SHALL display an error message to the user

### Requirement: App.test.tsx validates route structure
The App test suite SHALL verify that public routes render without auth, protected routes redirect unauthenticated users, and unknown paths render the not-found page.

Reference: Route config in App.tsx, Phase 1 auth gates (PDD section 7.1).

#### Scenario: Public route renders without auth
- **WHEN** an unauthenticated user navigates to `/login`
- **THEN** the LoginPage component SHALL render without redirect

#### Scenario: Protected route redirects unauthenticated user
- **WHEN** an unauthenticated user navigates to `/`
- **THEN** the user SHALL be redirected to `/login`

#### Scenario: Unknown route renders not-found page
- **WHEN** a user navigates to `/nonexistent`
- **THEN** the NotFoundPage component SHALL render

### Requirement: VerifyPage handles CODE_NOT_DELIVERED (409)
The VerifyPage test suite SHALL verify that when the backend returns HTTP 409 (OTP status not yet "sent"), the UI displays a specific "not delivered" message rather than a generic network error, and keeps the OTP input editable for retry.

Reference: OTP 409 error handling (fix-otp-409-error-handling change).

#### Scenario: 409 shows "not delivered" message
- **WHEN** `verifyCode` rejects with `AuthError` code `CODE_NOT_DELIVERED`
- **THEN** VerifyPage SHALL display a "not delivered" message

#### Scenario: 409 does not show generic network error
- **WHEN** `verifyCode` rejects with `AuthError` code `CODE_NOT_DELIVERED`
- **THEN** the generic network error message SHALL NOT be displayed

#### Scenario: OTP input remains editable after 409
- **WHEN** a CODE_NOT_DELIVERED error is displayed
- **THEN** the OTP input fields SHALL remain enabled so the user can retry

### Requirement: authenticatedFetch token lifecycle
The `client.test.ts` test suite SHALL verify that `authenticatedFetch` correctly attaches access tokens, handles 401 refresh flows, and deduplicates concurrent refresh attempts.

Reference: Token management spec (auth-state), authenticated-fetch spec.

#### Scenario: Access token attached to request
- **WHEN** an access token exists in memory and `authenticatedFetch` is called
- **THEN** the request SHALL include `Authorization: Bearer <token>` header

#### Scenario: Request without auth when no token
- **WHEN** no access token exists and `authenticatedFetch` is called
- **THEN** the request SHALL be sent without an Authorization header

#### Scenario: Caller-provided headers preserved
- **WHEN** `authenticatedFetch` is called with custom headers
- **THEN** the custom headers SHALL be preserved alongside the Authorization header

#### Scenario: Non-401 errors pass through
- **WHEN** the server responds with a non-401 error (e.g., 500)
- **THEN** `authenticatedFetch` SHALL return the error response without interception

#### Scenario: 401 triggers refresh and retry
- **WHEN** the server responds with 401 and a refresh token exists
- **THEN** `authenticatedFetch` SHALL call `refreshTokens`, then retry the original request with the new access token

#### Scenario: No refresh token triggers failure handler
- **WHEN** the server responds with 401 and no refresh token exists
- **THEN** `authenticatedFetch` SHALL call the registered failure handler and return the 401 response

#### Scenario: Refresh failure triggers failure handler
- **WHEN** the server responds with 401 and the refresh attempt also fails
- **THEN** `authenticatedFetch` SHALL clear tokens and call the failure handler

#### Scenario: Concurrent refresh calls deduplicated
- **WHEN** multiple requests receive 401 simultaneously
- **THEN** only one refresh call SHALL be made, and all waiting requests SHALL retry with the new token
