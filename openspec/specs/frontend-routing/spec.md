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
The admin SPA SHALL be served under the URL prefix `/admin/`. Specifically:

- `web/admin/vite.config.ts` SHALL set `base: '/admin/'` so that Vite emits every asset URL (`<script>`, `<link>`, HMR client, etc.) under the `/admin/` prefix in both dev and production builds.
- `web/admin/src/App.tsx` SHALL pass `basename="/admin"` to `<BrowserRouter>` so that every declared route is interpreted relative to that base.
- The canonical admin entry point SHALL be `http://localhost:<NGINX_PORT>/admin/`, served via the existing `deploy/nginx/nginx.conf` `location /admin` block.
- Direct access to the Vite dev server at `http://localhost:<WEB_ADMIN_PORT>/admin/` SHALL also work, for debugging and for development without nginx.
- Direct access at `http://localhost:<WEB_ADMIN_PORT>/` (without the `/admin/` prefix) is NOT required to work — this is an accepted regression from the previous broken-but-superficially-working dev flow.

The admin SPA SHALL use React Router with the following routes, each rendering a placeholder page component:
- `/` — Dashboard
- `/orders` — Order management
- `/menu` — Menu management
- `/users` — User management
- `/promos` — Promocode management
- `/settings` — Shop settings

The admin SPA's API client SHALL continue to call backend paths at `/api/v1/...` (absolute, NOT `/admin/api/v1/...`). Only the static asset URLs and the React Router paths are prefixed by `/admin/`.

#### Scenario: Admin dashboard is reachable through nginx
- **WHEN** a developer opens `http://localhost:<NGINX_PORT>/admin/` in a browser
- **THEN** the admin SPA's dashboard page SHALL render, and every asset request in the DevTools Network tab SHALL return HTTP 200, with no 404s on `/admin/src/main.tsx`, `/admin/@vite/client`, or any other asset

#### Scenario: Deep link to an admin sub-route survives a hard reload
- **WHEN** a developer navigates to `http://localhost:<NGINX_PORT>/admin/menu` and presses reload
- **THEN** the Menu page SHALL render (NOT the dashboard, NOT a 404), because nginx proxies the request to the Vite dev server which serves the SPA shell, and React Router interprets `/admin/menu` relative to `basename="/admin"` and matches it to the `menu` route

#### Scenario: Admin API calls are unaffected by the base path
- **WHEN** the admin SPA makes an HTTP request to the backend (e.g. `listCategories()` calling `/api/v1/admin/menu/categories`)
- **THEN** the outbound request URL SHALL be `/api/v1/admin/menu/categories`, NOT `/admin/api/v1/admin/menu/categories`
- **AND** nginx SHALL route the request through its `location /api/` block to the `core-api` upstream, unchanged

#### Scenario: Customer SPA is unaffected
- **WHEN** a customer opens `http://localhost:<NGINX_PORT>/`
- **THEN** the customer SPA SHALL render exactly as before — no `/admin/` prefix, no routing change, no asset change

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
