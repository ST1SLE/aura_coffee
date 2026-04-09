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
