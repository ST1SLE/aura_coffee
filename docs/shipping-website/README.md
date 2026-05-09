# Shipping Aura Coffee To The Public Internet

This directory is the execution hub for making Aura Coffee reachable by real
customers in production.

The target shape is a same-origin public website behind nginx:

- `https://DOMAIN/` serves the customer SPA.
- `https://DOMAIN/admin/` serves the staff SPA.
- `https://DOMAIN/api/` proxies to `core-api`.
- `https://DOMAIN/api/webhooks/yukassa` proxies to `payment-webhook`.
- PostgreSQL and Redis stay private inside the Docker Compose network.
- SMS.ru, YuKassa, and Yandex Maps are real external providers configured only
  through production environment variables.

## Documents

| File | Use |
|------|-----|
| [01-execution-plan.md](01-execution-plan.md) | The phase-by-phase plan we will execute together. |
| [02-production-configuration.md](02-production-configuration.md) | Concrete production env, domain, nginx, Compose, backup, and provider checklist. |
| [03-launch-runbook.md](03-launch-runbook.md) | Dry-run, staging, go-live, rollback, and post-launch verification commands. |
| [04-provider-integration-rollout-plan.md](04-provider-integration-rollout-plan.md) | Step-by-step plan for enabling and testing Yandex Maps, SMS.ru, and YuKassa. |
| [05-stage-0-economical-prerequisites.md](05-stage-0-economical-prerequisites.md) | Economical acquisition guide for Stage 0 domain, VPS, provider, test phone, fiscal, and legal inputs. |
| [menu-catalog/](menu-catalog/) | Stage 3 menu/media CSV packet and validation instructions. |
| [../audit-results/2026-05-09-runtime-readiness-sync.md](../audit-results/2026-05-09-runtime-readiness-sync.md) | Current runtime status delta, remaining launch blockers, and UX good-to-have backlog. |

## Current Production Readiness Summary

The repo already has the right architectural direction: a same-origin monolith
behind nginx with `core-api`, customer/admin SPAs, workers, PostgreSQL, and
Redis deployed with Docker Compose.

The local stack remains development-shaped by design:

- Compose uses dev Docker targets and bind mounts source into containers.
- Customer/admin SPAs run through Vite dev servers.
- nginx listens on HTTP with `server_name localhost`.
- PostgreSQL and Redis publish host ports for local development.
- `.env.example` contains dev-safe defaults and placeholder credentials.

Shipping uses a production overlay rather than mutating the local workflow.

Stage 1 production skeleton artifacts now exist in repo:

- `docker-compose.production.yml`
- `.env.production.example`
- `deploy/nginx/nginx.production.conf`
- `deploy/nginx/Dockerfile`
- `scripts/production/validate-env.sh`
- `scripts/production/compose.sh`

## Roadmap From Current State To Production

Use this as the top-level launch map. The detailed packet docs below explain
each step, but this is the exact order we should follow together.

### Stage 0: Launch Inputs

Owner: user, with Codex turning decisions into checklists and config templates.

We need these before production engineering can become concrete:

- Canonical domain or staging subdomain. Current values:
  `aura-coffee-bakery.ru` and `staging.aura-coffee-bakery.ru` on Beget.
- VPS or hosting provider, preferably a Russian-region VPS for the first launch.
  Current staging VPS: `212.8.226.214`, Ubuntu 24.04.4 LTS.
- Production contact email for TLS/provider accounts.
- YuKassa test and live shop access.
- SMS.ru account with balance, `api_id`, and spending limits.
- Yandex Maps keys with Geosuggest/Suggest and Geocoder enabled.
- Controlled real phone number for OTP tests.
- Owner/accountant decision for 54-FZ receipts and refund procedure.
- Legal owner for privacy, consent, public offer, refund policy, and 152-FZ
  checks.

Gate:

- DNS/VPS path is known.
- Webhook URL is fixed as `https://DOMAIN/api/webhooks/yukassa`.
- Provider dashboard access exists or has a named owner.

Current status:

- Domain and staging subdomain are bought on Beget.
- `staging.aura-coffee-bakery.ru` points to the VPS `212.8.226.214`.
- `aura-coffee-bakery.ru` remains parked on Beget until staging is proven.
- VPS baseline is complete: Ubuntu 24.04.4, Docker/Compose installed, `deploy`
  SSH works, firewall allows only SSH/HTTP/HTTPS.
- Stage 2 HTTPS skeleton is deployed on the VPS. HTTP redirects to HTTPS,
  staging is protected with a Basic Auth first prompt and secure cookie handoff,
  authorized `/health`, `/`, `/admin/`, and menu media requests return 200 over
  HTTPS, and Postgres/Redis are private. YuKassa remains fake and SMS remains
  log/mock.
- Stage 0 is effectively ready for engineering work with caveats. YuKassa is
  intentionally deferred/mocked until owner details are available. SMS.ru account
  setup exists and the API key is present on the VPS, but staging is deliberately
  back in mock mode as of 2026-05-07: `SMS_BACKEND=log`. This keeps website
  testing unblocked while SMS.ru sender/legal constraints are resolved. Yandex
  keys exist, Aura supports separate Suggest/Geocoder keys, and closed-staging
  Yandex smoke passed through the server-side `/api/v1/maps/*` proxy. Yandex
  licensing/data storage still blocks delivery launch, not staging skeleton work.
- Stage 3 menu/media is loaded on closed staging from
  `docs/shipping-website/menu-catalog/`: 11 categories, 53 items, 104 size
  options, 4 alternative-milk modifiers, 28 item/modifier links, and media under
  `/media/menu/`. Video playback is gated on staging: desktop uses cursor
  proximity, including hybrid cursor/touch devices, and mobile plays only
  viewport-visible videos while keeping offscreen videos paused. Owner approval
  is still required for English names, size-label UX, and cacao/matcha
  alternative-milk pricing caveats.
- Current VPS release as of 2026-05-09:
  `72afc0334716-codex-hybrid-video-gate-20260509T170604Z`, built from a clean
  Git archive at `72afc03 fix(customer): detect hybrid cursor video playback`.

Current public-launch blockers:

- Real YuKassa test-shop and live payment path is not proven.
- Real SMS.ru OTP path is not proven and is blocked by sender/legal constraints.
- Yandex license/storage decision, production restrictions, quota monitoring, and
  full delivery checkout smoke are not complete.
- Backup/restore drill and operational monitoring are not complete.
- Legal/privacy/offer/refund/consent materials and final menu/media approval are
  owner-blocked.
- Staff/admin privileged access-token storage still needs hardening before broad
  public use.

### Stage 1: Production Skeleton In Repo

Owner: Codex.

Implement the deployment shape without live providers:

- `docker-compose.production.yml`.
- `.env.production.example` with no secrets.
- Production nginx config for `/`, `/admin/`, `/api/`, `/health`,
  `/api/webhooks/yukassa`, and `/media/menu/`.
- Static customer/admin frontend serving; no Vite dev servers in production.
- No public Postgres or Redis port bindings.
- Restart policies and health checks.
- Optional `scripts/production/validate-env.sh` and deploy/readiness helpers.

Provider mode for this stage:

```text
YUKASSA_BACKEND=fake
SMS_BACKEND=log
YANDEX_MAPS_SUGGEST_API_KEY=
YANDEX_MAPS_GEOCODER_API_KEY=
YANDEX_MAPS_API_KEY=
```

Gate:

- `scripts/production/compose.sh .env.production.example config` is valid.
- Production images build.
- nginx is the only public service.
- `/`, `/admin/`, `/health`, and `/media/menu/...` smoke successfully.

### Stage 2: Private Staging Deploy

Owner: user for server access, Codex for commands and fixes.

Deploy the production skeleton to the VPS or staging host while providers remain
fake/log.

Steps:

- Put sanitized `/opt/aura-coffee/.env.production` on the server.
- Point DNS at the host.
- Start production Compose overlay.
- Run migrations.
- Load the closed-staging draft menu seed and media placeholders.
- Smoke customer, admin, health, media, and same-origin API routing over HTTP.
- Issue TLS certificate.
- Restart with the TLS and staging-auth Compose overlays.
- Smoke the same routes over HTTPS with Basic Auth credentials and confirm
  unauthenticated requests return 401.
- Install a certificate renewal command/timer.

Gate:

- HTTPS works.
- Closed staging access control is enabled.
- Closed-staging draft menu is loaded before cart/order smoke tests.
- Public pages load.
- admin SPA loads at `/admin/`.
- Postgres/Redis are private.
- No real SMS or payment calls occur yet.

### Stage 3: Menu And Media Readiness

Owner: user for shop data/assets, Codex for import/template and validation.

This can run in parallel with provider account setup, but it must finish before
public launch.

Steps:

- Give owner a strict spreadsheet template. Current packet:
  `docs/shipping-website/menu-catalog/`.
- Require stable slugs/codes, not display names as primary keys.
- Load final names, categories, sizes, prices in kopecks, active flags, and sort
  order.
- Place media under `/media/menu/{slug}/hero.mp4` and
  `/media/menu/{slug}/poster.webp`.
- Import with the guarded script when replacing the closed-staging draft menu:
  `ALLOW_MENU_CATALOG_IMPORT=1 python -m database.seeds.menu_catalog --catalog-dir docs/shipping-website/menu-catalog --replace-existing`.
- Check mobile card crop, detail page crop, poster fallback, and video failure
  fallback.

Gate:

- `scripts/production/validate-menu-catalog.py docs/shipping-website/menu-catalog`
  passes on the owner-filled catalog.
- Final menu/prices/sizes are approved by the shop owner.
- Every public item has acceptable image/video behavior.
- `curl -I https://DOMAIN/media/menu/...` works for representative assets.

### Stage 4: Yandex Maps

Owner: user for key/dashboard, Codex for probes and app smoke.

Enable Yandex before SMS/YuKassa because delivery validation depends on
geocoding but does not move money.

Steps:

- Enable Geosuggest/Suggest and Geocoder HTTP API.
- Restrict the keys by server IP/domain where possible.
- Set `YANDEX_MAPS_SUGGEST_API_KEY` and `YANDEX_MAPS_GEOCODER_API_KEY` in server
  env only.
- Keep `YANDEX_MAPS_API_KEY` empty unless using the legacy/common fallback.
- Restart `core-api`.
- Probe Geocoder from inside the `core-api` container.
- Test customer address suggest.
- Test typed address save without selecting a suggestion.
- Test low-precision/vague address rejection.

Gate:

- Suggest works through Aura API.
- Typed delivery address geocodes or blocks delivery safely.
- Yandex key is not visible in frontend bundles or browser network calls.

### Stage 5: SMS.ru OTP

Owner: user for SMS account/phone, Codex for smoke and log inspection.

Enable SMS with cost limits and a controlled number.

Steps:

- Fund SMS.ru account.
- Create `api_id`.
- Configure daily spend/volume limit.
- Set `SMS_BACKEND=smsru` and `SMSRU_API_KEY`.
- Restart `sms-worker`, `core-api-worker`, and `core-api`.
- Request OTP from customer UI.
- Wait for SMS worker to mark delivery `sent`; OTP is asynchronous.
- Verify OTP and confirm JWT/session creation.
- Inspect `sms-worker` logs.

Gate:

- Controlled phone receives OTP.
- Login succeeds.
- Logs include `BLOCK_SMSRU_CALL`.
- Logs do not include raw phone, OTP, SMS body, JWT, or API key.

### Stage 6: YuKassa Test-Shop Payment Path

Owner: user for YuKassa dashboard, Codex for runtime checks and log inspection.

Use the real YuKassa HTTP path with test-shop credentials before any live money.

Steps:

- Configure YuKassa test shop.
- Set webhook URL to `https://DOMAIN/api/webhooks/yukassa`.
- Subscribe to `payment.succeeded`, `payment.canceled`, `refund.succeeded`, and
  `refund.canceled`.
- Set `YUKASSA_BACKEND=live`,
  `YUKASSA_BASE_URL=https://api.yookassa.ru/v3`, and test shop credentials.
- Restart `payment-worker`, `payment-webhook`, and `core-api`.
- Create small pickup order.
- Pay with YuKassa test card.
- Confirm webhook reaches Aura.
- Confirm order moves `CREATED -> PAID`.
- Inspect payment logs.

Gate:

- Payment redirect works.
- Webhook emits `BLOCK_WEBHOOK_VERIFY` before DB-write markers.
- Payment processing emits `BLOCK_TX_PAYMENT`.
- Duplicate webhook is idempotent.
- Invalid source/signature is rejected.
- Logs do not include raw webhook body, secret, PAN, JWT, or PII.

### Stage 7: Refund, Cancellation, And Failure Drills

Owner: user plus Codex.

Do this in YuKassa test mode before live credentials.

Steps:

- Create and pay a second controlled test order.
- Trigger admin cancel/refund path.
- Confirm refund/payment state in Aura.
- Confirm refund in YuKassa dashboard.
- Replay duplicate webhook if provider tooling allows.
- Try invalid webhook source/signature if feasible.

Gate:

- Refund path works.
- Duplicate terminal events do not double-apply side effects.
- Invalid webhooks are rejected before mutation.
- Logs remain redacted.

### Stage 8: Backups, Restore, And Operations

Owner: Codex for scripts, user for server schedule/alerts.

Do this before live payment acceptance.

Steps:

- Add backup and restore scripts.
- Run a Postgres backup.
- Restore into scratch DB or scratch stack.
- Run readiness checks after restore.
- Configure retention: at least 7 daily and 4 weekly backups.
- Add or document checks for disk, container health, TLS expiry, SMS balance,
  Yandex quota, and YuKassa failed webhooks/payments.

Gate:

- Backup file exists.
- Restore drill succeeds.
- Readiness check passes after restore.

### Stage 9: Full Private End-To-End Smoke

Owner: user plus Codex.

Run the complete private launch flow with test/fake money where possible.

Steps:

- Open customer site on mobile and desktop.
- Browse menu.
- Register/login with SMS OTP.
- Add item to cart.
- Create pickup order.
- Pay through YuKassa test path.
- Confirm customer order detail changes to paid.
- Staff logs in at `/admin/`.
- Barista changes order status.
- Courier/admin surfaces are role-correct.
- Run delivery path with an in-zone Yandex-geocoded address.
- Run cancel/refund path on a controlled order.

Gate:

- The core business flow works before public traffic.
- Any code fixes found here get normal tests plus GRACE LDD/redaction coverage
  when they touch auth, SMS, payments, webhooks, PII, logging, or state
  transitions.

### Stage 10: Controlled Live Cutover

Owner: user plus Codex.

Do not begin this stage until all previous gates pass.

Steps:

- Take final database backup.
- Replace YuKassa test credentials with live credentials.
- Confirm `SMS_BACKEND=smsru`, `YANDEX_MAPS_SUGGEST_API_KEY`, and
  `YANDEX_MAPS_GEOCODER_API_KEY` remain real and working.
- Configure live YuKassa webhook.
- Create one tiny real pickup order with owner approval.
- Pay with a real card.
- Confirm order moves to `PAID`.
- Confirm fiscal/receipt status in provider tooling.
- Confirm staff can operate the order.
- Optionally refund the controlled order if the owner wants a live refund drill.
- Monitor logs for 30-60 minutes.

Gate:

- One real payment works.
- Fiscal receipt path is correct.
- Logs remain redacted.
- No recurring webhook/worker errors appear during observation.

### Stage 11: Public Launch

Owner: user for go/no-go, Codex for final checks.

Open public traffic only when these are true:

- Final menu, prices, sizes, and media are approved.
- Legal/privacy/offer/refund content is published.
- SMS.ru balance and limits are active.
- Yandex quota/billing monitoring is active.
- YuKassa live payment and receipt path are proven.
- Backup and restore drill passed.
- Staff accounts and roles are verified.
- Operational rollback path is written and understood.

If any gate fails, stop at that stage, roll back only that provider/config path,
preserve evidence, and fix in a scoped packet.

## Launch Principles

1. Keep one public entry point: nginx on `80` and `443`.
2. Keep database and Redis private: no public host port bindings.
3. Keep secrets out of Git: real `.env.production` lives only on the server.
4. Keep provider integrations server-side: no Yandex, SMS.ru, or YuKassa keys in
   frontend bundles.
5. Treat legal and provider account readiness as launch blockers, not afterwork.
6. Execute in small GRACE packets with verification evidence after each packet.

## External Source References

These were used for the initial shipping plan and should be refreshed before
final provider configuration:

- YuKassa API format: https://yookassa.ru/developers/using-api/interaction-format
- YuKassa webhooks: https://yookassa.ru/developers/using-api/webhooks
- YuKassa 54-FZ receipts: https://yookassa.ru/developers/payment-acceptance/receipts/54fz/yoomoney/basics
- SMS.ru send API: https://sms.ru/docs/api/api_group_sms/send
- SMS.ru approved sender list: https://sms.ru/docs/api/api_group_sms/api_senders
- Yandex Geosuggest quick start: https://yandex.com/maps-api/docs/suggest-api/quickstart.html
- Yandex Geocoder request format: https://yandex.ru/maps-api/docs/geocoder-api/request.html
- Yandex key restrictions and quotas: https://yandex.com/maps-api/docs/js-api/limit.html
- Docker Compose production guidance: https://docs.docker.com/compose/how-tos/production/
- Docker environment variable guidance: https://docs.docker.com/compose/how-tos/environment-variables/best-practices/
- Certbot nginx instructions: https://certbot.eff.org/instructions?os=ubuntuxenial&ws=nginx
- 152-FZ Article 18: https://legalacts.ru/doc/152_FZ-o-personalnyh-dannyh/glava-4/statja-18/
- 152-FZ Article 19: https://legalacts.ru/doc/152_FZ-o-personalnyh-dannyh/glava-4/statja-19/
- 152-FZ Article 22: https://legalacts.ru/doc/152_FZ-o-personalnyh-dannyh/glava-4/statja-22/

## One Question That Changes The Plan

Will production run on a single Russian VPS that we manage directly, or on a
managed cloud platform with managed PostgreSQL/Redis?
- single Russian VPS

The safest starting assumption is one Russian VPS with Docker Compose and local
PostgreSQL/Redis volumes, because that matches the current codebase and avoids
cross-service database networking.
