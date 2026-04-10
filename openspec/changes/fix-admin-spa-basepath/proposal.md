## Why

The admin SPA is unreachable through the canonical nginx entry point. Manual testing confirmed:

- `http://localhost:<NGINX_PORT>/admin` → 404 chain (assets load from root, not from `/admin`)
- `http://localhost:<NGINX_PORT>/admin/` → same
- `http://localhost:<WEB_ADMIN_PORT>/admin` → also fails (for the same reason, even bypassing nginx)
- `http://localhost:<WEB_ADMIN_PORT>/` → works, because Vite serves assets at root and the SPA's own router has no basename

Root cause is that `deploy/nginx/nginx.conf:27` proxies `location /admin` to `web-admin:5174`, but the admin Vite dev server (`web/admin/vite.config.ts`) has no `base: '/admin/'`, and `web/admin/src/App.tsx` has no `<BrowserRouter basename=…>`. When the browser requests `/admin`, Vite serves HTML that then references `/src/main.tsx`, `/@vite/client`, etc. at absolute root. The browser resolves those relative to the current URL (`/admin`), the server sees `/admin/src/main.tsx`, Vite has no such module, cascade of 404s.

This blocks any workflow that assumes a single production-style entry point (`nginx` on port `NGINX_PORT`). Developers currently work around it by hitting the Vite dev server directly — fine locally but misleading for testing the full routing stack and for anything that goes through nginx in CI or staging.

**MVP Phase**: Phase 2 — Menu & Cart (PDD §7.1) as the blocking phase, but the fix is deploy-level and applies to every subsequent phase.

## What Changes

- Add `base: '/admin/'` to `web/admin/vite.config.ts`. This tells Vite to emit asset URLs prefixed with `/admin/` in both dev and production builds, so `<script src="/admin/src/main.tsx">` resolves correctly under the nginx `/admin` route.
- Add `basename="/admin"` to the `<BrowserRouter>` in `web/admin/src/App.tsx`. This tells React Router that every declared route is relative to `/admin`, so `/admin/menu` maps to the `menu` route and the default `/admin` maps to the index route.
- Verify the nginx location block at `deploy/nginx/nginx.conf:27-32`. The current `proxy_pass http://admin;` (without a trailing slash) preserves the `/admin` prefix in the upstream request, which is what we want now that Vite knows about that prefix. No nginx change is expected. If inspection reveals a subtle trailing-slash bug, fix it in the same change — but as a discrete follow-up task, not a handwave.
- Update `web/admin/src/main.tsx` ONLY if the StrictMode / root-render pattern needs to pass a `base` hint to anything (it does not — React Router reads the basename from `BrowserRouter`). Keeping main.tsx in the file lane is defensive, not required.
- Add one end-to-end style test using `curl` (or similar) in a VERIFY task that exercises `/admin/`, `/admin/menu`, and a deep link like `/admin/menu/123` through nginx, asserting HTTP 200 + the expected HTML shell.

## Capabilities

### Modified Capabilities
- `frontend-routing`: the admin SPA is served under a `/admin` URL base, both in the Vite dev server and through the nginx reverse proxy, instead of at the server root. Every route in the admin SPA is now addressable at `/admin/<route>`.

## Impact

- **Code**:
  - `web/admin/vite.config.ts` — add one line: `base: '/admin/'`.
  - `web/admin/src/App.tsx` — change `<BrowserRouter>` to `<BrowserRouter basename="/admin">`.
  - `web/admin/src/main.tsx` — touched only if a follow-up needs a `<base>` tag or similar. Aim: zero touch.
  - `deploy/nginx/nginx.conf` — touched only if inspection surfaces a concrete trailing-slash bug. Aim: zero touch; flag for follow-up if any change is needed.
- **APIs**: none.
- **DB**: none.
- **Auth / RBAC**: none. Requests to `/api/v1/*` still go through nginx `location /api/` untouched. The admin SPA still calls API paths at absolute `/api/v1/...`, not `/admin/api/v1/...`, because the API routing is independent of the admin base.
- **Dev workflow change**: direct access to the admin SPA at `http://localhost:<WEB_ADMIN_PORT>/` SHALL stop working after this change — Vite will emit assets under `/admin/`, so direct root access returns 404 on the assets. Developers must use either `http://localhost:<WEB_ADMIN_PORT>/admin/` or `http://localhost:<NGINX_PORT>/admin/`. This is a known tradeoff documented in `README.md` if it exists, or surfaced in the `./scripts/up.sh` banner.
- **Workers**: none.
- **Dependencies**: none.

## Non-Goals

- **No customer SPA changes.** Customer SPA stays at root. This change is admin-only.
- **No admin menu form or CRUD changes.** Those live in `fix-admin-menu-bilingual-schema`. This change MUST NOT edit anything under `web/admin/src/pages/`, `web/admin/src/api/`, or `web/admin/src/i18n/`.
- **No backend URL changes.** API paths stay at `/api/v1/...`.
- **No production deploy / TLS / CSP changes.** Scope is limited to the dev stack's nginx config and Vite base path.
- **No subdomain-based separation.** A future change MAY move admin to `admin.localhost` or similar, but this change keeps the path-based split.
- **No auth redirect URL rewrites.** If `ProtectedRoute` or login redirects use hard-coded absolute paths, they SHOULD already be relative to the router basename — confirm during implementation; if they aren't, raise a follow-up, don't inline the fix.
- **No `staff_auth` login page addition.** The admin SPA currently has no login screen; adding one is a separate concern.

## File Lane (merge safety)

This change is allowed to modify ONLY the following files:

```
web/admin/vite.config.ts
web/admin/src/App.tsx
web/admin/src/main.tsx        (only if strictly required; aim to leave untouched)
deploy/nginx/nginx.conf       (only if a concrete bug is found; aim to leave untouched)
```

This change MUST NOT touch:

```
web/admin/src/pages/**
web/admin/src/api/**
web/admin/src/i18n/**
web/customer/**
services/**
packages/**
database/**
```

Files explicitly reserved for sibling parallel changes:

- `web/admin/src/api/**`, `web/admin/src/pages/Menu/**`, `web/admin/src/i18n/**` → `fix-admin-menu-bilingual-schema`
- `web/customer/**` → `fix-customer-menu-aggregated-endpoint`

If during implementation the agent discovers a required change outside the lane (e.g. a hard-coded absolute URL in `AuthProvider`), STOP and escalate. Do not broaden the diff silently.
