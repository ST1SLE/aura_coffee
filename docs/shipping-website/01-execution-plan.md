# Aura Coffee Website Shipping Execution Plan

## Scope

Ship Aura Coffee as a real public website for customers in Russia:

- Customer web ordering at `https://DOMAIN/`.
- Staff/admin panel at `https://DOMAIN/admin/`.
- Online prepayment through YuKassa.
- SMS OTP and status notifications through SMS.ru.
- Delivery address suggest/geocode through Yandex Maps.
- PostgreSQL and Redis running privately on the production host.
- Backups, monitoring, rollback, and launch verification in place.

Out of scope for the first launch:

- Native mobile apps.
- Multi-location or multitenant hosting.
- Managed delivery provider integrations.
- Re-architecting into Kubernetes or multi-server deployment.
- Public database access from outside the host.

## Required Project Context

Read these before implementation packets:

- `AGENTS.md` for invariants, GRACE rules, and production safety gates.
- `docs/PRODUCT_DESIGN_DOCUMENT.md` for PDD invariants and external API rules.
- `docs/technology.xml` for the intended same-origin nginx/Compose shape.
- `docs/development-plan.xml` for module boundaries.
- `docs/verification-plan.xml` for required LDD markers and redaction gates.
- `docker-compose.yml`, `.env.example`, and `deploy/nginx/nginx.conf` for current
  dev deployment shape.
- `services/core-api/src/core_api/settings.py`,
  `services/payment-worker/src/payment_worker/settings.py`, and
  `services/sms-worker/src/sms_worker/settings.py` for runtime safety rails.
- `docs/phase6_manual_test_scenarios.md` for manual flow coverage and provider
  caveats.

## Invariants And Hard Gates

- INV-001: orders must be prepaid online through YuKassa before kitchen work.
- INV-002: all mutations require server-side auth and role checks.
- INV-004: payment, loyalty, promo, refund, and compensation paths must stay
  atomic.
- INV-008: delivery radius validation must remain server-side with Yandex
  geocoding when coordinates are absent.
- INV-012: OTP SMS rate limits must prevent SMS bombing and cost blowups.
- INV-013: phone, name, address, OTP, JWT, passwords, API keys, webhook bodies,
  and payment details must not appear in logs.
- INV-015: secrets must only live in environment variables or server secret
  storage, never in Git.
- INV-016: payment, order, delivery, OTP, user, and promocode state transitions
  must remain explicit PDD transitions only.

GRACE LDD assertions are required for implementation packets touching:

- auth, OTP, SMS, PII, logging, or redaction;
- YuKassa payment creation, webhook processing, refunds, or webhook ingress;
- order/payment/delivery state transitions;
- atomic transaction boundaries;
- required log markers listed in `docs/verification-plan.xml`.

Documentation-only packets do not require LDD.

## Decisions To Make Before Implementation

| Decision | Recommended default | Why it matters |
|----------|---------------------|----------------|
| Hosting | One Russian VPS, Docker Compose, local PostgreSQL/Redis volumes | Lowest drift from current repo and simplest private DB networking. |
| Domain | One canonical domain, optional `www` redirect | YuKassa webhooks, TLS, CORS, cookies, and Yandex restrictions need final domain. |
| TLS | nginx + Certbot/Let's Encrypt on host | YuKassa webhooks require public HTTPS on accepted ports. |
| Production Compose | Add `docker-compose.production.yml` overlay | Keeps local dev flow untouched while hardening production. |
| Frontend serving | Static production builds served by nginx | Removes Vite dev servers from production. |
| Secrets | `/opt/aura-coffee/.env.production`, not committed | Satisfies INV-015 and avoids placeholder boot. |
| Media assets | Serve `/media/menu/` from a read-only server directory or baked static assets | Admin stores paths only; binary upload is out of v1. |
| Backups | Daily PostgreSQL dumps plus restore drill | Local DB on VPS is simple but must have reliable recovery. |
| Fiscalization | Confirm YuKassa 54-FZ receipt path before live payment acceptance | Payment launch can be blocked by legal/accounting compliance. |
| Personal data | Confirm 152-FZ operator and hosting obligations | App stores phone, names, and addresses. |

## Execution Packets

### Packet 0: Launch Inputs And Account Readiness

Owner: user plus Codex for checklists.

Deliverables:

- Final domain name.
- Russian VPS or cloud provider selected.
- Production contact email for TLS and provider accounts.
- YuKassa shop credentials and test/live mode access.
- YuKassa webhook configuration path agreed:
  `https://DOMAIN/api/webhooks/yukassa`.
- YuKassa fiscal receipt plan confirmed with accountant.
- SMS.ru account funded, `api_id` created, sender name requested/approved.
- Yandex Maps keys created with Geosuggest and Geocoder enabled.
- Legal/accounting confirmation for 152-FZ and 54-FZ duties.

Acceptance:

- No code changes yet.
- `02-production-configuration.md` checklist has concrete values or explicit
  TODO markers.

Rollback:

- None. This packet is account/config discovery only.

### Packet 1: Production Compose Overlay

Owner: Codex.

Likely files:

- `docker-compose.production.yml`
- `.env.production.example`
- `deploy/production/` helper files if needed
- `README.md` or this directory if command docs need updates

Implementation:

- Build Python services from `target: base`, not `dev`.
- Remove source bind mounts from production services.
- Remove public host ports for PostgreSQL, Redis, core-api, payment-webhook, and
  frontend internals.
- Publish only nginx on `80` and `443` or publish nginx on internal HTTP if TLS
  terminates at a host nginx.
- Add restart policies.
- Add production healthchecks where feasible.
- Keep `db-migrate` one-shot and make seed behavior production-safe.
- Ensure `AURA_ENV=production` refuses placeholder secrets.

Verification:

- `scripts/production/compose.sh .env.production.example config`
- Build all production images.
- Run production overlay locally with fake/log external backends first.
- Confirm Postgres/Redis are not published to `0.0.0.0`.
- Confirm `/health` works through nginx.

LDD:

- Not required if this packet only changes deployment files.

Rollback:

- Stop production overlay and return to local `docker-compose.yml`.

### Packet 2: Static Frontend Production Serving

Owner: Codex.

Likely files:

- `web/customer/Dockerfile` or `deploy/frontend/` Dockerfile
- `web/admin/Dockerfile` or `deploy/frontend/` Dockerfile
- `docker-compose.production.yml`
- `deploy/nginx/nginx.production.conf`

Implementation:

- Build customer with `npm ci && npm run build`.
- Build admin with `npm ci && npm run build`.
- Serve `web/customer/dist` at `/`.
- Serve `web/admin/dist` at `/admin/`.
- Preserve admin basename `/admin/`.
- Ensure API calls stay same-origin under `/api`.
- Ensure `/media/menu/` has a deterministic production source.

Verification:

- `npm run build` in `web/customer`.
- `npm run build` in `web/admin`.
- Production nginx serves `/`, `/admin/`, `/api/health` or `/health`.
- Direct SPA deep links reload correctly.

LDD:

- Not required if only frontend build/serving changes.

Rollback:

- Revert production static-serving changes or switch production overlay back to
  Vite containers for emergency internal testing only.

### Packet 3: Production Nginx, TLS, And Webhook Ingress

Owner: Codex plus user for DNS.

Likely files:

- `deploy/nginx/nginx.production.conf`
- `docker-compose.production.yml`
- `docs/shipping-website/03-launch-runbook.md`

Implementation:

- Set canonical `server_name`.
- Redirect HTTP to HTTPS after certificate issuance.
- Terminate TLS with Certbot certificates or host-level TLS proxy.
- Keep exact `/api/webhooks/yukassa` route before generic `/api/`.
- Overwrite forwarded IP headers on webhook route.
- Add request body limits and timeout settings.
- Add static caching for frontend assets.
- Decide HSTS after successful HTTPS smoke.

Verification:

- `curl -I http://DOMAIN/` redirects to HTTPS.
- `curl -I https://DOMAIN/` returns 200.
- `curl https://DOMAIN/health` returns `{"status":"ok", ...}`.
- `tests/test_nginx_webhook_route.py` passes if route tests apply to the new
  config.
- YuKassa dashboard webhook test reaches payment-webhook.

LDD:

- Required only if webhook verification or payment-worker code changes. Not
  required for nginx-only route/config changes, but route regression tests are
  required.

Rollback:

- Restore previous nginx config and reload nginx/container.
- Temporarily disable live YuKassa webhook in provider dashboard if ingress is
  misrouting.

### Packet 4: Production Environment And Secret Safety

Owner: user for real secret values, Codex for templates and checks.

Likely files:

- `.env.production.example`
- `scripts/production/validate-env.sh` or equivalent
- docs in this directory

Implementation:

- Create a no-secret example with every required variable.
- Add validation script that checks required variables are present and obvious
  dev placeholders are absent.
- Document secret generation commands.
- Ensure `CORS_ORIGINS=https://DOMAIN`.
- Ensure `YUKASSA_BACKEND=live`, `SMS_BACKEND=smsru`,
  `YUKASSA_BASE_URL=https://api.yookassa.ru/v3`.
- Do not commit real `.env.production`.

Verification:

- Run env validator against a sanitized production-like file.
- Boot production containers with placeholder-free dummy values in a private
  dry-run where external calls are not executed.
- Confirm core-api, payment-worker, and sms-worker fail fast on unsafe secrets.

LDD:

- Not required for env templates. Required if code safety rails change.

Rollback:

- Revert env template/script changes. Server real env remains outside Git.

### Packet 5: Backups, Restore, And Operations

Owner: Codex.

Likely files:

- `scripts/production/backup-postgres.sh`
- `scripts/production/restore-postgres.sh`
- `scripts/production/deploy.sh`
- `scripts/production/check-readiness.sh`
- docs in this directory

Implementation:

- Add Postgres backup script using `pg_dump` from the database container.
- Store timestamped backups outside the repo, for example
  `/var/backups/aura-coffee/postgres`.
- Add retention policy.
- Add restore drill instructions to a separate database or staging stack.
- Add disk, volume, and container health checks.
- Add log rotation guidance.

Verification:

- Run backup on a non-production or staging stack.
- Restore into a fresh test database and run migration/readiness checks.
- Confirm backup files do not contain secrets in names or logs.

LDD:

- Not required unless runtime code changes.

Rollback:

- Disable cron/systemd timer and keep last successful backup.

### Packet 6: Provider Integration Dry Run

Owner: user plus Codex.

Implementation:

- Yandex: verify Suggest and Geocoder with production key restrictions.
- SMS.ru: send OTP to controlled phone and verify logs are redacted.
- YuKassa: create test payment, process webhook, process cancellation/refund.
- Fiscalization: verify receipt status in YuKassa or chosen fiscal path.

Verification:

- Real SMS OTP auth works for a controlled number.
- Yandex manual typed address geocodes and validates in delivery radius.
- `payment.succeeded` webhook transitions payment/order correctly.
- Repeated webhook is idempotent.
- Invalid webhook source/signature is rejected.
- Refund path works and creates the expected refund/payment state.

LDD:

- Required if fixes are needed in auth, SMS, payment, refunds, PII/logging, or
  state transitions.

Rollback:

- Set provider dashboards back to test mode or disable webhook.
- Revert `SMS_BACKEND`/`YUKASSA_BACKEND` in staging, never in live without a
  written operator decision.

### Packet 7: Full Launch Verification And Cutover

Owner: user plus Codex.

Implementation:

- Freeze launch branch.
- Take final database backup if migrating existing data.
- Deploy production overlay.
- Run readiness checks.
- Run controlled end-to-end order.
- Monitor logs for 30-60 minutes.

Verification:

- Public pages load on mobile and desktop.
- Customer signup/login works with SMS OTP.
- Public menu, cart, checkout, and order detail work.
- YuKassa payment redirects and webhook moves order to `PAID`.
- Staff admin login works.
- Barista/courier roles see only allowed surfaces.
- Refund/cancel operational path is proven.
- Logs contain no raw PII or secrets.

LDD:

- Required only for code changes made during the launch packet. Runtime launch
  smoke should still inspect LDD markers and redaction-sensitive logs.

Rollback:

- Restore previous image tag/config.
- Disable YuKassa webhook temporarily if payment ingress is unsafe.
- Restore latest database backup only if data corruption occurred and the
  business accepts data loss since backup time.

## Major Failure Modes

| Failure | Preventive control |
|---------|--------------------|
| DB exposed to internet | Production Compose must not publish PostgreSQL/Redis ports. Firewall denies all but SSH/HTTP/HTTPS. |
| Placeholder secrets in production | `AURA_ENV=production` plus env validation and service safety rails. |
| Vite dev servers exposed | Static production builds served by nginx. |
| YuKassa webhook cannot reach us | Public HTTPS, accepted port, exact route, DNS ready before dashboard switch. |
| Webhook accepted from attacker | IP whitelist and/or signature verification; forwarded IP headers overwritten by nginx. |
| SMS cost spike | OTP rate limits, SMS.ru daily limit, provider dashboard alerts. |
| Yandex key leaks | Server-side proxy only; key restrictions; no frontend env exposure. |
| Delivery orders bypass geocode | Preserve PDD rule: Geocoder unavailable blocks delivery, Suggest failure only degrades UX. |
| Legal launch blocker | 152-FZ and 54-FZ review before accepting real customer orders. |
| Media files 404 | Define `/media/menu/` deploy source and include asset smoke. |
| No recovery path | Daily backups plus restore drill before go-live. |

## Smallest Viable Launch

The smallest safe launch is:

1. One Russian VPS with Docker and Compose.
2. One production domain with TLS.
3. Production Compose overlay with only nginx public.
4. Static customer/admin frontend served by nginx.
5. Internal PostgreSQL and Redis volumes.
6. Real SMS.ru, YuKassa, and Yandex env values.
7. Daily Postgres backups and a tested restore path.
8. Manual launch checklist with one controlled real order.

Anything less is not production-safe for real customers.
