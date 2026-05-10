# Production Configuration Checklist

Use this file as the working checklist while preparing the real server. Do not
put real secrets in this repository.

## 1. Domain And DNS

Required decisions:

- Canonical domain: `aura-coffee-bakery.ru`.
- Staging domain: `staging.aura-coffee-bakery.ru`.
- Optional `www` domain: `TODO` (recommended: redirect to canonical domain
  later, not required for staging).
- Production contact email: `TODO`.
- DNS provider: Beget.
- VPS IPv4: `212.8.226.214`.
- VPS OS: Ubuntu 24.04.4 LTS.
- SSH key: `~/.ssh/aura-vps` private key, `~/.ssh/aura-vps.pub` public key.

Required records:

| Record | Value | Status |
|--------|-------|--------|
| `A staging.aura-coffee-bakery.ru` | `212.8.226.214` | Done; resolves to VPS. |
| `A aura-coffee-bakery.ru` | VPS IPv4 | TODO only after staging is proven. Currently resolves to Beget IP `5.101.152.161`. |
| `AAAA DOMAIN` | VPS IPv6, if used | TODO |
| `CNAME www` or redirect | Canonical domain | TODO |

Acceptance:

- `dig +short DOMAIN A` returns the server IP.
- `curl http://DOMAIN/health` reaches the server before HTTPS redirect is
  enabled, or the equivalent HTTP-01 Certbot validation succeeds.

## 2. VPS Baseline

Recommended default:

- Russian-region VPS.
- Ubuntu 24.04 LTS.
- 2 vCPU minimum.
- 4 GB RAM minimum.
- 40-80 GB disk minimum, more if menu media/videos are stored locally.
- Static IPv4.

Selected staging VPS:

- IPv4: `212.8.226.214`.
- OS: Ubuntu 24.04.4 LTS.
- CPU/RAM/disk observed over SSH: 2 vCPU, 3.8 GiB RAM, 38G root disk with 36G
  free.
- Baseline status: `deploy` user created, SSH key login works, Docker Engine
  and Compose plugin installed, `ufw` allows only SSH/HTTP/HTTPS, and
  `/opt/aura-coffee`, `/srv/aura-coffee/media/menu`,
  `/var/backups/aura-coffee/postgres` exist.

Host baseline:

- Create non-root deploy user.
- SSH key login only.
- Disable password login where practical.
- Install Docker Engine and Docker Compose plugin.
- Configure firewall to allow only `22`, `80`, and `443`.
- Enable unattended security upgrades if acceptable for the VPS provider.
- Create `/opt/aura-coffee` for app checkout/config.
- Create `/var/backups/aura-coffee/postgres` for backups.
- Create `/srv/aura-coffee/media/menu` if menu media is served from host disk.

Acceptance:

- `docker version` works.
- `docker compose version` works.
- `sudo ufw status` or provider firewall shows only intended ingress.
- `ss -tulpn` shows no public Postgres/Redis listener.

## 3. Production Compose

Production overlay must change the local dev shape:

- Use Python Docker `base` targets, not `dev`.
- Remove source bind mounts.
- Remove Vite dev servers.
- Build static frontend assets.
- Publish only nginx publicly.
- Do not publish PostgreSQL or Redis.
- Add `restart: unless-stopped` or equivalent.
- Use named volumes for database and Redis.
- Keep migrations as a controlled one-shot job.

Expected services:

| Service | Public? | Notes |
|---------|---------|-------|
| `nginx` | yes, `80`/`443` | Only public entry point. |
| `core-api` | no | Reached only by nginx and internal services. |
| `payment-webhook` | no | Reached only by nginx exact webhook route. |
| `core-api-worker` | no | Celery worker. |
| `payment-worker` | no | Celery worker. |
| `sms-worker` | no | Celery worker. |
| `scheduler` | no | Celery beat if still required. |
| `postgres` | no | Internal network only. |
| `redis` | no | Internal network only. |

Required checks:

```bash
scripts/production/compose.sh .env.production.example config

scripts/production/compose.sh --tls .env.production.example config

scripts/production/compose.sh --tls --staging-auth .env.production.example config

scripts/production/compose.sh /opt/aura-coffee/.env.production ps

scripts/production/compose.sh /opt/aura-coffee/.env.production ps --format json

scripts/production/compose.sh /opt/aura-coffee/.env.production port postgres 5432

scripts/production/compose.sh /opt/aura-coffee/.env.production port redis 6379
```

The last two commands can print `:0` on newer Compose versions for exposed but
unpublished container ports. Treat any concrete host port above zero on
PostgreSQL or Redis as a failure.

## 4. Production Environment

Real production env lives on the server only, for example:

```text
/opt/aura-coffee/.env.production
```

Required variables:

| Variable | Production value shape |
|----------|------------------------|
| `AURA_ENV` | `production` |
| `DATABASE_URL` | `postgresql://USER:PASSWORD@postgres:5432/aura_coffee` |
| `POSTGRES_USER` | non-default username if possible |
| `POSTGRES_PASSWORD` | generated strong password |
| `POSTGRES_DB` | `aura_coffee` |
| `REDIS_URL` | `redis://redis:6379/0` |
| `CORS_ORIGINS` | `https://DOMAIN` |
| `JWT_SECRET_KEY` | random string, at least 32 chars |
| `ENCRYPTION_KEY` | 64 hex chars, 32 bytes |
| `SMS_BACKEND` | `smsru` |
| `SMSRU_API_KEY` | real SMS.ru `api_id` |
| `SMSRU_SENDER_NAME` | approved sender name if enabled in code/provider |
| `YANDEX_MAPS_SUGGEST_API_KEY` | real Geosuggest/Suggest key |
| `YANDEX_MAPS_GEOCODER_API_KEY` | real HTTP Geocoder key |
| `YANDEX_MAPS_API_KEY` | optional legacy/common fallback; leave empty when using split keys |
| `YUKASSA_BACKEND` | `live` |
| `YUKASSA_SHOP_ID` | real shop ID |
| `YUKASSA_SECRET_KEY` | real secret key |
| `YUKASSA_BASE_URL` | `https://api.yookassa.ru/v3` |
| `YUKASSA_WEBHOOK_IPS` | official trusted IPs or approved alternative verification |
| `YUKASSA_WEBHOOK_SIGNATURE_SECRET` | set if configured in YuKassa |
| `ADMIN_LOGIN` | non-default initial admin login |
| `ADMIN_PASSWORD` | strong one-time initial admin password |
| `NGINX_HTTP_PORT` | `80` for direct public HTTP |
| `AURA_MENU_MEDIA_DIR` | `/srv/aura-coffee/media/menu` |

Secret generation examples:

```bash
openssl rand -hex 32          # ENCRYPTION_KEY
openssl rand -base64 48       # JWT_SECRET_KEY or passwords
```

Acceptance:

- No production secret is committed.
- `scripts/production/validate-env.sh /opt/aura-coffee/.env.production` passes.
- `AURA_ENV=production` boots only with non-placeholder `JWT_SECRET_KEY` and
  `ENCRYPTION_KEY`.
- `YUKASSA_BACKEND=live` refuses empty credentials or sandbox/test/localhost
  base URLs.
- `SMS_BACKEND=smsru` refuses an empty SMS.ru key.

## 5. Nginx And TLS

Required routes:

| Public route | Internal target |
|--------------|-----------------|
| `/health` | `core-api:8000/health` |
| `/api/webhooks/yukassa` | `payment-webhook:8241/webhooks/yukassa` |
| `/api/` | `core-api:8000` |
| `/admin/` | admin SPA static files |
| `/media/menu/` | approved static media source |
| `/` | customer SPA static files |

TLS:

- Use Let's Encrypt/Certbot or provider-managed TLS.
- Keep HTTP available for initial certificate issuance.
- Redirect HTTP to HTTPS after certificate is issued.
- Do not enable HSTS until HTTPS smoke and rollback path are proven.

Webhook ingress:

- Exact `/api/webhooks/yukassa` route must appear before generic `/api/`.
- nginx must overwrite client-supplied forwarded IP headers on the webhook
  route.
- payment-webhook must verify source IP and/or configured signature.

Acceptance:

```bash
curl -I http://DOMAIN/
curl -I https://DOMAIN/
curl -s https://DOMAIN/health
curl -I https://DOMAIN/admin/
```

## 6. Yandex Maps

Provider setup:

- Enable Geosuggest/Suggest API on the Suggest key.
- Enable Geocoder HTTP API on the Geocoder key.
- Restrict the keys by domain and/or server IP where the provider supports it.
- Record daily request limits and billing threshold.

App requirements:

- Keys stay in server env only:
  `YANDEX_MAPS_SUGGEST_API_KEY` and `YANDEX_MAPS_GEOCODER_API_KEY`.
- `YANDEX_MAPS_API_KEY` is only a legacy/common fallback.
- Frontend calls Aura Core API proxy, not Yandex directly.
- Suggest failure may degrade to manual text input.
- Geocoder failure must block delivery address validation.
- Typed addresses without coordinates must be geocoded on save/order validation.

Production probe:

```bash
docker compose exec -T core-api python3 -c "
import httpx, os
k = os.getenv('YANDEX_MAPS_GEOCODER_API_KEY') or os.getenv('YANDEX_MAPS_API_KEY','')
print('key-present:', bool(k), 'len:', len(k))
r = httpx.get(
    'https://geocode-maps.yandex.ru/1.x/',
    params={'geocode':'Москва','apikey':k,'format':'json'},
    timeout=5,
)
print('HTTP', r.status_code, r.text[:160])
"
```

Acceptance:

- Valid key returns HTTP 200 from provider probe.
- Customer address suggest returns useful options.
- Manual typed delivery address validates or fails with a user-safe error.

## 7. SMS.ru

Provider setup:

- Real SMS.ru account.
- Balance funded.
- `api_id` created.
- Sender name requested and approved if using a branded sender.
- Daily spend/volume limit configured.
- OTP message length reviewed to avoid accidental multi-segment cost.

App requirements:

- `SMS_BACKEND=smsru`.
- `SMSRU_API_KEY` set.
- OTP rate limits remain enforced in Core API.
- Logs do not include raw phone numbers, OTP codes, JWTs, API keys, or SMS body.

Acceptance:

- Controlled phone receives OTP.
- OTP verify returns JWT.
- `sms-worker` logs contain `[SmsWorker][send_otp][BLOCK_SMSRU_CALL]`.
- Captured logs do not expose raw PII/secrets.

## 8. YuKassa

Provider setup:

- Shop credentials available.
- Test and live modes understood.
- Webhook URL set to `https://DOMAIN/api/webhooks/yukassa`.
- Fiscalization/54-FZ receipt path confirmed before real payments.
- Refund procedure agreed with the shop operator.

App requirements:

- `YUKASSA_BACKEND=live`.
- `YUKASSA_BASE_URL=https://api.yookassa.ru/v3`.
- `YUKASSA_SHOP_ID` and `YUKASSA_SECRET_KEY` set.
- Webhook verification uses IP whitelist and/or signature.
- Payment/refund operations remain idempotent.

Acceptance:

- Controlled payment redirects to YuKassa confirmation.
- `payment.succeeded` webhook moves Payment to `SUCCEEDED` and Order to `PAID`.
- Duplicate webhook does not double-apply side effects.
- Invalid webhook source/signature is rejected.
- Refund path works in test mode before live use.
- Receipt/fiscal status is visible and correct in provider tooling.

## 9. Menu Media

Current product model:

- Admin edits `media_type`, `media_url`, and `media_poster_url`.
- Binary upload/storage is out of v1.
- Valid paths must live under `/media/menu/`.

Production options:

| Option | Pros | Cons |
|--------|------|------|
| Bake approved media into frontend/nginx image | Simple immutable deploy | New media requires image rebuild. |
| Mount `/srv/aura-coffee/media/menu` read-only into nginx | Content updates without rebuild | Need backup and content deploy discipline. |
| External object storage/CDN | Scales better | Current validators reject external/signed URLs, so this is not v1-compatible without code/PDD changes. |

Recommended v1:

- Host directory `/srv/aura-coffee/media/menu`.
- Mount read-only to nginx.
- Include media directory in backup or content sync plan.

Acceptance:

```bash
curl -I https://DOMAIN/media/menu/example/poster.webp
curl -I https://DOMAIN/media/menu/example/hero.mp4
```

## 10. Backups And Monitoring

Minimum operations:

- Daily Postgres dump.
- Retain at least 7 daily and 4 weekly backups.
- Restore drill before go-live.
- Disk usage alert.
- Container health check.
- TLS certificate expiry alert.
- SMS.ru balance alert.
- Yandex quota/billing alert.
- YuKassa failed webhook/payment alert.

Suggested backup command shape:

```bash
scripts/production/install-ops-cron.sh \
  --staging-auth \
  /opt/aura-coffee/.env.production

scripts/production/backup-postgres.sh \
  --staging-auth \
  --weekly \
  /opt/aura-coffee/.env.production

scripts/production/restore-postgres.sh \
  --staging-auth \
  /opt/aura-coffee/.env.production \
  /var/backups/aura-coffee/postgres/aura_daily_YYYYMMDDTHHMMSSZ.sql.gz
```

Acceptance:

- Backup file exists.
- Restore into a scratch database succeeds.
- A readiness check passes after restore.
- Deploy-user cron contains the managed `AURA_COFFEE_OPS` block.
- `scripts/production/check-ops-health.sh --staging-auth
  /opt/aura-coffee/.env.production` exits 0.

Closed-staging result on 2026-05-09: passed with Alembic `0011 (head)`,
representative row counts, scratch DB cleanup, and staging `/health` OK.
Recurring ops schedule result on 2026-05-10: deploy-user cron installed daily
and weekly backups plus a 15-minute ops health check.

## 11. Legal And Business Launch Checks

This section needs owner confirmation before real customers use the site:

- 152-FZ personal data operator notification or applicable exception.
- Russian data localization confirmed by hosting region/provider.
- Privacy policy and consent text published.
- Public offer/terms for online orders published if required by business.
- 54-FZ fiscal receipt flow confirmed.
- Refund and cancellation policy matches the PDD and real shop process.
- Staff access policy and password rotation process agreed.

These are not optional technical cleanup. They can block the launch.
