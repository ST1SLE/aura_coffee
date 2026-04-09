## ADDED Requirements

### Requirement: AuthProvider context
The system SHALL provide an `AuthProvider` React context component that wraps the application and exposes auth state: `{ user: User | null, isAuthenticated: boolean, isLoading: boolean, login: (phone) => Promise, verifyCode: (phone, code) => Promise, logout: () => Promise }`. The `AuthProvider` SHALL attempt a silent refresh on mount if a refresh token exists in localStorage.

#### Scenario: Initial load with valid refresh token
- **WHEN** the app mounts and a refresh token exists in localStorage
- **THEN** `AuthProvider` calls `refreshTokens`, decodes the returned JWT access token to extract user `{ id, role }`, sets `isAuthenticated: true` and `isLoading: false` upon success

#### Scenario: Initial load without refresh token
- **WHEN** the app mounts and no refresh token exists in localStorage
- **THEN** `AuthProvider` sets `isAuthenticated: false` and `isLoading: false` without API calls

#### Scenario: Initial load with expired refresh token
- **WHEN** the app mounts and the refresh token in localStorage is expired/invalid
- **THEN** `AuthProvider` clears the stored token, sets `isAuthenticated: false` and `isLoading: false`

### Requirement: Token management
The system SHALL store the access token in-memory (module-level variable) and the refresh token in localStorage under key `aura_refresh_token`. The access token SHALL be attached to all authenticated API requests via an `Authorization: Bearer <token>` header. Upon receiving a 401 response, the system SHALL attempt one silent refresh before redirecting to login.

#### Scenario: Access token attached to requests
- **WHEN** an authenticated API request is made
- **THEN** the access token from memory is included in the `Authorization` header

#### Scenario: Auto-refresh on 401
- **WHEN** an API request returns 401 and a refresh token exists
- **THEN** the system calls `refreshTokens`, retries the original request with the new access token

#### Scenario: Refresh failure triggers logout
- **WHEN** a 401 auto-refresh attempt also fails
- **THEN** the system clears all tokens and sets `isAuthenticated: false`

### Requirement: useAuth hook
The system SHALL export a `useAuth()` hook that returns the AuthContext value. Calling `useAuth()` outside of `AuthProvider` SHALL throw an error.

#### Scenario: useAuth within AuthProvider
- **WHEN** a component inside `AuthProvider` calls `useAuth()`
- **THEN** it receives the current auth state and action functions

#### Scenario: useAuth outside AuthProvider
- **WHEN** a component outside `AuthProvider` calls `useAuth()`
- **THEN** a descriptive error is thrown

### Requirement: ProtectedRoute component
The system SHALL provide a `ProtectedRoute` component that checks `isAuthenticated` from AuthContext. If not authenticated and not loading, it SHALL redirect to `/login` preserving the attempted URL as `returnUrl` in navigation state. If loading, it SHALL render a loading indicator.

#### Scenario: Unauthenticated user accessing protected route
- **WHEN** an unauthenticated user navigates to a protected route (e.g., `/orders`)
- **THEN** they are redirected to `/login` with the original path saved in state

#### Scenario: Authenticated user accessing protected route
- **WHEN** an authenticated user navigates to a protected route
- **THEN** the route content renders normally

#### Scenario: Redirect after login
- **WHEN** user logs in after being redirected from a protected route
- **THEN** they are redirected back to the originally attempted URL

#### Scenario: Auth loading state
- **WHEN** `AuthProvider` is performing silent refresh (isLoading: true)
- **THEN** `ProtectedRoute` displays a loading indicator instead of redirecting
