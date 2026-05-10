# Provider Integration Rollout Plan

This is the operator checklist for moving Aura Coffee from mocked providers to
real Yandex Maps, SMS.ru, and YuKassa integrations.

Do not jump from local mocks directly to public live ordering. Enable one
external provider at a time, prove the runtime path, check logs for redaction,
then either continue or roll back that provider before touching the next one.

## Scope

Target runtime:

- `https://DOMAIN/` customer site.
- `https://DOMAIN/admin/` staff site.
- `https://DOMAIN/api/` Core API.
- `https://DOMAIN/api/webhooks/yukassa` payment webhook ingress.
- PostgreSQL and Redis private inside Docker Compose.
- Provider secrets stored only in `/opt/aura-coffee/.env.production`.

Out of scope for this file:

- Menu spreadsheet import.
- Legal text drafting.
- Product behavior changes.
- Payment/refund state-machine changes.

## Hard Rules

- No real customer traffic before all gates in this file pass.
- No real provider secrets in Git, screenshots, terminal transcripts, or docs.
- Keep Yandex, SMS.ru, and YuKassa keys server-side only.
- Keep Postgres and Redis private; only nginx is public.
- Yandex Suggest may degrade to manual entry, but Geocoder failure must block
  delivery validation when coordinates are absent.
- SMS OTP tests must use a controlled phone and provider spend limits.
- YuKassa test shop must pass before live shop credentials are used.
- If code changes touch auth, OTP, SMS, payment creation, webhooks, refunds,
  PII, secrets, logging, transaction boundaries, or state transitions, GRACE LDD
  assertions are required before the packet is done.

Required LDD markers for code-change packets:

- `CoreApi auth.otp_request BLOCK_OTP_GEN`
- `SmsWorker send_otp BLOCK_SMSRU_CALL`
- `CoreApi auth.otp_verify BLOCK_AUTH_VERIFY`
- `PaymentWorker process_webhook BLOCK_WEBHOOK_VERIFY`
- `PaymentWorker process_webhook BLOCK_TX_PAYMENT`
- `PaymentWorker create_intent BLOCK_TX_PAYMENT`
- `PaymentWorker initiate_refund BLOCK_TX_PAYMENT`

Redaction checks for code-change packets must assert captured logs contain no
raw phone number, OTP code, JWT, password, PAN, API key, raw webhook body, or
full address.

## Roles

User owns:

- VPS/domain/provider dashboards.
- Real secret values.
- SMS test phone access.
- YuKassa shop/accountant/fiscalization decisions.
- Final legal/business launch approval.

Codex owns:

- Repo changes for production Compose/nginx/env validation/scripts.
- Safe local/staging commands.
- Test execution and log inspection.
- GRACE/LDD test additions if implementation fixes are needed.
- Updating this docs directory when the actual path changes.

## Current Closed-Staging Snapshot

Last checked: 2026-05-10.

- VPS release:
  `bbea3f268b98-codex-video-buffering-20260510T091654Z`, built from a clean
  Git archive.
- Runtime shape: nginx publishes `80/443`; Postgres, Redis, Core API, SMS
  worker, payment worker, and payment webhook are private Docker services.
- Provider modes: `AURA_ENV=production`, `YUKASSA_BACKEND=fake`,
  `SMS_BACKEND=log`. These are acceptable only for closed staging.
- Menu/media: `docs/shipping-website/menu-catalog` validates with
  11 categories, 53 items, 104 size options, 4 modifiers, and 28 item-modifier
  links. Video playback smoke passed on staging: desktop loads only near-cursor
  product videos, including hybrid cursor/touch devices, and mobile keeps
  offscreen videos paused while visible videos play. As of 2026-05-10, video
  cards keep the poster visible while autoplay buffers, all 54 staging
  `hero.mp4` files pass faststart validation, and byte-range smoke for
  `/media/menu/ice-americano/hero.mp4` returns `206 video/mp4`.
- Yandex address smoke passed on 2026-05-09: direct provider probes from
  `core-api`, Aura `/api/v1/maps/*` proxy calls, vague-address low-precision
  rejection, browser address-form suggest/geocode/save, and cleanup all passed;
  the frontend bundle and browser network did not expose direct Yandex calls.
- Backup/restore drill passed on 2026-05-09: daily and weekly dump files were
  created, the daily dump restored into a scratch DB, Alembic reported
  `0011 (head)`, representative row counts passed, the scratch DB was dropped,
  no `aura_restore_*` DB remained, and staging `/health` stayed OK.
- Recurring server-side ops passed on 2026-05-10: deploy-user cron installs
  daily backups, weekly backup copies, and a 15-minute ops health check for
  services, public health, TLS expiry, backup freshness, disk usage, provider
  modes, Yandex split-key presence, and the cron marker.
- Staff/admin access-token storage hardening is complete locally: privileged
  access tokens are memory-only, route guards recover from the HttpOnly refresh
  cookie after reload, and legacy durable browser tokens are cleared.
- Next provider gate: SMS.ru controlled OTP smoke when the provider path is
  ready. If SMS remains blocked, the residual media and slow-network video checks
  are complete; the remaining launch gates are provider/account access and final
  end-to-end smoke.

## Phase 0: Freeze Launch Inputs

Goal: collect the values that all later phases depend on.

Steps:

1. Choose canonical `DOMAIN` or a temporary `staging.DOMAIN`.
2. Choose VPS/provider and record public IPv4.
3. Create DNS `A DOMAIN -> VPS_IPV4`.
4. Decide whether `www` redirects to canonical domain.
5. Confirm production contact email for TLS and provider accounts.
6. Confirm public webhook URL:
   `https://DOMAIN/api/webhooks/yukassa`.
7. Choose controlled OTP test phone.
8. Confirm who owns 54-FZ receipt/fiscalization decisions.
9. Confirm who approves privacy policy, personal-data consent, offer/refund
   text, and 152-FZ duties.

Checks:

```bash
dig +short DOMAIN A
curl -I http://DOMAIN/
```

Gate:

- DNS resolves to the VPS or is intentionally waiting for propagation.
- Webhook URL is final enough to enter in YuKassa test shop settings.
- Legal/fiscalization owners are known.

Rollback:

- None. This phase only records inputs.

## Phase 1: Deploy Safe Production-Like Skeleton

Goal: prove public nginx, static frontends, private DB/Redis, health checks, and
media serving before real providers are enabled.

Precondition:

- Production overlay and static frontend serving are implemented, or we execute
  `01-execution-plan.md` Packets 1-5 first.

Temporary provider mode:

```text
YUKASSA_BACKEND=fake
SMS_BACKEND=log
YANDEX_MAPS_SUGGEST_API_KEY=
YANDEX_MAPS_GEOCODER_API_KEY=
YANDEX_MAPS_API_KEY=
```

Current YuKassa decision as of 2026-05-04:

- Keep YuKassa mocked until the coffee shop owner can provide the business
  details required by YuKassa and approve 54-FZ/refund decisions.
- Production/staging skeleton work should continue with `YUKASSA_BACKEND=fake`.

Steps:

1. Put sanitized production-like env on the server:
   `/opt/aura-coffee/.env.production`.
2. Keep real provider credentials out of this first skeleton boot.
3. Build images with the production overlay.
4. Run migrations.
5. Start the stack.
6. Confirm only nginx is public.
7. Confirm `/media/menu/` is served from the intended source.

Commands:

```bash
scripts/production/validate-env.sh /opt/aura-coffee/.env.production

scripts/production/compose.sh /opt/aura-coffee/.env.production config

scripts/production/compose.sh /opt/aura-coffee/.env.production up -d --build

scripts/production/compose.sh /opt/aura-coffee/.env.production ps

scripts/production/compose.sh /opt/aura-coffee/.env.production port postgres 5432

scripts/production/compose.sh /opt/aura-coffee/.env.production port redis 6379

curl -I https://DOMAIN/
curl -I https://DOMAIN/admin/
curl -s https://DOMAIN/health
```

Expected:

- `port postgres 5432` prints nothing or fails.
- `port redis 6379` prints nothing or fails.
- Customer site, admin site, and health endpoint respond through nginx.
- No real provider calls happen.

Gate:

- Public skeleton works with fake/log providers.
- DB and Redis are not reachable from the public internet.

Rollback:

```bash
scripts/production/compose.sh /opt/aura-coffee/.env.production down
```

## Phase 2: Enable Yandex Maps

Goal: prove Suggest and Geocoder through the Core API server-side proxy.

Current closed-staging result as of 2026-05-09: passed. Direct Yandex provider
probes from `core-api` returned HTTP 200, Aura proxy endpoints returned
suggestions and street-level geocode, vague input returned `low_precision`, and
an authenticated browser address-form flow created and deleted a controlled
saved-address smoke record without direct Yandex browser requests.

Provider dashboard steps:

1. Create or select Yandex Maps API keys.
2. Enable Geosuggest/Suggest API on the Suggest key.
3. Enable Geocoder HTTP API on the Geocoder key.
4. Restrict the keys by server IP and/or domain where the provider supports it.
5. Record quota, billing threshold, and where usage statistics are monitored.
6. Wait for key/restriction activation if needed.

Server env:

```text
YANDEX_MAPS_SUGGEST_API_KEY=real_geosuggest_key
YANDEX_MAPS_GEOCODER_API_KEY=real_geocoder_key
YANDEX_MAPS_API_KEY=
```

Restart:

```bash
scripts/production/compose.sh /opt/aura-coffee/.env.production up -d core-api
```

Provider probe from inside `core-api`:

```bash
scripts/production/compose.sh /opt/aura-coffee/.env.production \
  exec -T core-api python3 -c "
import httpx, os
k = os.getenv('YANDEX_MAPS_GEOCODER_API_KEY') or os.getenv('YANDEX_MAPS_API_KEY', '')
print('key-present:', bool(k), 'len:', len(k))
r = httpx.get(
    'https://geocode-maps.yandex.ru/1.x/',
    params={'geocode': 'Moscow', 'apikey': k, 'format': 'json'},
    timeout=5,
)
print('HTTP', r.status_code, r.text[:160])
"
```

App checks:

1. Log in as a customer.
2. Open checkout or profile address form.
3. Type an address and confirm suggestions appear.
4. Save a typed address without selecting a suggestion.
5. Confirm it geocodes and stores coordinates, or fails with a user-safe error.
6. Try an intentionally vague address and confirm low precision is rejected.

Gate:

- Provider probe returns HTTP 200.
- Suggest works through Aura API, not directly from frontend to Yandex.
- Manual typed address either geocodes or blocks delivery safely.
- No Yandex key appears in frontend bundle or browser network requests.

Rollback:

```text
YANDEX_MAPS_SUGGEST_API_KEY=
YANDEX_MAPS_GEOCODER_API_KEY=
YANDEX_MAPS_API_KEY=
```

Then restart `core-api`. The expected rollback state is degraded address UX, not
silent delivery validation bypass.

## Phase 3: Enable SMS.ru OTP

Goal: prove real OTP delivery and login while keeping cost and log exposure
bounded.

Provider dashboard steps:

1. Create/fund SMS.ru account.
2. Create `api_id`.
3. Configure daily spend or volume limit.
4. Request/confirm sender name if branded sender is required.
5. Record balance, limit, and status pages for monitoring.
6. Review OTP text length to avoid accidental multi-segment messages.

Current staging status as of 2026-05-07:

- VPS is back in safe mock mode: `SMS_BACKEND=log`.
- VPS has `SMSRU_API_KEY`, but it is not used while `SMS_BACKEND=log`.
- Local SMS worker safety tests pass for `BLOCK_SMSRU_CALL` and redaction.
- Use operator-only Redis OTP assistance for closed-staging website testing;
  do not expose generated OTPs through logs or UI.

Current decision after SMS.ru sender validation on 2026-05-07:

- Branded sender/operator registration is not economical for staging because
  major operators require a legal entity/IP contract and monthly fees.
- OTP text uses SMS.ru code/password mode: `Ваш код: {code}`. SMS.ru may strip
  the text and deliver only the code from the shared `SMS.RU` sender.
- Keep `SMSRU_SENDER_NAME` empty for this staging path. Use it only after an
  approved branded sender exists.
- Real SMS remains blocked until a provider path works without paid/legal
  operator registration.

Server env:

```text
SMS_BACKEND=smsru
SMSRU_API_KEY=real_api_id
```

Safe VPS switch, with the secret entered interactively instead of pasted into
shell history:

```bash
ssh -i ~/.ssh/aura-vps -o IdentitiesOnly=yes deploy@212.8.226.214

read -rsp "SMSRU_API_KEY: " SMSRU_API_KEY
echo
export SMSRU_API_KEY
ENV=/opt/aura-coffee/.env.production
cp "$ENV" "$ENV.bak.$(date -u +%Y%m%dT%H%M%SZ)"

python3 - "$ENV" <<'PY'
from pathlib import Path
import os
import sys

path = Path(sys.argv[1])
key = os.environ["SMSRU_API_KEY"].strip()
if not key or key == "your-smsru-api-key":
    raise SystemExit("SMSRU_API_KEY is empty or placeholder")

values = {
    "SMS_BACKEND": "smsru",
    "SMSRU_API_KEY": key,
}
seen: set[str] = set()
out: list[str] = []
for line in path.read_text().splitlines():
    if "=" in line and not line.lstrip().startswith("#"):
        name = line.split("=", 1)[0]
        if name in values:
            out.append(f"{name}={values[name]}")
            seen.add(name)
            continue
    out.append(line)

for name, value in values.items():
    if name not in seen:
        out.append(f"{name}={value}")

path.write_text("\n".join(out) + "\n")
PY

unset SMSRU_API_KEY
cd /opt/aura-coffee/app
scripts/production/validate-env.sh "$ENV"
scripts/production/compose.sh --tls --staging-auth "$ENV" \
  up -d --force-recreate sms-worker core-api-worker core-api
```

Manual editor fallback if the remote terminal says
`Error opening terminal: xterm-ghostty`:

```bash
TERM=xterm-256color nano /opt/aura-coffee/.env.production
```

Controlled OTP flow:

1. Clear any test-phone rate-limit keys only if needed and only for the
   controlled number.
2. Request OTP from the customer UI using the controlled personal phone only.
3. Wait for SMS arrival.
4. Enter OTP and complete login.
5. Capture full verify response if using API commands; do not pipe directly to
   `jq -r .access_token` until the response is known-good.
6. If verifying by API, wait for Redis OTP state `sent` before verify. The SMS
   worker flips status asynchronously.

Log check:

```bash
scripts/production/compose.sh /opt/aura-coffee/.env.production \
  logs --tail 150 sms-worker
```

Remote redaction smoke after the controlled UI login attempt:

```bash
ssh -i ~/.ssh/aura-vps -o IdentitiesOnly=yes deploy@212.8.226.214 '
cd /opt/aura-coffee/app
COMPOSE="scripts/production/compose.sh --tls --staging-auth /opt/aura-coffee/.env.production"
logs=$($COMPOSE logs --tail 250 sms-worker core-api 2>/dev/null || true)
printf "%s\n" "$logs" | grep -q "BLOCK_SMSRU_CALL" \
  && echo "block_smsru_call=yes" || echo "block_smsru_call=no"
printf "%s\n" "$logs" | grep -Eiq "\+7[0-9]{10}|access_token|refresh_token|api_id|secret_key|SMSRU_API_KEY|otp_code|Ваш код|Aura Coffee:" \
  && echo "sensitive_pattern=yes" || echo "sensitive_pattern=no"
'
```

Expected:

- Controlled phone receives OTP.
- OTP verify returns a JWT/session.
- Logs include `BLOCK_SMSRU_CALL`.
- Logs do not include raw phone, OTP code, SMS body, JWT, or API key.

Gate:

- Real SMS OTP login works for controlled phone.
- Provider spend/volume limit is active.
- Redaction inspection passes.

Rollback:

```text
SMS_BACKEND=log
SMSRU_API_KEY=
```

Then run:

```bash
scripts/production/validate-env.sh /opt/aura-coffee/.env.production
scripts/production/compose.sh --tls --staging-auth /opt/aura-coffee/.env.production \
  up -d --force-recreate sms-worker core-api-worker core-api
```

## Phase 4: Enable YuKassa Test-Shop Payments

Goal: use the real YuKassa HTTP path and webhook ingress with test-shop
credentials before any live money is accepted.

Provider dashboard steps:

1. Create/access YuKassa test shop.
2. Get test `shopId` and test secret key.
3. Set HTTP notification URL:
   `https://DOMAIN/api/webhooks/yukassa`.
4. Subscribe to at least:
   - `payment.succeeded`
   - `payment.canceled`
   - `refund.succeeded`
   - `refund.canceled`
5. Confirm HTTPS works on accepted public port.
6. Confirm source verification method: IP whitelist and/or configured signature.

Server env:

```text
YUKASSA_BACKEND=live
YUKASSA_BASE_URL=https://api.yookassa.ru/v3
YUKASSA_SHOP_ID=test_shop_id
YUKASSA_SECRET_KEY=test_secret_key
YUKASSA_WEBHOOK_IPS=trusted_provider_ips_or_current_approved_value
YUKASSA_WEBHOOK_SIGNATURE_SECRET=only_if_configured
```

Restart:

```bash
scripts/production/compose.sh /opt/aura-coffee/.env.production \
  up -d payment-worker payment-webhook core-api
```

Payment test:

1. Create a small pickup order in the customer UI.
2. Follow the YuKassa confirmation URL.
3. Pay with a YuKassa test card.
4. Return to Aura Coffee.
5. Confirm order status changes from `CREATED` to `PAID`.
6. Confirm the payment object in YuKassa test dashboard has `test=true`.
7. Inspect payment-webhook logs.

Log check:

```bash
scripts/production/compose.sh /opt/aura-coffee/.env.production \
  logs --tail 200 payment-webhook payment-worker
```

Expected:

- Customer is redirected to YuKassa and back.
- Webhook reaches Aura at `/api/webhooks/yukassa`.
- Logs include `BLOCK_WEBHOOK_VERIFY` before DB-write markers.
- Logs include `BLOCK_TX_PAYMENT`.
- Logs do not include raw webhook body, secret key, full PAN, JWT, or PII.

Gate:

- Test payment succeeds.
- Order moves to `PAID`.
- Webhook verification and transaction markers are visible.
- No secret/PII leakage appears in logs.

Rollback:

1. Disable test-shop webhook in YuKassa dashboard.
2. Revert server env:

```text
YUKASSA_BACKEND=fake
YUKASSA_SHOP_ID=dev-shop
YUKASSA_SECRET_KEY=dev-secret
```

3. Restart `payment-worker`, `payment-webhook`, and `core-api`.

## Phase 5: YuKassa Refund, Duplicate, And Rejection Tests

Goal: prove payment edge cases before live credentials.

Tests:

1. Create another controlled test order and pay it.
2. Trigger admin cancel/refund path.
3. Confirm refund state in Aura.
4. Confirm refund state in YuKassa test dashboard.
5. Send or replay a duplicate webhook if provider/dashboard tooling supports it.
6. Send an invalid webhook source/signature test if feasible.
7. Confirm duplicate terminal event does not double-apply side effects.

Expected:

- Refund path works in test mode.
- Duplicate webhook is idempotent.
- Invalid webhook source/signature is rejected before mutation.
- Logs remain redacted.

Gate:

- Payment success, cancellation/refund, duplicate webhook, and invalid webhook
  behavior are all known before live cutover.

Rollback:

- Disable YuKassa webhook in dashboard.
- Revert provider env to fake mode.
- Keep test order evidence for later debugging.

## Phase 6: Backups And Restore Drill

Goal: prove we can recover before accepting live orders.

Steps:

1. Run Postgres backup on staging/production-like stack.
2. Restore into scratch DB or scratch stack.
3. Run migrations/readiness checks against restored data.
4. Confirm backup filename/logs do not include secrets.
5. Configure retention: at least 7 daily and 4 weekly backups.

Backup command shape:

```bash
scripts/production/backup-postgres.sh \
  --staging-auth \
  --weekly \
  /opt/aura-coffee/.env.production

scripts/production/restore-postgres.sh \
  --staging-auth \
  /opt/aura-coffee/.env.production \
  /var/backups/aura-coffee/postgres/aura_daily_YYYYMMDDTHHMMSSZ.sql.gz
```

Current closed-staging result as of 2026-05-09: passed.

- Backup files created:
  `aura_daily_20260509T182207Z.sql.gz` and
  `aura_weekly_20260509T182207Z.sql.gz`, both 12,979 bytes.
- Restore scratch DB: `aura_restore_20260509T182218Z`.
- Restore checks: `restore_sql=ok`, Alembic `0011 (head)`,
  `table_count=21`, `menu_items=55`, `users=8`.
- Cleanup/readiness: scratch DB dropped, no `aura_restore_*` DB remained, and
  staging `/health` returned `{"status":"ok","yukassa_backend":"fake"}`.
- Filename/log review: emitted paths, sizes, schema version, row counts, and
  Compose warnings only; no env secrets, phone numbers, OTPs, JWTs, payment
  credentials, or address payloads were printed.
- Recurring schedule command:
  `scripts/production/install-ops-cron.sh --staging-auth
  /opt/aura-coffee/.env.production`.
- Cron defaults: daily backup `17 2 * * 1-6`, weekly backup copy
  `17 2 * * 0`, ops health check `*/15 * * * *`.
- Ops health check:
  `scripts/production/check-ops-health.sh --staging-auth
  /opt/aura-coffee/.env.production`.

Gate:

- Backup exists.
- Restore drill succeeds.
- Readiness check passes after restore.
- Recurring backup schedule is installed.
- Server-side ops health check exits 0.

Rollback:

- Disable backup timer/cron if broken.
- Keep last successful backup.

## Phase 7: Controlled Live Cutover

Goal: run one real-money order under supervision before public traffic.

Preconditions:

- Phase 1-6 gates passed.
- Final menu/prices/sizes are loaded or current launch menu is explicitly
  approved.
- Media assets are deployed and smoke-tested.
- Privacy/offer/refund/legal pages are approved.
- YuKassa fiscalization/54-FZ path is approved by owner/accountant.
- SMS.ru balance and limits are active.
- Yandex quota/billing alert is active.
- Staff have production credentials and role access is verified.

Steps:

1. Take final database backup.
2. Replace YuKassa test credentials with live shop credentials.
3. Confirm:

```text
YUKASSA_BACKEND=live
YUKASSA_BASE_URL=https://api.yookassa.ru/v3
YUKASSA_SHOP_ID=live_shop_id
YUKASSA_SECRET_KEY=live_secret_key
SMS_BACKEND=smsru
YANDEX_MAPS_SUGGEST_API_KEY=real_geosuggest_key
YANDEX_MAPS_GEOCODER_API_KEY=real_geocoder_key
YANDEX_MAPS_API_KEY=
```

4. Configure live YuKassa webhook URL:
   `https://DOMAIN/api/webhooks/yukassa`.
5. Restart affected services.
6. Create one tiny real pickup order with owner approval.
7. Pay with a real card.
8. Confirm order moves to `PAID`.
9. Confirm receipt/fiscal status in YuKassa/provider tooling.
10. Confirm admin sees the order.
11. Optionally refund the controlled live order if business wants a refund
    drill.
12. Monitor logs for 30-60 minutes.

Live smoke commands:

```bash
curl -I https://DOMAIN/
curl -I https://DOMAIN/admin/
curl -s https://DOMAIN/health

scripts/production/compose.sh /opt/aura-coffee/.env.production ps

scripts/production/compose.sh /opt/aura-coffee/.env.production \
  logs --tail 200 core-api payment-webhook payment-worker sms-worker
```

Gate:

- Controlled live payment succeeds.
- Fiscal/receipt status is correct.
- Staff can operate the order.
- Logs are redacted.
- No recurring worker/webhook errors appear during observation window.

Rollback:

1. Disable live YuKassa webhook in provider dashboard.
2. Put site into maintenance or stop public ordering if available.
3. Revert to previous image/config if the problem is deploy-related.
4. Restore database backup only if data corruption occurred and the owner
   accepts data loss since backup time.
5. Preserve logs and provider event IDs for debugging.

## Phase 8: Public Launch Gate

Only open public traffic when every item is true:

- DNS and HTTPS are stable.
- Static customer/admin frontends work on desktop and mobile.
- Menu, prices, sizes, and media are approved.
- `/media/menu/` posters/videos return `200`.
- Real SMS OTP works.
- Yandex Suggest/Geocoder works or fails safely.
- YuKassa live payment works.
- YuKassa refund/cancel procedure is known.
- Fiscal receipt path is confirmed.
- Backups and restore drill passed.
- Legal/privacy/offer/refund content is published.
- Staff accounts and roles are verified.
- Logs show no raw PII or secrets.
- Monitoring exists for disk, containers, TLS expiry, SMS balance, Yandex quota,
  and YuKassa failed webhooks/payments.

## External References To Refresh Before Execution

- YuKassa API format:
  https://yookassa.ru/developers/using-api/interaction-format
- YuKassa webhooks:
  https://yookassa.ru/developers/using-api/webhooks
- YuKassa test payments:
  https://yookassa.ru/developers/payment-acceptance/testing-and-going-live/testing
- SMS.ru API:
  https://sms.ru/docs/api
- SMS.ru send API:
  https://sms.ru/docs/api/api_group_sms
- Yandex key restrictions:
  https://yandex.ru/dev/commercial/doc/en/concepts/limit
- Yandex Geosuggest request format:
  https://yandex.ru/maps-api/docs/suggest-api/request.html
