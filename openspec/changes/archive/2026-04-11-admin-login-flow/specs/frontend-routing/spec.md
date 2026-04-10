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
- `/` — Dashboard (protected)
- `/orders` — Order management (protected)
- `/menu` — Menu management (protected)
- `/users` — User management (protected)
- `/promos` — Promocode management (protected)
- `/settings` — Shop settings (protected)

Routes marked "protected" SHALL be wrapped, as a group, by a single `ProtectedRoute` wrapper around the shared `Layout` element. `ProtectedRoute` SHALL redirect unauthenticated users to `/login?returnUrl=<current path>` (see spec `admin-auth-ui` §Admin ProtectedRoute guard). The `/login` route SHALL NOT be wrapped — it must be reachable without a token. Refs: spec `admin-auth-ui`; spec `staff-auth`.

- **Previously:** The admin SPA had six routes, all rendered unconditionally inside `Layout`. There was no `/login` route. `web/admin/src/api/client.ts` shipped a `getAccessToken()` stub reading `localStorage.getItem('accessToken')`, but nothing wrote to that key — developers injected tokens by hand via DevTools.
- **Now:** A seventh route `/login` renders outside `Layout`. The remaining six routes are grouped under a `ProtectedRoute` wrapper that redirects unauthenticated users to `/login?returnUrl=<path>`. The token is written to `localStorage.accessToken` by the login page and cleared by a client-wide 401 handler in `authenticatedFetch`.

The admin SPA's API client SHALL continue to call backend paths at `/api/v1/...` (absolute, NOT `/admin/api/v1/...`). Only the static asset URLs and the React Router paths are prefixed by `/admin/`.

#### Scenario: Admin dashboard is reachable through nginx
- **WHEN** a developer opens `http://localhost:<NGINX_PORT>/admin/` in a browser
- **THEN** the admin SPA's dashboard page SHALL render, and every asset request in the DevTools Network tab SHALL return HTTP 200, with no 404s on `/admin/src/main.tsx`, `/admin/@vite/client`, or any other asset

#### Scenario: Bare /admin path redirects to /admin/
- **WHEN** a client sends `GET /admin` (no trailing slash) to `http://localhost:<NGINX_PORT>`
- **THEN** nginx SHALL respond with HTTP 301 and a `Location: /admin/` header, and a standard HTTP client following redirects SHALL land on the admin dashboard at `/admin/`

#### Scenario: Bare /admin path in a browser address bar lands on the dashboard
- **WHEN** a developer types `http://localhost:<NGINX_PORT>/admin` into a browser address bar and presses Enter
- **THEN** the browser SHALL follow the 301 redirect, the address bar SHALL update to `http://localhost:<NGINX_PORT>/admin/`, and the admin SPA dashboard SHALL render with all assets returning 200

#### Scenario: Trailing-slash form is unaffected
- **WHEN** a client sends `GET /admin/` to `http://localhost:<NGINX_PORT>` (the pre-existing canonical form)
- **THEN** nginx SHALL proxy to the `web-admin` upstream via the prefix-match `location /admin` block exactly as before, and the response SHALL be the SPA HTML shell — NOT a redirect, NOT a 404

#### Scenario: Deep link to an admin sub-route survives a hard reload
- **WHEN** a developer navigates to `http://localhost:<NGINX_PORT>/admin/menu` and presses reload
- **THEN** the Menu page SHALL render (NOT the dashboard, NOT a 404), because nginx proxies the request to the Vite dev server which serves the SPA shell, and React Router interprets `/admin/menu` relative to `basename="/admin"` and matches it to the `menu` route

#### Scenario: Admin API calls are unaffected by the base path
- **WHEN** the admin SPA makes an HTTP request to the backend (e.g. `listCategories()` calling `/api/v1/admin/menu/categories`)
- **THEN** the outbound request URL SHALL be `/api/v1/admin/menu/categories`, NOT `/admin/api/v1/admin/menu/categories`
- **AND** nginx SHALL route the request through its `location /api/` block to the `core-api` upstream, unchanged

#### Scenario: Customer SPA is unaffected
- **WHEN** a customer opens `http://localhost:<NGINX_PORT>/`
- **THEN** the customer SPA SHALL render exactly as before — no `/admin/` prefix, no routing change, no asset change, and the `/admin` redirect block SHALL NOT match because `=` is an exact match on the literal path `/admin`

#### Scenario: Navigation between admin routes
- **WHEN** staff navigates to `/orders`
- **THEN** the Orders placeholder page is rendered without a full page reload

#### Scenario: Unknown admin route shows 404
- **WHEN** staff navigates to a non-existent route
- **THEN** a "Page not found" placeholder is displayed

#### Scenario: Unauthenticated access to any protected admin route redirects to login
- **WHEN** an unauthenticated user (no `accessToken` in `localStorage`) navigates to `/admin/menu`
- **THEN** the router SHALL immediately redirect to `/admin/login?returnUrl=%2Fmenu` with `replace: true`, and the Menu page SHALL NOT render

#### Scenario: Login route accessible without auth
- **WHEN** an unauthenticated user navigates to `/admin/login`
- **THEN** the `LoginPage` component is rendered WITHOUT the `Layout` sidebar or header, and no redirect occurs

#### Scenario: Login route accessible WITH auth
- **WHEN** an authenticated user (valid `accessToken` in `localStorage`) navigates to `/admin/login`
- **THEN** the `LoginPage` component is rendered (the login route is NOT wrapped in `ProtectedRoute`), allowing the user to re-authenticate and overwrite the previous token

#### Scenario: Login with returnUrl round-trip
- **WHEN** an unauthenticated user navigates to `/admin/settings`, is redirected to `/admin/login?returnUrl=%2Fsettings`, and submits valid credentials
- **THEN** after successful login the router SHALL navigate to `/settings` with `replace: true`, landing the user at their originally requested page
