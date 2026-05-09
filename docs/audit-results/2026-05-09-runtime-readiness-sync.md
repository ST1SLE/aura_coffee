# Aura Coffee Runtime Readiness Sync

Date: 2026-05-09
Scope: closed-staging documentation sync after the clean VPS release and current
menu/provider packets.

## Evidence Checked

- Local repo head: `72afc03 fix(customer): detect hybrid cursor video playback`.
- VPS release metadata:
  `72afc0334716-codex-hybrid-video-gate-20260509T170604Z`, source
  `git_archive_clean`, packet `customer_hybrid_video_playback_gate`.
- VPS Compose status: nginx publishes only `80/443`; Core API, Postgres, Redis,
  SMS worker, payment worker, and payment webhook are internal Docker services.
- VPS provider modes: `AURA_ENV=production`, `YUKASSA_BACKEND=fake`,
  `SMS_BACKEND=log`; Yandex key variables are present on the server path but no
  key material is recorded here.
- Menu catalog validation passed for `docs/shipping-website/menu-catalog`:
  11 categories, 53 items, 104 size options, 4 modifiers, and 28 item-modifier
  links.
- Menu video playback smoke passed on closed staging: desktop cursor-away state
  left all 53 videos paused and unloaded; hovering a product loaded only that
  product video; mobile-path viewport playback paused all offscreen videos.
- Yandex Maps closed-staging smoke passed: direct provider probes from
  `core-api` returned HTTP 200 for Suggest and Geocoder, Aura
  `/api/v1/maps/*` proxy returned suggestions and street-level geocode, vague
  input returned `422 {"reason": "low_precision"}`, and browser address-form
  create/delete used only Aura endpoints with no direct Yandex browser request.

## Current State

Closed staging is now production-shaped at the deployment boundary: static
frontends, same-origin nginx, TLS, staging access protection, private
Postgres/Redis, private payment webhook, and `/media/menu/` serving are in place.
The current VPS release is built from a clean Git archive rather than manual
server overlays.

Closed staging is not public-launch ready yet. It deliberately runs mocked
payment and SMS modes while provider/legal gates are unresolved:

- YuKassa is still fake; no real payment, webhook, fiscalization, refund, or
  duplicate-webhook drill has passed.
- SMS.ru is still log/mock; the real provider path is blocked by sender/legal
  constraints and must be tested only with a controlled phone and redaction
  inspection.
- Yandex Suggest/Geocoder works through the server-side Aura proxy on closed
  staging, but delivery launch still requires license/storage/quota/billing due
  diligence and a full delivery checkout smoke.
- The menu/media packet is validated and loaded for closed staging, but owner
  approval is still required for final names, prices, sizes, English labels,
  media quality, and alternative-milk pricing caveats.

## Audit Status Delta

Mitigated or resolved since the 2026-05-03 production security audit:

- The public staging stack no longer uses the local dev Compose shape.
- Nginx is the only public service; Postgres, Redis, Core API, workers, and
  payment webhook are internal.
- Production nginx/TLS/staging-auth overlays exist and are deployed.
- `/media/menu/` is served by nginx from a read-only media mount.
- Production nginx access logs omit query strings, reducing address PII exposure
  in server logs.
- `.dockerignore` exists and excludes env files, keys, caches, build output,
  archives, and local DB/log artifacts.
- Container restart policies and health checks cover the current production-like
  overlay well enough for closed staging.
- Customer menu video autoplay is now gated for closed staging: desktop uses
  cursor proximity, including hybrid cursor/touch devices, while mobile plays
  visible videos and keeps offscreen videos paused.
- Backup/restore drill passed on closed staging: daily and weekly Postgres dump
  files were created under `/var/backups/aura-coffee/postgres`, the daily dump
  restored into scratch DB `aura_restore_20260509T182218Z`, Alembic reported
  `0011 (head)`, representative counts returned `table_count=21`,
  `menu_items=55`, `users=8`, the scratch DB was dropped, no `aura_restore_*`
  DB remained, and staging `/health` stayed OK.

Still open before public launch:

- Real YuKassa test-shop payment, webhook, refund, duplicate, and invalid-source
  drills.
- Real SMS.ru OTP delivery with controlled phone, spend limits, and log
  redaction proof.
- Yandex production restrictions, quota/billing monitoring, and full delivery
  checkout smoke.
- Recurring backup schedule, retention job wiring, and operational alerting.
- Staff/admin access token still persists in `localStorage`; refresh tokens are
  HttpOnly, but privileged access-token storage remains a security hardening
  item.
- Payment webhook idempotency/concurrency hardening for real provider traffic.
- OTP send idempotency around provider-success/Redis-status failure.
- Phone hash pepper/HMAC migration planning.
- Trusted client-IP helper and proxy-header posture for staff login throttling.
- Legal/privacy/offer/refund/consent pages and 152-FZ owner decisions.
- Final owner approval of menu, prices, sizes, media, and operating procedures.

## Product UX Good-To-Have Backlog

These are not required to keep closed staging safe, but they matter for a
smooth public launch:

- Maintenance or ordering-paused mode that leaves menu browsing available while
  blocking checkout.
- Staff exception dashboard for failed payments, failed notifications, refund
  retries, and stuck order states.
- Operator runbook for one-order drills: pickup, delivery, cancellation, refund,
  provider outage, and customer support call.
- Lightweight monitoring for disk, container health, TLS expiry, SMS balance,
  Yandex quota, YuKassa webhook failures, and worker queue depth.
- Remaining mobile/slow-network media checks for poster fallback, first-load
  stall, and card crop. Autoplay/proximity/offscreen playback was smoke-tested
  on closed staging on 2026-05-09.
- Accessibility and text-overflow screenshot gates for the final customer and
  staff surfaces after content freezes.
- A privacy-safe analytics/error-reporting policy before adding any third-party
  telemetry.

## GRACE / LDD Gate

This sync is documentation-only. No runtime code, state machine, transaction,
auth, SMS, payment, PII, logging, or required-marker behavior changed in this
packet, so LDD assertions are not required.
