## MODIFIED Requirements

### Requirement: Customer app routing
Previously: The customer SPA SHALL use React Router with routes: `/`, `/cart`, `/checkout`, `/orders`, `/profile`, each rendering a placeholder page component.
Now: The customer SPA SHALL use React Router with the following routes:
- `/` — Home / Menu
- `/login` — Phone input (public)
- `/login/verify` — OTP verification (public)
- `/cart` — Cart (protected)
- `/checkout` — Checkout (protected)
- `/orders` — Order history (protected)
- `/profile` — Profile (protected)

Routes marked "protected" SHALL be wrapped with `ProtectedRoute` and redirect unauthenticated users to `/login`. Routes marked "public" SHALL be accessible without authentication. The app SHALL be wrapped with `AuthProvider`.

#### Scenario: Navigation between customer routes
- **WHEN** an authenticated user navigates to `/cart`
- **THEN** the Cart page is rendered without a full page reload

#### Scenario: Unauthenticated access to protected route
- **WHEN** an unauthenticated user navigates to `/checkout`
- **THEN** they are redirected to `/login` with `/checkout` saved as return URL

#### Scenario: Login route accessible without auth
- **WHEN** an unauthenticated user navigates to `/login`
- **THEN** the phone input screen is rendered

#### Scenario: Unknown route shows 404
- **WHEN** user navigates to a non-existent route (e.g., `/nonexistent`)
- **THEN** a "Page not found" placeholder is displayed
