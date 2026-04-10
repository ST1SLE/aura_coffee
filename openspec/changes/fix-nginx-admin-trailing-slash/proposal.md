## Why

`http://localhost:${NGINX_PORT}/admin` (no trailing slash) returns HTTP 404 through the nginx reverse proxy, while `http://localhost:${NGINX_PORT}/admin/` (with trailing slash) returns 200. Reproduced:

```
curl -o /dev/null -w '%{http_code}\n' http://localhost:8240/admin/   → 200
curl -o /dev/null -w '%{http_code}\n' http://localhost:8240/admin    → 404
```

Root cause: `deploy/nginx/nginx.conf:27` declares `location /admin { proxy_pass http://admin; }` with no trailing-slash handling. Because the Vite dev server inside `web-admin` is configured with `base: '/admin/'` (set by the earlier `fix-admin-spa-basepath` change), it only serves the SPA shell at `/admin/` — the bare `/admin` path has no corresponding file and Vite 404s. Nginx faithfully proxies the broken path instead of normalizing to the canonical one.

This bites manual testing because:
- The test scenario doc under Phase 2 instructs developers to open `http://localhost:8240/admin` (no slash). Devs follow the doc, hit 404, assume the admin SPA is broken, and stall.
- Every other SPA convention on the web accepts either form — the missing trailing slash is a footgun, not a feature.
- Future end-to-end tests or CI probes that omit the slash would also break.

The previous `fix-admin-spa-basepath` change intentionally left this untouched ("No nginx change is expected. If inspection reveals a subtle trailing-slash bug, fix it in the same change"). Inspection during that change did not surface the bug because it only checked `/admin/`. This change closes the gap.

**MVP Phase**: Phase 2 — Menu & Cart (PDD §7.1) as the blocking phase for manual testing; the fix is routing-layer and applies to every subsequent phase.

## What Changes

- Add a `location = /admin { return 301 /admin/; }` block to `deploy/nginx/nginx.conf`, placed **before** the existing `location /admin { ... }` block so the exact-match `=` form wins for the bare path. The 301 redirects to the trailing-slash canonical form that already works.
- Update the `frontend-routing` capability spec's `Admin app routing` requirement with a new scenario that asserts the bare-slash request returns a 301 redirect to the trailing-slash form.
- No changes to `web/admin/vite.config.ts`, `web/admin/src/App.tsx`, or anything under `web/admin/src/**`. The previous `fix-admin-spa-basepath` change already correctly configures `base: '/admin/'` and `basename="/admin"`; this change is nginx-only.
- No changes to `docker-compose.yml`, `.env.example`, `scripts/up.sh`, or any backend code.

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities

- `frontend-routing`: the admin SPA SHALL be reachable via both `http://localhost:${NGINX_PORT}/admin` and `http://localhost:${NGINX_PORT}/admin/`, with the bare form 301-redirecting to the trailing-slash form.

## Impact

- **Code**:
  - `deploy/nginx/nginx.conf` — add three lines (one `location = /admin` exact-match block) before the existing `location /admin` block.
  - `openspec/specs/frontend-routing/spec.md` — via the delta spec under this change.
- **APIs**: none.
- **DB**: none.
- **Auth / RBAC**: none. The 301 is issued by nginx before any application-level auth runs, which is fine because the response is a redirect, not a protected resource.
- **Dev workflow change**: `http://localhost:${NGINX_PORT}/admin` now works (via redirect). No existing URL breaks. Any bookmark or script using the trailing-slash form continues to work unchanged.
- **Workers**: none.
- **Dependencies**: none.
- **Production**: if a production nginx config is derived from this dev file in the future, it picks up the same redirect. No-op for today because no production nginx exists yet.
- **Inviolable rules**: none affected.

## Non-Goals

- **Not changing the Vite base path or React Router basename.** Those are already correct per `fix-admin-spa-basepath`. This change MUST NOT touch `web/admin/vite.config.ts`, `web/admin/src/App.tsx`, or `web/admin/src/main.tsx`.
- **Not addressing migrations / seeds / bring-up flow.** That's the sibling change `fix-dev-stack-auto-apply-migrations`. This change MUST NOT touch `docker-compose.yml`, `.env.example`, `scripts/up.sh`, or `database/AGENTS.md`.
- **Not adding a second location for direct Vite port access (`http://localhost:${WEB_ADMIN_PORT}/admin`).** The Vite dev server already handles its own trailing-slash behavior and is explicitly documented as a debug-only path, not the canonical entry point.
- **Not rewriting proxy_pass semantics, adding `proxy_redirect`, or changing any headers on the existing `/admin/` block.** Scope is limited to adding the redirect block for the bare path.
- **Not changing the customer SPA's root routing.** `location /` continues to proxy to the customer container unchanged.
- **Not introducing a generic "strip trailing slash" or "add trailing slash" rule for every location.** Explicit, per-path redirects only.

## File Lane (merge safety)

This change is allowed to modify ONLY:

```
deploy/nginx/nginx.conf
openspec/changes/fix-nginx-admin-trailing-slash/**
openspec/specs/frontend-routing/spec.md    (via archive at merge time; delta lives under changes/)
```

This change MUST NOT touch:

```
web/admin/**                                (reserved for future admin SPA changes)
web/customer/**
services/**
packages/**
database/**
docker-compose.yml                          (reserved for fix-dev-stack-auto-apply-migrations)
.env.example                                (reserved for fix-dev-stack-auto-apply-migrations)
scripts/**                                  (reserved for fix-dev-stack-auto-apply-migrations)
openspec/specs/docker-dev-env/**            (reserved for sibling change)
openspec/specs/database-setup/**
```

If during implementation the agent discovers a required change outside the lane (e.g. the existing `location /admin` block has a trailing-slash bug in `proxy_pass` that the fix can't route around), STOP and escalate to the user. Do not broaden the diff silently.
