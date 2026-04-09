## Why

Auth flow is completely untestable in Docker Compose. Three infrastructure bugs block all manual testing:

1. **Vite proxy ECONNREFUSED** — `web-customer` container proxies `/api` to `localhost:8000`, but `localhost` inside the container is the container itself, not `core-api`. Every API call fails with "Network error".
2. **Nginx crash on startup** — nginx resolves `core-api:8000` upstream at config parse time, but `core-api` starts after nginx (depends on postgres/redis healthcheck). Nginx exits with `host not found in upstream`.
3. **Postgres healthcheck spam** — `pg_isready -U aura` checks database named after user (`aura`), but the actual DB is `aura_coffee`. Logs flooded with `FATAL: database "aura" does not exist` every 5 seconds. Non-blocking but noisy.

Additionally, the `HomePage` route is not wrapped in `ProtectedRoute`, so opening `/` does not redirect to `/login` as the test plan expects.

4. **sms-worker task not discovered** — `autodiscover_tasks(["sms_worker.tasks"])` only loads `tasks/__init__.py`, which registers `health_check` but does not import `tasks/otp.py`. The `send_otp_sms` task is invisible to Celery, so OTP messages are silently dropped.

## What Changes

- **[docker]** Fix Vite proxy target: `localhost:8000` → `core-api:8000` in `vite.config.ts`
- **[docker]** Add `depends_on: core-api` to nginx service in `docker-compose.yml`
- **[docker]** Fix postgres healthcheck: `pg_isready -U aura` → `pg_isready -U aura -d aura_coffee`
- **[web-customer]** Wrap `HomePage` route in `ProtectedRoute` so `/` redirects unauthenticated users to `/login`
- **[sms-worker]** Import `send_otp_sms` in `tasks/__init__.py` so Celery discovers it

## Non-Goals

- No changes to nginx.conf itself — the upstream config is correct, just needs core-api to be ready
- No env-variable abstraction for Vite proxy target — local non-Docker dev is not a current workflow
- No auth logic changes — this is purely routing and infrastructure
- No migration or schema changes

## MVP Phase

Phase 0 bugfix (blocks Phase 1 Auth testing)

## Capabilities

### New Capabilities
<!-- None — this is a bugfix -->

### Modified Capabilities
- `docker-dev-env`: Vite proxy resolves correctly inside Docker network; nginx starts reliably; healthcheck logs clean
- `auth-ui`: Root route `/` now requires authentication, matching test plan expectations

## Impact

- **Files:** `docker-compose.yml`, `web/customer/vite.config.ts`, `web/customer/src/App.tsx`
- **Services:** web-customer (proxy fix), nginx (startup order), postgres (healthcheck), web-customer (route protection)
- **Risk:** Low — all changes are config/routing, no business logic affected
