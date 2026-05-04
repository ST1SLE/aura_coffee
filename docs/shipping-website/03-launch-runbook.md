# Launch Runbook

This runbook is written for the recommended single-VPS Docker Compose launch.
Adjust commands if the final hosting decision changes.

## Operating Rule

Production work is done in packets. Each packet ends with:

- files changed;
- commands run;
- verification evidence;
- LDD markers asserted or why LDD did not apply;
- rollback path.

Never put real secrets in command output, docs, Git, issue comments, or logs.

## Preflight: Local Production-Like Dry Run

Goal: prove production build/deployment mechanics without real providers.

Commands:

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml config
docker compose -f docker-compose.yml -f docker-compose.production.yml build
docker compose -f docker-compose.yml -f docker-compose.production.yml up -d
docker compose -f docker-compose.yml -f docker-compose.production.yml ps
curl -s http://localhost/health
```

Expected:

- Only nginx is reachable from the host.
- Customer SPA loads.
- Admin SPA loads under `/admin/`.
- `/health` returns `status=ok`.
- Fake/log provider mode works if the dry-run env uses fake/log backends.

Do not use live provider credentials in local dry-runs.

## Server Bootstrap

Run on the VPS as the deploy user, adjusting paths to the final decision:

```bash
sudo mkdir -p /opt/aura-coffee
sudo mkdir -p /var/backups/aura-coffee/postgres
sudo mkdir -p /srv/aura-coffee/media/menu
sudo chown -R "$USER":"$USER" /opt/aura-coffee /srv/aura-coffee
```

Install Docker and Compose from official packages or provider image.

Firewall baseline:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status verbose
```

Acceptance:

- SSH remains reachable.
- Only `22`, `80`, `443` are open publicly.
- Docker commands work for deploy user.

## First Server Deploy

1. Put code under `/opt/aura-coffee/app`.
2. Put real env at `/opt/aura-coffee/.env.production`.
3. Ensure the production Compose overlay reads the server env file.
4. Build and boot.

Command shape:

```bash
cd /opt/aura-coffee/app
docker compose --env-file /opt/aura-coffee/.env.production \
  -f docker-compose.yml \
  -f docker-compose.production.yml \
  up -d --build
```

Readiness:

```bash
docker compose --env-file /opt/aura-coffee/.env.production \
  -f docker-compose.yml \
  -f docker-compose.production.yml \
  ps

curl -s http://localhost/health
```

Expected:

- `db-migrate` exits successfully.
- Long-running app services are up.
- `core-api`, `payment-webhook`, workers, Postgres, and Redis are not published
  to public host ports.

## TLS Issuance

Before certificate issuance:

- DNS `A` record points to the VPS.
- HTTP on port `80` reaches nginx.
- nginx uses the final `server_name`.

Certbot shape if TLS is host-managed:

```bash
sudo certbot --nginx -d DOMAIN -d www.DOMAIN
```

After issuance:

```bash
curl -I http://DOMAIN/
curl -I https://DOMAIN/
curl -s https://DOMAIN/health
```

Expected:

- HTTP redirects to HTTPS.
- HTTPS certificate is valid.
- `/health` returns OK through public domain.

## Provider Smoke Tests

### Yandex

```bash
docker compose --env-file /opt/aura-coffee/.env.production \
  -f docker-compose.yml \
  -f docker-compose.production.yml \
  exec -T core-api python3 -c "
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

Expected:

- HTTP 200 from Yandex.
- Customer address suggest works through `https://DOMAIN/api/v1/maps/suggest`.
- Manual typed delivery address geocodes or fails safely.

### SMS.ru

Controlled test:

1. Request OTP from customer UI using an allowed test phone.
2. Confirm SMS arrives.
3. Verify OTP.
4. Inspect logs for redaction.

Log check:

```bash
docker compose --env-file /opt/aura-coffee/.env.production \
  -f docker-compose.yml \
  -f docker-compose.production.yml \
  logs --tail 100 sms-worker
```

Expected:

- OTP arrives.
- Logs contain markers, not raw phone, OTP, message body, JWT, or API key.

### YuKassa

Controlled test:

1. Create a small pickup order.
2. Follow YuKassa confirmation URL.
3. Complete payment in test mode first.
4. Confirm webhook reaches `https://DOMAIN/api/webhooks/yukassa`.
5. Confirm order moves `CREATED -> PAID`.
6. Confirm receipt/fiscal status in provider tooling.
7. Test refund/cancel path before live mode.

Expected:

- Webhook returns success after processing.
- Duplicate webhook is idempotent.
- Invalid webhook source/signature is rejected.
- Logs do not include raw webhook body or secrets.

## Full End-To-End Launch Smoke

Run from a real browser on mobile width and desktop width:

1. Load `https://DOMAIN/`.
2. Browse menu.
3. Register/login with SMS OTP.
4. Add item to cart.
5. Create pickup order.
6. Pay through YuKassa.
7. Confirm order page changes to paid.
8. Staff logs in at `/admin/`.
9. Barista changes order to preparing and ready.
10. Customer receives in-app/SMS notification as expected.
11. Run delivery path with an in-zone address.
12. Courier role sees only courier surfaces.
13. Admin cancel/refund path works on a controlled order.

Technical checks:

```bash
curl -I https://DOMAIN/
curl -I https://DOMAIN/admin/
curl -s https://DOMAIN/health
docker compose --env-file /opt/aura-coffee/.env.production \
  -f docker-compose.yml \
  -f docker-compose.production.yml \
  ps
```

Log checks:

```bash
docker compose --env-file /opt/aura-coffee/.env.production \
  -f docker-compose.yml \
  -f docker-compose.production.yml \
  logs --tail 200 core-api payment-webhook payment-worker sms-worker nginx
```

Expected:

- No raw phone numbers.
- No OTP codes.
- No JWTs.
- No API keys.
- No full addresses.
- No raw YuKassa webhook bodies.
- No payment PAN or card details.

## Backup Verification

Before live customer traffic:

```bash
BACKUP="/var/backups/aura-coffee/postgres/aura_$(date -u +%Y%m%dT%H%M%SZ).sql.gz"
docker compose --env-file /opt/aura-coffee/.env.production \
  -f docker-compose.yml \
  -f docker-compose.production.yml \
  exec -T postgres sh -lc 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  | gzip > "$BACKUP"
ls -lh "$BACKUP"
```

Restore drill:

- Restore into a scratch database or staging stack.
- Run migrations/readiness checks.
- Confirm representative rows are present.

Do not wait for an incident to test restore.

## Cutover Checklist

Only cut over after all are true:

- DNS points to production.
- HTTPS valid.
- Production Compose uses non-dev service shape.
- Database and Redis are private.
- Real production env has no placeholders.
- SMS.ru OTP works.
- Yandex suggest/geocode works.
- YuKassa test payment and refund work.
- Fiscal receipt path is confirmed.
- Backup and restore drill completed.
- Legal/accounting checks are accepted.
- Staff accounts are created with strong credentials.
- Manual end-to-end smoke passed.

Cutover actions:

1. Take final backup.
2. Deploy final images/config.
3. Enable YuKassa live webhook.
4. Enable live SMS.ru if not already live.
5. Place one controlled real order.
6. Monitor logs and provider dashboards for 30-60 minutes.

## Rollback

Use the least destructive rollback that fixes the incident.

### Config or Image Regression

```bash
cd /opt/aura-coffee/app
git checkout PREVIOUS_RELEASE_TAG_OR_COMMIT
docker compose --env-file /opt/aura-coffee/.env.production \
  -f docker-compose.yml \
  -f docker-compose.production.yml \
  up -d --build
```

### Bad Provider Webhook

- Disable YuKassa webhook in dashboard or point it back to staging.
- Keep the site up if orders can be paused safely.
- Do not delete payment/refund rows.

### Database Corruption

- Stop write traffic first.
- Identify last known good backup.
- Restore only after business owner accepts loss of writes after backup time.
- Preserve corrupted volume for forensic inspection.

### TLS Failure

- Revert nginx TLS config to last known good config.
- Renew/reissue cert.
- Do not enable HSTS until this path has been proven.

## Post-Launch Monitoring

First day:

- Check `/health` every 5 minutes manually or with uptime monitor.
- Watch SMS.ru balance and error rates.
- Watch Yandex quota and 4xx/5xx responses.
- Watch YuKassa failed webhooks and payment/refund states.
- Watch disk usage and Postgres volume growth.
- Review redaction-sensitive logs after first real orders.

First week:

- Confirm backups run daily.
- Restore one backup into a scratch environment.
- Rotate initial admin password if it was shared during launch.
- Review failed checkout/order/payment logs.
- Record launch lessons back into this directory.
