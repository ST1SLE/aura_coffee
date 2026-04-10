## 1. Baseline reproduction

- [x] 1.1 PREREQ [dev-env] With the dev stack up, run `curl -o /dev/null -w '%{http_code}\n' http://localhost:${NGINX_PORT}/admin` and record the result. Expect `404`. Then run `curl -o /dev/null -w '%{http_code}\n' http://localhost:${NGINX_PORT}/admin/` and record the result. Expect `200`. This is the broken baseline.
- [x] 1.2 PREREQ [dev-env] Open `deploy/nginx/nginx.conf` and locate the existing `location /admin { proxy_pass http://admin; }` prefix-match block. Record its line number. The new exact-match block will be inserted immediately before it.

## 2. Nginx config edit

- [x] 2.1 IMPL [nginx] In `deploy/nginx/nginx.conf`, add a new block `location = /admin { return 301 /admin/; }` immediately before the existing `location /admin { proxy_pass http://admin; }` block. Preserve all surrounding whitespace and the order of every other `location` directive. Do NOT edit the existing `location /admin` block, the `location /api/` block, the `location /` block, or any `upstream` directive.
- [x] 2.2 VERIFY [nginx] Run `docker compose exec nginx nginx -t` and confirm the config parses cleanly (`syntax is ok` / `test is successful`). If it fails, STOP and do not reload — fix the syntax first.

## 3. Reload and smoke-test

- [x] 3.1 IMPL [nginx] Reload nginx without restarting the container: `docker compose exec nginx nginx -s reload`. Confirm no errors in `docker compose logs nginx --tail 20`.
- [x] 3.2 VERIFY [nginx] Run `curl -o /dev/null -w '%{http_code} %{redirect_url}\n' http://localhost:${NGINX_PORT}/admin` and confirm the response is `301 /admin/` (or `301 http://localhost:${NGINX_PORT}/admin/` depending on nginx's redirect form). Not 404, not 200, not 308.
- [x] 3.3 VERIFY [nginx] Run `curl -L -o /dev/null -w '%{http_code}\n' http://localhost:${NGINX_PORT}/admin` (with `-L` to follow redirects) and confirm the final response is `200`. This proves the full flow: bare path → 301 → canonical path → SPA shell.
- [x] 3.4 VERIFY [nginx] Run `curl -o /dev/null -w '%{http_code}\n' http://localhost:${NGINX_PORT}/admin/` and confirm it still returns `200` directly, with NO redirect. This proves the trailing-slash form is unaffected by the new exact-match block.
- [x] 3.5 VERIFY [nginx] Run `curl -o /dev/null -w '%{http_code}\n' http://localhost:${NGINX_PORT}/` and confirm the customer SPA still returns `200`. This proves the exact-match `= /admin` did not shadow the root `location /` block.

## 4. Deep-link and browser verification

- [x] 4.1 VERIFY [browser] Open `http://localhost:${NGINX_PORT}/admin` in a browser address bar, press Enter, and confirm (a) the address bar updates to `http://localhost:${NGINX_PORT}/admin/`, (b) the admin SPA dashboard renders, (c) DevTools Network tab shows zero 404s on asset requests under `/admin/`.
- [x] 4.2 VERIFY [browser] Navigate to `http://localhost:${NGINX_PORT}/admin/menu` and press reload (hard-refresh, Ctrl+Shift+R). Confirm the Menu page renders — NOT the dashboard, NOT a 404 — proving React Router's `basename="/admin"` still correctly interprets the sub-route and the new redirect block does not interfere with deep links under `/admin/`.
- [x] 4.3 VERIFY [browser] In DevTools, confirm that an admin API call (e.g. `listCategories()`) still targets `/api/v1/admin/menu/categories` — NOT `/admin/api/v1/admin/menu/categories`. The redirect block MUST NOT affect API routing.

## 5. Test-scenario doc update

- [x] 5.1 VERIFY [docs] Re-read the Phase 2 manual test scenario doc that originally instructed the developer to open `http://localhost:8240/admin`. Confirm that URL now works end-to-end through the browser (via 301 → dashboard). No edit to the doc is strictly required — the doc becomes correct by virtue of the fix — but record in the task log that the scenario passes as written.
