## 1. Vite base path

- [ ] 1.1 PREREQ [web-admin] Bring up the dev stack locally and confirm the broken baseline: `curl -sI http://localhost:${NGINX_PORT}/admin/` returns 200 HTML, but the subsequent asset fetch (e.g. `/admin/src/main.tsx`) returns 404. Record the exact failing URL in the task log so the verify step at the bottom has a baseline.
- [ ] 1.2 IMPL [web-admin] In `web/admin/vite.config.ts`, add `base: '/admin/'` to the `defineConfig({...})` options object. Do not touch `resolve`, `plugins`, or `server.port`. Commit as a single-line addition.
- [ ] 1.3 VERIFY [web-admin] Restart the dev stack (`docker compose restart web-admin nginx`) and re-fetch `curl -sI http://localhost:${NGINX_PORT}/admin/src/main.tsx`. Expect 200 (or a Vite-style redirect, not 404). Direct access to `http://localhost:${WEB_ADMIN_PORT}/` is expected to now fail — record this in the task log as a known trade-off.

## 2. Router basename

- [ ] 2.1 IMPL [web-admin] In `web/admin/src/App.tsx`, change `<BrowserRouter>` to `<BrowserRouter basename="/admin">`. No other changes to `App.tsx` — do NOT reorder imports, do NOT touch `<Routes>` or any `<Route>` element, do NOT rename anything.
- [ ] 2.2 VERIFY [web-admin] Reload `http://localhost:${NGINX_PORT}/admin/` and confirm: (a) the dashboard route renders, (b) clicking the nav link to `/menu` results in the URL becoming `/admin/menu` and the Menu page rendering, (c) a hard reload on `/admin/menu` still renders the Menu page (not the dashboard and not a 404).

## 3. Nginx inspection (follow-up gate)

- [ ] 3.1 VERIFY [web-admin] Re-read `deploy/nginx/nginx.conf` lines 26-32. Confirm `proxy_pass http://admin;` has no trailing slash, which preserves the `/admin` prefix in the upstream request. If a change is needed here, STOP and escalate to the user before editing — nginx edits are out of lane unless the broken behavior is concretely reproduced and attributed to the conf file.

## 4. End-to-end verification

- [ ] 4.1 VERIFY [web-admin] From the host, run three `curl` checks and record the HTTP status:
    - `curl -sI http://localhost:${NGINX_PORT}/admin/` → expect 200
    - `curl -sI http://localhost:${NGINX_PORT}/admin/menu` → expect 200
    - `curl -sI http://localhost:${NGINX_PORT}/admin/nonexistent-page` → expect 200 (SPA catch-all renders 404 component) or whatever the SPA's 404 behavior is; record the actual status either way.
- [ ] 4.2 VERIFY [web-admin] Open the admin SPA in a real browser via `http://localhost:${NGINX_PORT}/admin/`, log in (after running the initial admin seed), navigate to every top-level page (`/admin/`, `/admin/orders`, `/admin/menu`, `/admin/users`, `/admin/promos`, `/admin/settings`), and confirm each renders without assets 404ing in the DevTools Console.
- [ ] 4.3 VERIFY [web-admin] From the same browser session, confirm that API calls to `/api/v1/admin/menu/*` still succeed — i.e. the admin base path affects only static asset URLs, not API URLs. If any API call is going out to `/admin/api/v1/...`, that is a bug and MUST be surfaced to the user (likely indicates a hard-coded absolute URL in an API client file that needs updating in a follow-up change).
