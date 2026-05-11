# Aura Coffee Staging Deployment Security Audit

Date: 2026-05-11
Target: closed staging at `https://staging.aura-coffee-bakery.ru`
VPS: `212.8.226.214`
Scope: low-impact defensive deployment audit against the current staging URL and
VPS host. No destructive tests, credential guessing, fuzzing, load testing, or
provider-side mutation drills were run.

## Executive Summary

The closed-staging deployment is production-shaped at the public boundary:
nginx is the only published application container, HTTP redirects to HTTPS,
staging Basic Auth blocks anonymous web/API access, TLS allows only TLS 1.2/1.3,
Postgres/Redis/Core API/payment-webhook/Vite ports are not externally reachable,
and the recurring ops health check is green.

This is acceptable for closed staging, but it is not yet ready for public launch
against malicious traffic. The main open risks are host SSH hardening, address
PII in Core API access logs, intentionally mocked provider modes, and a few
HTTP/header/application hardening items.

## Evidence Collected

Fresh probe time:

- Local operator time: `2026-05-11T17:09:20+03:00`.
- VPS time: `2026-05-11T14:09:21+00:00`.
- Active release path:
  `/opt/aura-coffee/releases/331dd3689bb0-codex-video-budget-20260510T100815Z`.
- Active Compose project: `app`, `running(9)`, using production, TLS, and
  staging-auth overlays.

Public boundary:

- DNS: `staging.aura-coffee-bakery.ru -> 212.8.226.214`.
- `http://staging.aura-coffee-bakery.ru/` returns `301` to HTTPS.
- Anonymous `https://staging.aura-coffee-bakery.ru/` returns `401`.
- Anonymous `https://staging.aura-coffee-bakery.ru/api/v1/menu` returns `401`.
- Certificate expires `Aug 4 11:45:09 2026 GMT`.
- TLS 1.0 and TLS 1.1 fail; TLS 1.2 and TLS 1.3 succeed.
- External service-port probe:
  `22`, `80`, `443` open; `5432`, `6379`, `8000`, `8240`, `8241`, `5173`,
  `5174` closed.

VPS and Compose posture:

- `docker ps` publishes only nginx on `0.0.0.0:80` and `0.0.0.0:443`.
- Core API, payment webhook, workers, Postgres, and Redis are Docker-internal.
- `ss -tulpn` shows public listeners only for SSH, HTTP, and HTTPS.
- `ufw` allows only `22/tcp`, `80/tcp`, and `443/tcp`, with default incoming
  deny.
- Ops health check: all 9 Compose services running, public health OK, TLS OK,
  daily backup fresh, weekly backup present, disk usage 20%, ops cron marker
  present.
- Ops health warning: provider dashboard alerts remain manual for SMS balance,
  Yandex quota, and YuKassa failures.

Application boundary:

- With the staging cookie, `/health`, `/api/v1/menu`, and `/admin/` return
  `200`; nonexistent media under `/media/menu/` returns `404`.
- Anonymous webhook POST to `/api/webhooks/yukassa` returns `401`.
- Authenticated webhook POST with spoofed `X-Forwarded-For: 127.0.0.1` returns
  `403`, which confirms nginx overwrites the forwarded source on the exact
  webhook route.
- Protected API paths such as `/api/v1/admin/orders`,
  `/api/v1/admin/menu/items`, `/api/v1/profile`, and `/api/v1/orders` return
  `401` without an application JWT even when the staging cookie is present.
- CORS allows `https://staging.aura-coffee-bakery.ru`; an `evil.example` origin
  does not receive `Access-Control-Allow-Origin`.

Runtime config posture:

- `AURA_ENV=production`.
- `CORS_ORIGINS=https://staging.aura-coffee-bakery.ru`.
- `SMS_BACKEND=log`.
- `YUKASSA_BACKEND=fake`.
- Yandex split keys are present; raw key material was not recorded.

## Findings

### High: SSH Allows Password And Root Login At The Policy Level

Evidence:

- `sshd -T` reports `passwordauthentication yes` and `permitrootlogin yes`.
- `/etc/ssh/sshd_config` contains `PermitRootLogin yes`.
- Cloud-init snippets conflict: one file sets `PasswordAuthentication no`,
  another sets `PasswordAuthentication yes`; effective config is `yes`.
- `passwd -S root` reports a set root password hash; `deploy` is locked.
- `fail2ban` is active, but SSH is under continuous attack: over 15k failed SSH
  attempts and over 1k total bans were recorded by the current jail status.

Impact:

Closed staging is exposed to internet-wide SSH brute force. Fail2ban reduces the
risk, but allowing password authentication and root login keeps an avoidable
remote attack surface open.

Required remediation:

- Set effective SSH policy to key-only deploy access:
  `PasswordAuthentication no`, `PermitRootLogin no`,
  `KbdInteractiveAuthentication no`.
- Consider `X11Forwarding no` and `AllowTcpForwarding no` unless a known ops
  workflow needs them.
- Validate with `sshd -t`, reload SSH, and verify a new key-based deploy
  session before closing the existing session.
- Consider locking the root password after confirming the provider console and
  deploy sudo recovery path.

### High: Core API Access Logs Contain Map Query Strings With Address PII

Evidence:

- nginx production access logs use the no-query format.
- Core API container logs still include request targets such as
  `/api/v1/maps/suggest?text=...`.
- A 24-hour scan found 21 query-string hits in `app-core-api-1` logs. No raw
  phone numbers, JWTs, or OTP values were found in the sampled service logs.

Impact:

Typed address text can enter app/container logs, which conflicts with INV-013
treatment of full addresses as PII. This remains true even though nginx access
logs omit query strings.

Required remediation:

- Prefer changing map suggest/geocode routes from GET query parameters to POST
  bodies.
- Also add access-log redaction or suppression for map-query routes at the ASGI
  or server logging layer.
- Add a redaction regression test that exercises `/api/v1/maps/*` and asserts
  full address text is absent from captured logs.

### High Before Public Launch: Mock Provider Modes Are Active

Evidence:

- VPS config reports `SMS_BACKEND=log` and `YUKASSA_BACKEND=fake`.
- Ops health intentionally reports those provider modes as OK for closed
  staging.

Impact:

This is safe for closed staging only. Public ordering with these modes would
allow fake payment success and log-mode OTP behavior.

Required remediation:

- Keep staging closed while mock modes are active.
- Before public launch, switch to `SMS_BACKEND=smsru` and
  `YUKASSA_BACKEND=live`, then run controlled SMS, payment, webhook, refund,
  duplicate-webhook, and invalid-source drills.
- Keep provider dashboard alerting in the launch checklist.

### Medium: Security Headers Are Minimal

Evidence:

- Authenticated and anonymous responses include `X-Content-Type-Options:
  nosniff` and `Referrer-Policy: strict-origin-when-cross-origin`.
- `Content-Security-Policy`, `X-Frame-Options` or `frame-ancestors`,
  `Permissions-Policy`, and HSTS are not currently present.

Impact:

The closed staging Basic Auth layer reduces exposure, but public launch should
have stronger browser-side protections, especially for the staff/admin surface.

Recommended remediation:

- Add a tested CSP for the customer and admin SPAs.
- Add `frame-ancestors 'none'` or equivalent anti-framing policy.
- Add a narrow `Permissions-Policy`.
- Enable HSTS only after HTTPS rollback and renewal behavior are proven.

### Medium: Provider Dashboard Alerting Is Still Manual

Evidence:

- `check-ops-health.sh` reports:
  `warn: provider_dashboard_alerts_manual=sms_balance_yandex_quota_yukassa_failures`.

Impact:

The server can be healthy while external provider balance, quota, billing, or
webhook delivery is failing.

Recommended remediation:

- Add operational checks or owner-facing dashboard alerts for SMS.ru balance,
  Yandex quota/billing, and YuKassa failed payments/webhooks before public
  launch.

### Low: Common Sensitive Paths Fall Through To SPA HTML

Evidence:

- With staging access, paths such as `/.env`, `/.git/config`, `/server-status`,
  `/docs`, `/redoc`, and `/openapi.json` returned HTML or authenticated API
  responses, not raw secret files.

Impact:

No secret leakage was observed, but returning `200` SPA HTML for common scanner
paths creates noisy false positives and weakens the deployment boundary signal.

Recommended remediation:

- Add explicit nginx denies or `404` responses for dotfiles, `/.git/*`,
  `/.env*`, `/server-status`, and any non-public docs paths.

## Positive Controls Confirmed

- Public app exposure is limited to nginx on `80/443`.
- PostgreSQL, Redis, Core API, payment webhook, and frontend dev ports are not
  externally reachable.
- TLS is valid and rejects TLS 1.0/1.1.
- Closed staging Basic Auth protects customer, admin, API, and health endpoints.
- Server-side API auth still protects privileged/customer routes behind staging
  auth.
- Webhook ingress through nginx resists client-supplied forwarded-IP spoofing in
  the tested path.
- CORS does not grant `Access-Control-Allow-Origin` to an untrusted origin.
- Backups and recurring ops cron are active.
- No raw phone numbers, JWTs, or OTP code fields were found in the sampled
  24-hour service logs.

## Recommended Next Actions

1. Harden SSH first: disable password authentication and root login, validate
   with a new key-based session, then reload SSH.
2. Stop address PII from entering Core API logs by moving map search/geocode to
   POST bodies and redacting or suppressing access logs for those paths.
3. Add CSP, anti-framing, and permissions headers in the TLS nginx template.
4. Keep the site closed while `SMS_BACKEND=log` and `YUKASSA_BACKEND=fake` are
   active.
5. Add explicit nginx denies for common sensitive scanner paths.
6. Add provider dashboard/alert checks for SMS.ru, Yandex, and YuKassa before
   public launch.

## Verification Commands Run

Representative commands:

```bash
dig +short staging.aura-coffee-bakery.ru A
curl -sS -m 10 -o /dev/null -w '%{http_code} %{redirect_url}\n' \
  http://staging.aura-coffee-bakery.ru/
curl -sS -m 10 -o /dev/null -w '%{http_code}\n' \
  https://staging.aura-coffee-bakery.ru/
openssl s_client -servername staging.aura-coffee-bakery.ru \
  -connect staging.aura-coffee-bakery.ru:443 </dev/null \
  | openssl x509 -noout -enddate
ssh -i ~/.ssh/aura-vps deploy@212.8.226.214 'docker ps'
ssh -i ~/.ssh/aura-vps deploy@212.8.226.214 'sudo -n ss -tulpn'
ssh -i ~/.ssh/aura-vps deploy@212.8.226.214 'sudo -n sshd -T'
ssh -i ~/.ssh/aura-vps deploy@212.8.226.214 \
  'cd /opt/aura-coffee/app && scripts/production/check-ops-health.sh \
   --staging-auth --domain staging.aura-coffee-bakery.ru \
   /opt/aura-coffee/.env.production /var/backups/aura-coffee/postgres'
```

## GRACE / LDD Gate

This packet is audit documentation only. It did not change runtime code, state
machines, transaction boundaries, auth behavior, OTP/SMS/payment code, PII
storage, or required log markers. LDD assertions are therefore not applicable.
