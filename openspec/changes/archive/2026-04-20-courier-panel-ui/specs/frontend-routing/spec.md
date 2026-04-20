## MODIFIED Requirements

### Requirement: Admin app routing
The admin SPA SHALL be served under the URL prefix `/admin/`. Specifically:

- `web/admin/vite.config.ts` SHALL set `base: '/admin/'` so that Vite emits every asset URL (`<script>`, `<link>`, HMR client, etc.) under the `/admin/` prefix in both dev and production builds.
- `web/admin/src/App.tsx` SHALL pass `basename="/admin"` to `<BrowserRouter>` so that every declared route is interpreted relative to that base.
- The canonical admin entry point SHALL be `http://localhost:<NGINX_PORT>/admin/`, served via the existing `deploy/nginx/nginx.conf` `location /admin` block.
- `deploy/nginx/nginx.conf` SHALL additionally declare an exact-match `location = /admin` block that returns a `301` redirect to `/admin/`, so that a bare-path request for `http://localhost:<NGINX_PORT>/admin` (without trailing slash) resolves to the canonical entry point instead of returning HTTP 404. The exact-match block SHALL be declared before the existing `location /admin` (prefix-match) block, so nginx's location-matching rules pick the exact-match form for the bare path.
- Direct access to the Vite dev server at `http://localhost:<WEB_ADMIN_PORT>/admin/` SHALL also work, for debugging and for development without nginx.
- Direct access at `http://localhost:<WEB_ADMIN_PORT>/` (without the `/admin/` prefix) is NOT required to work — this is an accepted regression from the previous broken-but-superficially-working dev flow.

The admin SPA SHALL use React Router with the following routes:
- `/login` — Staff login (public, renders outside `Layout`)
- `/` — Dashboard (protected, `allowedRoles: ['admin', 'barista']`)
- `/orders` — Order management (protected, `allowedRoles: ['admin', 'barista']`)
- `/menu` — Menu management (protected, `allowedRoles: ['admin', 'barista']`)
- `/users` — User management (protected, `allowedRoles: ['admin', 'barista']`)
- `/promos` — Promocode management (protected, `allowedRoles: ['admin', 'barista']`)
- `/settings` — Shop settings (protected, `allowedRoles: ['admin', 'barista']`)
- `/courier` — Courier deliveries view (protected, `allowedRoles: ['admin', 'courier']`, renders outside `Layout` — no sidebar)
- any other path — `NotFoundPage`

The admin/barista routes (`/`, `/orders`, `/menu`, `/users`, `/promos`, `/settings`) SHALL be grouped under a single `ProtectedRoute` wrapper with `allowedRoles={['admin', 'barista']}` around the shared `Layout` element. The `/courier` route SHALL be wrapped, separately, by a `ProtectedRoute` with `allowedRoles={['admin', 'courier']}` around a lightweight shell (`CourierShell`) that renders only the `LanguageSwitcher` and `NotificationList`, **not** the admin `Layout`. `ProtectedRoute` SHALL redirect unauthenticated users to `/login?returnUrl=<current path>` (see spec `admin-auth-ui` §Admin ProtectedRoute guard). The `/login` route SHALL NOT be wrapped — it must be reachable without a token.

**Previously:** The admin SPA had six protected routes (`/`, `/orders`, `/menu`, `/users`, `/promos`, `/settings`), all grouped under a single `ProtectedRoute` wrapper with no role check, all rendering inside `Layout`. There was no `/courier` route. A logged-in courier could reach every admin route via URL and would see (but not mutate) an admin-shaped UI.

**Now:** A seventh protected route `/courier` is added under its own `ProtectedRoute` group with `allowedRoles: ['admin', 'courier']` and a courier-specific shell. The existing six routes gain `allowedRoles: ['admin', 'barista']`. Couriers attempting to visit any admin route are redirected to `/courier`; admins and baristas attempting to visit `/courier` are redirected to `/` unless explicitly allowed (admins are).

Refs: spec `admin-auth-ui`; spec `staff-auth`; spec `courier-panel-ui`; PDD §4.5; INV-010.

The admin SPA's API client SHALL continue to call backend paths at `/api/v1/...` (absolute, NOT `/admin/api/v1/...`). Only the static asset URLs and the React Router paths are prefixed by `/admin/`.

#### Scenario: Admin dashboard is reachable through nginx
- **WHEN** a developer opens `http://localhost:<NGINX_PORT>/admin/` in a browser
- **THEN** the admin SPA's dashboard page SHALL render, and every asset request in the DevTools Network tab SHALL return HTTP 200, with no 404s on `/admin/src/main.tsx`, `/admin/@vite/client`, or any other asset

#### Scenario: Admin dashboard is reachable on the Vite dev server
- **WHEN** a developer opens `http://localhost:<WEB_ADMIN_PORT>/admin/` directly (bypassing nginx)
- **THEN** the admin SPA's dashboard page SHALL render, and every asset request in the DevTools Network tab SHALL return HTTP 200

#### Scenario: Admin bare path without trailing slash redirects
- **WHEN** a developer opens `http://localhost:<NGINX_PORT>/admin` (no trailing slash) in a browser
- **THEN** the browser receives an HTTP 301 redirect to `http://localhost:<NGINX_PORT>/admin/`, and the subsequent request resolves to the admin SPA's dashboard page (no 404)

#### Scenario: Unauthenticated access to admin route
- **WHEN** an unauthenticated user navigates to `/admin/menu`
- **THEN** they are redirected to `/admin/login?returnUrl=%2Fmenu` and the login page is rendered

#### Scenario: Unauthenticated access to courier route
- **WHEN** an unauthenticated user navigates to `/admin/courier`
- **THEN** they are redirected to `/admin/login?returnUrl=%2Fcourier` and the login page is rendered

#### Scenario: Courier navigating to admin route is redirected
- **WHEN** an authenticated courier (token present, `staffRole === 'courier'`) navigates to `/admin/menu`
- **THEN** they are redirected to `/admin/courier` (the role-based redirect from `ProtectedRoute`), and the menu page is NOT rendered

#### Scenario: Barista navigating to courier route is redirected
- **WHEN** an authenticated barista (token present, `staffRole === 'barista'`) navigates to `/admin/courier`
- **THEN** they are redirected to `/admin/` (the role-based redirect from `ProtectedRoute`), and the courier page is NOT rendered

#### Scenario: Admin can visit courier route directly
- **WHEN** an authenticated admin (token present, `staffRole === 'admin'`) navigates to `/admin/courier`
- **THEN** the courier page renders (admins are explicitly in the `['admin', 'courier']` allow-list)

#### Scenario: Courier page does not render the admin sidebar
- **WHEN** any authorized user (admin or courier) visits `/admin/courier`
- **THEN** the response does NOT contain the admin `Layout` sidebar navigation (no Dashboard/Orders/Menu/Users/Promos/Settings links), only the courier page chrome

#### Scenario: Login page is not wrapped in ProtectedRoute
- **WHEN** any user navigates to `/admin/login`
- **THEN** the login page renders regardless of token or role state, and no redirect is issued by `ProtectedRoute`

#### Scenario: Unknown route shows 404
- **WHEN** a user navigates to a non-existent route (e.g., `/admin/nonexistent`)
- **THEN** the `NotFoundPage` is rendered
