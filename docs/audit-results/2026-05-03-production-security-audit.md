# Aura Coffee Production Security Audit

Date: 2026-05-03
Scope: read-only production-readiness security audit for server launch.

No implementation files were changed. This report was produced from source/config
inspection, dependency advisory checks, and parallel subagent review.

## Executive Summary

Aura Coffee is not ready to expose as a production system with the current
Compose/nginx shape. The largest blockers are deployment-boundary issues rather
than ordinary application bugs: the current stack publishes internal services,
serves Vite dev servers, exposes Redis/Postgres/Core API host ports, and has no
production nginx/TLS overlay. There are also payment/SMS hardening gaps that
should be fixed before real money or customer PII flows through the system.

## 2026-05-09 Runtime Status Addendum

This audit is a historical 2026-05-03 snapshot. The closed-staging VPS has since
been moved to a production-shaped deployment:

- Current VPS release:
  `543c08d8407b-codex-cart-prune-20260509T151010Z`, built from a clean Git
  archive at `543c08d fix: prune stale cart lines`.
- Public entry points are nginx `80/443`; Core API, payment webhook, workers,
  Postgres, and Redis are internal Docker services.
- TLS, staging access protection, `/media/menu/` serving, no-query production
  access logs, and `.dockerignore` are now present.
- Closed staging intentionally remains in mock provider mode:
  `YUKASSA_BACKEND=fake` and `SMS_BACKEND=log`.
- The validated menu/media catalog is loaded for closed staging, but owner
  approval is still required before public launch.

Status interpretation:

- Findings 1, 4, 8, 12, 14, and the staging part of 15 are mitigated for the
  current closed-staging deployment.
- Finding 2 is mitigated at the deployment boundary because the payment webhook
  is not publicly published, but live YuKassa invalid-source/signature drills
  are still required.
- Finding 3 remains a public-launch blocker by design: fake/log providers are
  acceptable only for closed staging and must not be used for public ordering.
- Findings 5, 6, 9, 10, and 11 remain hardening items before broad public use.
- Finding 7 is partly mitigated because nginx access logs omit query strings;
  the app still uses GET map endpoints, so browser/proxy history exposure is
  not fully eliminated.

See `docs/audit-results/2026-05-09-runtime-readiness-sync.md` for the current
pending and good-to-have backlog.

Good signs:

- Core API route coverage check found all 75 `/api/*` routes represented in
  either `ROUTE_MATRIX` or `PUBLIC_ROUTES`.
- Core API secret safety rails reject weak JWT/encryption secrets outside
  `AURA_ENV=dev`.
- Customer refresh token handling is HttpOnly-cookie based and customer access
  token storage is in-memory.
- `npm audit --omit=dev` found zero known production dependency advisories for
  both frontends.
- `pip-audit` found zero known advisories in the resolved Python dependencies
  for core-api, payment-worker, sms-worker, and shared.

## Critical Findings

### 1. Current Compose Stack Is Dev-Only And Exposes Internals

Evidence:

- `docker-compose.yml:8-21` publishes Postgres and Redis host ports.
- `docker-compose.yml:73-85` publishes Core API, uses `target: dev`, bind mounts
  source/tests, and runs `uvicorn --reload`.
- `docker-compose.yml:195-215` runs customer/admin through `npm install &&
  npm run dev -- --host` and publishes Vite ports.
- `docker-compose.yml:217-227` publishes nginx but still proxies to Vite dev
  servers.
- `docs/shipping-website/README.md:30-37` already describes the current local
  stack as development-shaped.

Impact:

If deployed as-is, database, Redis/Celery broker, Core API, frontend dev
servers, and nginx can all become public entry points. Redis exposure is
especially severe because it stores sessions, OTP state, Celery broker data, and
payment/SMS task queues.

Required before launch:

- Add a production Compose overlay.
- Publish only nginx on public ports.
- Keep Postgres, Redis, Core API, webhook, workers, and frontend internals on
  private Docker networks only.
- Use production Docker targets/images, no bind mounts, no `--reload`, no Vite
  dev servers.

### 2. Direct Payment Webhook Spoofing Is Possible If The Override Is Shipped

Evidence:

- `docker-compose.override.yml:2-4` publishes `payment-webhook` directly.
- `services/payment-worker/src/payment_worker/webhook.py:105-110` trusts the
  first `X-Forwarded-For` value when present.
- `deploy/nginx/nginx.conf:31-36` correctly overwrites `X-Forwarded-For` only
  on the canonical nginx webhook route.
- `services/payment-worker/src/payment_worker/webhook.py:179-186` makes
  signature verification optional; no secret means every signature is accepted.
- `.env.example:42-45` whitelists local/docker names and leaves
  `YUKASSA_WEBHOOK_SIGNATURE_SECRET` empty.

Impact:

A direct request to the published webhook port can bypass nginx and spoof
`X-Forwarded-For`. If the attacker knows or obtains a `yukassa_payment_id`, they
can attempt forged `payment.succeeded` or `payment.canceled` events.

Required before launch:

- Do not publish `payment-webhook` directly in production.
- Ensure only nginx reaches it internally.
- Require a real webhook signature secret in production, or treat IP whitelist
  as the only protection only if direct access is impossible and YuKassa source
  IPs are exact.
- Add production tests/probes proving a direct host port is not open.

### 3. Fake/Log Providers Are Not Barred By Production Runtime Guards

Evidence:

- `.env.example:26` defaults `SMS_BACKEND=log`.
- `.env.example:38` defaults `YUKASSA_BACKEND=fake`.
- `services/payment-worker/src/payment_worker/settings.py:69-77` allows
  `fake` mode without checking `AURA_ENV`.
- `services/payment-worker/src/payment_worker/yukassa_fake.py:97-107` creates
  fake payment ids and schedules fake callbacks that can drive success/cancel
  webhooks.
- `services/sms-worker/src/sms_worker/settings.py:42-52` allows `log` mode
  without checking `AURA_ENV`.

Impact:

A misconfigured production environment can accept orders as paid without real
YuKassa payment, or avoid real SMS delivery. This is a launch blocker because
the code has safety rails for missing live credentials, but not for accidentally
choosing mock backends outside dev.

Required before launch:

- Add an environment guard: when `AURA_ENV=production`, require
  `YUKASSA_BACKEND=live` and `SMS_BACKEND=smsru`.
- Keep fake/log modes only for dev, test, and local staging with explicit
  non-production environment names.
- Add tests for these settings rails.

## High Findings

### 4. Redis/Celery Is A Privileged Trust Boundary But Dev Compose Publishes It

Evidence:

- `docker-compose.yml:18-21` publishes Redis.
- `.env.example:11` uses unauthenticated `redis://redis:6379/0`.
- `services/core-api/src/core_api/services/otp.py:232-238` stores OTP code state
  in Redis JSON.
- `services/core-api/src/core_api/routers/auth.py:145-149` sends clear OTP code
  as Celery task args through Redis.
- Payment/refund workers trust Celery task args for state-mutating operations.

Impact:

Public Redis exposure would allow OTP/session disclosure and task injection
against payment/SMS workers. This is fully mitigated by private networking, but
the current dev compose shape does the opposite.

Required before launch:

- No public Redis port in production.
- Consider Redis auth/TLS or at least private firewall-only access on the VPS.
- Treat Redis compromise as equivalent to account/session/payment compromise.

### 5. Payment Webhook Idempotency Is Not Atomic Under Concurrency

Evidence:

- `services/payment-worker/src/payment_worker/webhook.py:216-230` implements
  idempotency as separate `EXISTS` and later `SET`.
- `services/payment-worker/src/payment_worker/webhook.py:873-888` checks Redis,
  processes DB work, then marks the event processed.
- `services/payment-worker/src/payment_worker/webhook.py:413-417` and
  `494-498` read payment rows without row locks before state changes.

Impact:

Concurrent duplicate webhooks can both observe "not processed" and double-apply
some side effects, including notifications, inventory restoration, loyalty
reversals, or promocode decrements. Existing source-state guards reduce damage
for terminal states but do not fully serialize the event boundary.

Required before launch:

- Claim event processing atomically with Redis `SET key value NX EX` before DB
  work, with a clear recovery strategy for failed in-flight events, or store
  webhook event ids in the database with a unique constraint inside the same
  transaction.
- Use row locks on payment/order rows during webhook mutation paths.
- Add concurrency regression tests.

### 6. Admin Staff Access JWT Persists In localStorage

Evidence:

- `web/admin/src/api/client.ts:31-68` reads/writes `accessToken` in
  `localStorage`.
- `web/admin/src/pages/Login/LoginPage.tsx:62-65` stores access token and role
  hint after login.
- Refresh tokens are better: `web/admin/src/api/client.ts:70-90` keeps refresh
  tokens as HttpOnly-cookie only and clears legacy localStorage refresh tokens.

Impact:

Any XSS, malicious browser extension, or same-origin script compromise can steal
a persistent privileged staff bearer token. Customer auth is safer because its
access token is module-memory only.

Required before launch:

- Mirror customer auth: store staff access token only in memory.
- Rehydrate staff sessions through HttpOnly refresh cookie on page load.
- Add CSP and security headers to reduce XSS blast radius.

### 7. Address PII Is Sent In Query Strings

Evidence:

- `web/customer/src/api/yandex_maps.ts:78` sends suggest text as
  `/api/v1/maps/suggest?text=...`.
- `web/customer/src/api/yandex_maps.ts:119` sends geocode text as
  `/api/v1/maps/geocode?text=...`.
- `services/core-api/src/core_api/routers/yandex_maps.py:117-151` exposes
  those as GET query endpoints.
- `deploy/nginx/nginx.conf:40-45` forwards `/api/` normally; default access
  logging commonly includes query strings.

Impact:

Raw customer address text can land in browser history, nginx logs, proxy logs,
APM traces, and upstream logs. This conflicts with INV-013 treatment of full
addresses as PII.

Required before launch:

- Move suggest/geocode to POST bodies or explicitly suppress/redact access-log
  query strings for these routes.
- Avoid logging raw map queries in application, proxy, and provider diagnostics.

### 8. Nginx Has No Production TLS Or Security Header Configuration

Evidence:

- `deploy/nginx/nginx.conf:17-19` listens on HTTP with `server_name localhost`.
- No `listen 443`, certificate config, HTTPS redirect, CSP, Referrer-Policy,
  X-Content-Type-Options, frame policy, request body limit, or static asset
  caching appears in the current nginx config.
- `docs/shipping-website/02-production-configuration.md:149-166` lists TLS and
  production routes as required launch work.

Impact:

The public site would not meet payment/webhook expectations, cookie security
expectations, or basic browser hardening if this nginx config were used
directly.

Required before launch:

- Add a production nginx config with final `server_name`, TLS, HTTP->HTTPS
  redirect, static asset serving, request limits/timeouts, and security headers.
- Keep HSTS until after HTTPS smoke and rollback are proven.

## Medium Findings

### 9. Phone Hashes Are Pseudonymous, Not Anonymized

Evidence:

- `services/core-api/src/core_api/utils/crypto.py:7-9` uses raw unsalted SHA-256
  for phone lookup hashes.
- `services/sms-worker/src/sms_worker/clients/log.py:24-25` logs an unsalted
  SHA-256 phone prefix.
- `services/sms-worker/src/sms_worker/clients/smsru.py:33-34` does the same for
  SMS.ru recipient refs.

Impact:

Russian phone number space is small enough for dictionary reversal. These
values are pseudonymous identifiers, not anonymized identifiers.

Recommended fix:

- Use HMAC-SHA256 with a server-side pepper for lookup/log identifiers.
- Plan migration carefully because existing `phone_hash` values are keys for
  users and OTP rate limits.

### 10. OTP SMS Can Resend After Provider Success But Redis Status Failure

Evidence:

- `services/sms-worker/src/sms_worker/tasks/otp.py:86-93` autoretries on any
  exception.
- `services/sms-worker/src/sms_worker/tasks/otp.py:98-108` calls the SMS
  transport before updating Redis OTP status.

Impact:

If SMS.ru accepts the message but Redis status update fails, Celery can retry
the whole task and send another SMS outside the Core API rate-limit path.

Recommended fix:

- Make OTP send idempotent around a provider/message id when available, or
  split provider-send and status-write retry handling so successful sends do
  not cause duplicate delivery.
- Add tests for Redis failure after provider success.

### 11. Staff Login IP Throttling Is Not Proxy-Ready

Evidence:

- `deploy/nginx/nginx.conf:40-45` forwards `X-Forwarded-For` for `/api/`.
- `services/core-api/src/core_api/routers/staff_auth.py:103-106` rate-limits by
  `request.client.host`.
- `docker-compose.yml:85` does not set explicit uvicorn proxy trust flags.

Impact:

Behind nginx/Docker, staff login throttling may key on the proxy/container IP
instead of the real client IP, depending on uvicorn/proxy configuration. That
can over-throttle all staff or under-represent attack source diversity.

Recommended fix:

- Add explicit proxy-header trust configuration in production.
- Centralize a trusted client-IP helper that only trusts nginx-injected headers
  from known proxy hops.

### 12. `/media/menu/` Production Serving Is Undefined

Evidence:

- Menu media validation expects public paths under `/media/menu/...`.
- `deploy/nginx/nginx.conf:21-68` has no `/media/menu/` location.
- `docs/shipping-website/02-production-configuration.md:149-166` lists
  `/media/menu/` as required.

Impact:

Production menu media may 404, or operators may work around it by using legacy
external `image_url` paths, weakening privacy and mixed-content control.

Recommended fix:

- Add an explicit production `/media/menu/` route served from an approved
  read-only host path or baked static asset directory.
- Keep admin validation aligned with that source.

### 13. Legacy `image_url` Is Less Constrained Than New Media Fields

Evidence:

- `web/admin/src/pages/Menu/MenuItemFormDialog.tsx:97-107` validates new media
  paths as local `/media/menu/` paths.
- `web/admin/src/pages/Menu/MenuItemFormDialog.tsx:244` submits legacy
  `image_url` without equivalent validation.
- `web/customer/src/pages/Menu/MenuMedia.tsx:96-104` falls back to `image_url`.
- `web/customer/src/pages/Menu/MenuMedia.tsx:182-188` renders it as `<img src>`.

Impact:

Staff can configure third-party image URLs that leak customer IP/user-agent to
external hosts or cause mixed-content/resource-policy issues.

Recommended fix:

- Deprecate legacy `image_url` or validate it with the same local path allowlist.

### 14. No `.dockerignore`

Evidence:

- No `.dockerignore` exists.
- `docker-compose.yml:29-31` and similar service builds use `context: .`.
- `.gitignore:8-9` excludes `.env` from Git only, not from Docker build context.

Impact:

Local secrets, worktrees, caches, and other ignored files can be sent to Docker
build context and potentially copied into images if future Dockerfiles broaden
`COPY` patterns.

Recommended fix:

- Add `.dockerignore` covering `.env*`, `.git`, `.worktrees`, `node_modules`,
  `dist`, caches, local DBs, logs, and agent-local state.

## Low Findings

### 15. Container Hardening Is Minimal

Evidence:

- Only Postgres and Redis have healthchecks in `docker-compose.yml`.
- App services have no production `restart` policy, non-root runtime user,
  `read_only`, `cap_drop`, or `security_opt`.
- Python Dockerfiles do not set a non-root `USER`.

Impact:

This is normal for an early dev stack but should be improved for internet
exposure.

Recommended fix:

- Add restart policies and service healthchecks in the production overlay.
- Run app containers as non-root where practical.
- Drop Linux capabilities and make filesystems read-only where feasible.

## Clean Checks And Negative Findings

- RBAC route coverage script found no missing `/api/*` route in
  `ROUTE_MATRIX`/`PUBLIC_ROUTES`.
- No `dangerouslySetInnerHTML`, `eval`, or `new Function` was found in customer
  or admin source.
- Customer auth stores access tokens in memory and clears legacy refresh tokens
  from localStorage.
- Frontend production dependency audits:
  - `web/customer`: zero known production advisories.
  - `web/admin`: zero known production advisories.
- Python dependency audits:
  - `services/core-api`: zero known advisories.
  - `services/payment-worker`: zero known advisories.
  - `services/sms-worker`: zero known advisories.
  - `packages/shared`: zero known advisories.
- `.env`, worktree `.env` files, and local worktrees are ignored by Git.

## Commands Run

Representative commands:

```bash
git status --short
rg --files -g '!*node_modules*' -g '!*.mp4' -g '!*.png' -g '!*.jpg' -g '!*.jpeg' -g '!*.webp'
rg -n --hidden -g '!.git' -g '!node_modules' -g '!dist' -g '!build' -g '!*.mp4' -g '!*.png' -g '!*.jpg' -g '!*.jpeg' -g '!*.webp' "(SECRET|PASSWORD|TOKEN|API_KEY|PRIVATE_KEY|BEGIN (RSA|OPENSSH|EC|DSA)|JWT|DATABASE_URL|REDIS_URL|SMSRU|YANDEX|YOO|YUKASSA|SENTRY|DEBUG)"
rg -n "(CORSMiddleware|allow_origins|allow_credentials|docs_url|redoc_url|openapi_url|TrustedHost|HTTPSRedirect|csrf|secure|httponly|samesite)" services packages web deploy docker-compose.yml docker-compose.override.yml .env.example pyproject.toml
rg -n "(dangerouslySetInnerHTML|innerHTML|eval\\(|new Function|localStorage|sessionStorage|document\\.cookie|console\\.(log|debug|info)|VITE_|import\\.meta\\.env|Authorization|Bearer)" web/customer web/admin services/core-api/src services/payment-worker/src services/sms-worker/src
npm audit --omit=dev --json
uvx --python /usr/bin/python3 pip-audit -f json --progress-spinner off services/core-api
uvx --python /usr/bin/python3 pip-audit -f json --progress-spinner off services/payment-worker
uvx --python /usr/bin/python3 pip-audit -f json --progress-spinner off services/sms-worker
uvx --python /usr/bin/python3 pip-audit -f json --progress-spinner off packages/shared
AURA_ENV=dev DATABASE_URL=sqlite:// REDIS_URL=redis://localhost:6379/0 JWT_SECRET_KEY=change-me-to-random-secret ENCRYPTION_KEY=0000000000000000000000000000000000000000000000000000000000000000 PYTHONPATH=packages/shared/src:services/core-api/src uv run --project services/core-api python - <<'PY'
from core_api.main import app
from core_api.rbac_matrix import ROUTE_MATRIX, PUBLIC_ROUTES
routes = []
for r in app.routes:
    path = getattr(r, "path", None)
    methods = getattr(r, "methods", None)
    if not path or not methods:
        continue
    for m in sorted(methods):
        if m in {"HEAD", "OPTIONS"}:
            continue
        routes.append((m, path))
known = set(ROUTE_MATRIX) | set(PUBLIC_ROUTES)
print([x for x in routes if x[1].startswith("/api/") and x not in known])
PY
```

## GRACE / LDD Gate

This was a read-only audit. No implementation changed, so no LDD assertions were
required for this audit packet.

Follow-up fixes will require LDD assertions if they touch:

- payment webhook verification/idempotency/state transitions;
- fake/live payment settings guards;
- SMS/OTP retries, rate limits, or redaction;
- auth token/session handling;
- PII logging or address query handling;
- any required marker in `docs/verification-plan.xml`.
