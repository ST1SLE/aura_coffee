## MODIFIED Requirements

_References: PDD §7.1 Phase 2 (Menu & Cart — as the blocking phase for the fix, though the requirement itself spans every phase), existing spec `frontend-routing` (admin app routing requirement)._

### Requirement: Admin app routing

**Previously:** The admin SPA used React Router with routes at `/`, `/orders`, `/menu`, `/users`, `/promos`, `/settings`. The SPA was served from the server root, with no base path, and was reachable only by direct access to the Vite dev server (`http://localhost:<WEB_ADMIN_PORT>/`). Accessing the admin SPA through the canonical nginx entry point at `/admin` returned 404s on every asset because Vite emitted root-relative asset URLs.

**Now:** The admin SPA SHALL be served under the URL prefix `/admin/`. Specifically:

- `web/admin/vite.config.ts` SHALL set `base: '/admin/'` so that Vite emits every asset URL (`<script>`, `<link>`, HMR client, etc.) under the `/admin/` prefix in both dev and production builds.
- `web/admin/src/App.tsx` SHALL pass `basename="/admin"` to `<BrowserRouter>` so that every declared route is interpreted relative to that base.
- The canonical admin entry point SHALL be `http://localhost:<NGINX_PORT>/admin/`, served via the existing `deploy/nginx/nginx.conf` `location /admin` block.
- Direct access to the Vite dev server at `http://localhost:<WEB_ADMIN_PORT>/admin/` SHALL also work, for debugging and for development without nginx.
- Direct access at `http://localhost:<WEB_ADMIN_PORT>/` (without the `/admin/` prefix) is NOT required to work — this is an accepted regression from the previous broken-but-superficially-working dev flow.

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
