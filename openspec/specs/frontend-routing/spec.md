## ADDED Requirements

### Requirement: Customer app routing
The customer SPA SHALL use React Router with the following routes:
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

### Requirement: Admin app routing
The admin SPA SHALL use React Router with the following routes, each rendering a placeholder page component:
- `/` — Dashboard
- `/orders` — Order management
- `/menu` — Menu management
- `/users` — User management
- `/promos` — Promocode management
- `/settings` — Shop settings

#### Scenario: Navigation between admin routes
- **WHEN** staff navigates to `/orders`
- **THEN** the Orders placeholder page is rendered without a full page reload

#### Scenario: Unknown admin route shows 404
- **WHEN** staff navigates to a non-existent route
- **THEN** a "Page not found" placeholder is displayed

### Requirement: App shell layout
Each SPA SHALL have a root layout component wrapping all routes. The layout SHALL include a header (with app name and language switcher) and a main content area. The customer layout SHALL include bottom navigation (mobile) or sidebar (desktop). The admin layout SHALL include a sidebar navigation.

#### Scenario: Layout persists across navigation
- **WHEN** user navigates between routes
- **THEN** the header and navigation remain rendered; only the main content area changes

### Requirement: Placeholder page components
Each placeholder page SHALL render the page name as an `<h1>` heading and a brief description. Placeholder pages SHALL be located in `src/pages/` directory.

#### Scenario: Placeholder renders page identity
- **WHEN** user navigates to a route
- **THEN** the page displays its name (e.g., "Menu", "Cart", "Orders") as a heading
