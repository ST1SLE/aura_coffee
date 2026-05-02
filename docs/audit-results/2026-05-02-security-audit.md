# Aura Coffee Security Audit - 2026-05-02

Scope: backend auth/RBAC, customer OTP and rate limiting, JWT/session storage,
PII isolation/log redaction, payment webhook trust/replay/idempotency,
CORS/nginx/docker config, frontend auth handling, dependency advisories, secret
exposure patterns, and admin/staff role separation.

Safety notes: real `.env` values were not read. Commands were non-destructive.
Only this report file was created.

## Executive Summary

No P0 issue was confirmed in this static audit, but several P1 issues should be
fixed before a real production deployment:

- Account disable/block is incomplete: blocked customers and deactivated staff
  can keep using existing access tokens, and refresh paths can mint fresh tokens
  without re-checking current account state.
- OTP SMS rate limiting is check-then-increment and can be bypassed under
  concurrent requests.
- Payment webhook ingress does not match the PDD: nginx does not route the
  public `/api/webhooks/yukassa` path to `payment-webhook`, and the webhook app
  trusts spoofable `X-Forwarded-For` without signature verification support.
- Core API accepts empty/placeholder JWT and encryption keys; unlike workers,
  it has no fail-fast secret safety rail.
- Customer refresh tokens and admin access tokens are stored in localStorage,
  which conflicts with the customer frontend guidance and increases XSS blast
  radius.

The project has good foundations: centralized default-deny RBAC middleware,
route-matrix tests, OTP max-attempt logic, redacted dev SMS logs, and payment
worker idempotency markers. The gaps are mostly around revocation, concurrency,
production ingress hardening, and secrets posture.

## Evidence Commands Run

- `rg -n "INV-002|INV-004|INV-013|INV-015|INV-016|OTP|SMS|JWT|webhook|CORS|PII|redact|rate|auth|payment" docs/...`
- `rg -n "oauth|jwt|JWT|token|localStorage|Authorization|Bearer|login|logout|role|OTP|otp|rate|phone|redact|YUKASSA|webhook|X-Forwarded|CORS|SECRET|PASSWORD|API_KEY" ...`
- `rg -n "(BEGIN ... KEY|AKIA...|AIza...|sk-...|postgresql://...|JWT_SECRET_KEY=|ENCRYPTION_KEY=|ADMIN_PASSWORD=|YUKASSA_SECRET_KEY=|SMSRU_API_KEY=)" --glob '!**/.env*' ...`
- `npm audit --omit=dev --audit-level=moderate` in `web/customer` - 0 vulnerabilities.
- `npm audit --omit=dev --audit-level=moderate` in `web/admin` - 0 vulnerabilities.
- `uvx --python /usr/bin/python3 pip-audit --progress-spinner off services/core-api` - vulnerable `cryptography 43.0.3`.
- `uvx --python /usr/bin/python3 pip-audit --progress-spinner off services/payment-worker` - no known vulnerabilities.
- `uvx --python /usr/bin/python3 pip-audit --progress-spinner off services/sms-worker` - vulnerable `cryptography 43.0.3`.
- `uvx --python /usr/bin/python3 pip-audit --progress-spinner off packages/shared` - no known vulnerabilities.

## P0 Findings

None confirmed.

## P1 Findings

### P1-1: Blocked/deactivated accounts can keep or regain sessions

Requirement: PDD says blocked users cannot authenticate or create orders
(`docs/PRODUCT_DESIGN_DOCUMENT.md:507-508`). INV-002 requires server-side auth
and role enforcement (`docs/PRODUCT_DESIGN_DOCUMENT.md:31`).

Evidence:

- `verify_code` only checks the OTP result, activates pending users, then issues
  tokens for whatever `user_info.status` is. It does not reject `BLOCKED` or
  `DELETED` after OTP verification
  (`services/core-api/src/core_api/routers/auth.py:159-168`).
- Customer refresh rotation reads only Redis session data and re-issues tokens
  without consulting the `users` table
  (`services/core-api/src/core_api/services/auth.py:114-124`).
- `get_current_user` validates only JWT signature/expiry and returns `sub` +
  `role`; it does not check current user/staff status
  (`services/core-api/src/core_api/deps/auth.py:39-50`).
- Staff login rejects inactive staff
  (`services/core-api/src/core_api/services/staff_auth.py:72-80`), but staff
  refresh trusts Redis `staff_refresh:*` and does not re-read `staff_accounts`
  (`services/core-api/src/core_api/services/staff_auth.py:90-101`).
- `block_user` changes DB state but has no Redis/session revocation path
  (`services/core-api/src/core_api/services/admin_users.py:351-353`).

Impact:

- A blocked customer with a still-valid access token can keep calling customer
  APIs until expiry.
- A blocked customer with a refresh token can mint fresh tokens.
- A staff account disabled after login can keep refreshing if the refresh token
  exists.

Suggested fix:

- Add a session revocation model: store sessions by user/staff id as well as by
  refresh token, and delete those keys on block/deactivate/delete.
- Re-check account status during refresh for customer and staff.
- Re-check status in `get_current_user` for protected mutations, or add a
  version/session counter claim that is invalidated on block.
- Make `verify_code` reject `BLOCKED` and `DELETED` users before issuing tokens.

Verification to add/run:

- Core API tests: blocked customer cannot verify OTP, cannot refresh, and cannot
  create an order with an existing token after block.
- Staff tests: inactive staff refresh returns 401 after `staff_accounts.is_active`
  changes to false.
- Command: `docker compose exec core-api pytest services/core-api/tests/test_auth_endpoints.py services/core-api/tests/test_staff_auth.py services/core-api/tests/test_admin_users_block.py -v`

GRACE/LDD applicability:

- Required. This touches auth, user lifecycle, role checks, and PDD §6.5.
- Assert `[CoreApi][auth.otp_verify][BLOCK_AUTH_VERIFY]` and relevant user state
  transition markers.
- Add redaction assertions: no raw phone, OTP code, JWT, password, or refresh
  token in captured logs.

### P1-2: OTP SMS rate limiting is not atomic under concurrency

Requirement: INV-012 requires max 1 SMS/min, 5/hour, 10/day per phone
(`docs/PRODUCT_DESIGN_DOCUMENT.md:41`). OTP lifecycle says rate limit is checked
before OTP creation (`docs/PRODUCT_DESIGN_DOCUMENT.md:467`).

Evidence:

- `send_code` performs `check_rate_limit`, then later calls
  `increment_rate_limits`, then `create_otp`
  (`services/core-api/src/core_api/routers/auth.py:82-95`).
- `check_rate_limit` is read-only GET/TTL
  (`services/core-api/src/core_api/services/otp.py:143-151`).
- `increment_rate_limits` is a separate pipeline executed after the check
  (`services/core-api/src/core_api/services/otp.py:161-168`).

Impact:

Concurrent requests for the same phone can all observe counters below the limit
before any increments land, causing multiple SMS jobs and cost/abuse exposure.

Suggested fix:

- Replace split check/increment with one Redis Lua script that:
  1. checks all windows,
  2. increments all counters only if allowed,
  3. returns a precise retry-after if denied.
- Consider combining OTP creation into the same script or adding a per-phone
  short lock so exactly one code is generated per allowed window.

Verification to add/run:

- A concurrency regression using `fakeredis` or real Redis: N parallel
  `send-code` calls for one phone produce exactly one success and N-1 `429`.
- Check `Retry-After` on minute/hour/day windows.
- Command: `docker compose exec core-api pytest services/core-api/tests/test_auth_endpoints.py services/core-api/tests/test_verify_409.py -v`

GRACE/LDD applicability:

- Required. This touches OTP/SMS and auth.
- Assert `[CoreApi][auth.otp_request][BLOCK_OTP_GEN]`, `[SmsWorker][send_otp][BLOCK_SMSRU_CALL]`, and no mismatched OTP beliefs.
- Add redaction assertions for phone and OTP code.

### P1-3: Payment webhook public ingress and trust model are incomplete

Requirement: PDD says nginx routes `/api/webhooks/yukassa` to Payment Worker
HTTP and webhook verification must use an IP whitelist, with signature
verification if configured (`docs/PRODUCT_DESIGN_DOCUMENT.md:114-117`,
`docs/PRODUCT_DESIGN_DOCUMENT.md:804-808`,
`docs/PRODUCT_DESIGN_DOCUMENT.md:841-843`). Verification plan expects valid
signature success and invalid signature failure
(`docs/verification-plan.xml:120-125`).

Evidence:

- `deploy/nginx/nginx.conf` proxies all `/api/` traffic to `core-api` and has no
  `payment-webhook` upstream or `/api/webhooks/yukassa` location
  (`deploy/nginx/nginx.conf:17-24`).
- `docker-compose.yml` runs `payment-webhook` internally on port 8241 but does
  not expose it through nginx
  (`docker-compose.yml:156-175`, `docker-compose.yml:217-226`).
- The webhook app trusts the first value of `X-Forwarded-For`
  (`services/payment-worker/src/payment_worker/webhook.py:92-99`).
- Nginx currently uses `$proxy_add_x_forwarded_for`, which preserves any
  client-supplied `X-Forwarded-For` before appending `$remote_addr`
  (`deploy/nginx/nginx.conf:20-23`). If this pattern is copied to webhook
  routing, a client can spoof the leftmost IP.
- There is no signature/HMAC verification implementation or setting in
  `services/payment-worker/src/payment_worker/webhook.py`; verification is IP
  only (`services/payment-worker/src/payment_worker/webhook.py:475-481`).

Impact:

- Real YuKassa callbacks sent to the documented public path will not reach the
  payment webhook, so paid orders may remain unpaid.
- If the webhook is later exposed using the current `X-Forwarded-For` trust
  pattern, an attacker can spoof a whitelisted IP unless the reverse proxy
  strips/overwrites that header.
- Without signature verification support, compromise/misrouting of the network
  trust boundary can lead to forged payment/refund state transitions.

Suggested fix:

- Add a dedicated nginx upstream and exact location:
  `/api/webhooks/yukassa` -> `payment-webhook:8241/webhooks/yukassa`.
- For webhook traffic, overwrite forwarded IP headers instead of appending:
  `proxy_set_header X-Forwarded-For $remote_addr;` or use a trusted-proxy
  mechanism and validate `request.client.host` is the proxy.
- Add optional signature verification if YuKassa dashboard signature settings
  are enabled; reject invalid signatures before JSON parsing/state mutation.
- Add a smoke test that posts through nginx to `/api/webhooks/yukassa`.

Verification to add/run:

- `docker compose exec payment-worker pytest services/payment-worker/tests/test_webhook.py -v`
- Add tests for spoofed `X-Forwarded-For`, nginx routed webhook path, and invalid
  signature rejection without DB writes.

GRACE/LDD applicability:

- Required. This touches payment webhook verification and payment/order state
  transitions.
- Assert `[PaymentWorker][process_webhook][BLOCK_WEBHOOK_VERIFY]`,
  `[PaymentWorker][process_webhook][BLOCK_TX_PAYMENT]`, and
  `[PaymentWorker][process_webhook][BLOCK_STATE_TRANSITION]`.
- Add redaction assertions for raw webhook body and payment secrets.

### P1-4: Core API accepts weak or placeholder JWT/encryption secrets

Requirement: INV-015 requires secrets in env and safe handling
(`docs/PRODUCT_DESIGN_DOCUMENT.md:44`).

Evidence:

- Core settings default `jwt_secret_key` and `encryption_key` to empty strings
  with no validator (`services/core-api/src/core_api/settings.py:11-15`).
- `.env.example` ships placeholder JWT and all-zero encryption values
  (`.env.example:19-21`). These are dev defaults, but Core API does not reject
  them outside dev.
- JWT signing/verification uses `settings.jwt_secret_key`
  (`services/core-api/src/core_api/services/auth.py:64-71`,
  `services/core-api/src/core_api/services/auth.py:147-150`).
- Phone encryption uses `settings.encryption_key`
  (`services/core-api/src/core_api/services/user.py:77-84`).

Impact:

A copied dev env can produce forgeable JWTs and decryptable PII in any
non-dev/staging/prod environment.

Suggested fix:

- Add Core API settings validation similar to payment/sms worker safety rails.
- Reject empty, placeholder, short, or all-zero `JWT_SECRET_KEY` and
  `ENCRYPTION_KEY` unless an explicit `AURA_ENV=dev` is set.
- Require 32-byte hex for `ENCRYPTION_KEY`; require a high-entropy JWT secret.
- Add startup tests for rejected placeholder secrets.

Verification to add/run:

- New settings tests for empty, placeholder, all-zero, malformed hex, and valid
  secrets.
- Command: `docker compose exec core-api pytest services/core-api/tests/test_settings*.py services/core-api/tests/test_jwt.py -v`

GRACE/LDD applicability:

- Required if implemented. This touches auth, PII encryption, and secrets.
- No state-machine marker is central, but redaction assertions and fail-fast
  startup tests are required.

### P1-5: Browser token storage leaves long-lived sessions exposed to XSS

Requirement: customer frontend AGENTS says the customer app must not store auth
tokens in localStorage (`web/customer/AGENTS.md:49-53`). The current
implementation explicitly keeps refresh tokens there.

Evidence:

- Customer `token.ts` stores refresh token in localStorage
  (`web/customer/src/auth/token.ts:60-79`) and the module contract says this is
  for silent refresh (`web/customer/src/auth/token.ts:1-8`).
- `AuthProvider` silently refreshes from that localStorage value on mount
  (`web/customer/src/auth/AuthProvider.tsx:84-100`).
- Admin client stores the staff access token in localStorage
  (`web/admin/src/api/client.ts:25-45`).

Impact:

Any XSS in either SPA can steal customer refresh tokens or staff access tokens.
Customer refresh tokens are especially sensitive because they last longer than
access tokens and can be rotated.

Suggested fix:

- Move refresh tokens to `HttpOnly; Secure; SameSite=Lax/Strict` cookies.
- Keep access tokens in memory only, or use a backend-for-frontend session cookie
  model.
- Add CSP and avoid inline script allowances in production nginx.
- For admin, either use HttpOnly session cookies or at minimum keep access token
  in memory and require re-login on reload.

Verification to add/run:

- Frontend tests asserting no auth tokens are written to localStorage.
- Backend refresh/logout tests using cookies and CSRF protections if cookies are
  introduced.

GRACE/LDD applicability:

- Required if backend auth endpoints change. This touches auth/session handling.
- Add redaction assertions for JWT and refresh token values.
- If frontend-only storage is changed without backend semantics, LDD markers are
  not applicable, but auth-flow tests are still required.

## P2 Findings

### P2-1: `send-code` returns deterministic `phone_hash` to public clients

Evidence:

- `send_code` returns `{"message": "OTP sent", "phone_hash": phone_hash}`
  (`services/core-api/src/core_api/routers/auth.py:111`).
- `phone_hash` is unsalted SHA-256 of the normalized phone
  (`services/core-api/src/core_api/utils/crypto.py:7-9`).

Impact:

Phone numbers have small search space. A deterministic unsalted hash returned to
the browser can be brute-forced offline and used to correlate logs, Redis keys,
or leaked data.

Suggested fix:

- Do not return `phone_hash` to the client. Return only a generic success
  message.
- If the UI needs a request handle, issue a random opaque OTP request id that
  cannot be mapped back to the phone.

Verification to add/run:

- Update auth endpoint tests to assert no `phone_hash` in the response.
- Add API schema parity check for `SendCodeResponse`.

GRACE/LDD applicability:

- Required. This touches OTP/customer identity and PII.
- Assert no raw phone/hash in logs or response where not required.

### P2-2: SMS.ru live error logging may leak provider-echoed phone/message data

Evidence:

- The live SMS transport sends `to` and `msg` to SMS.ru
  (`services/sms-worker/src/sms_worker/clients/smsru.py:48-55`).
- On provider error, it logs the full response payload
  (`services/sms-worker/src/sms_worker/clients/smsru.py:61-65`).
- Verification policy forbids raw phone, OTP code, and PII in logs
  (`docs/verification-plan.xml:10-12`).

Impact:

If SMS.ru error responses include recipient numbers, per-number result maps, or
echoed message content, logs can contain raw phone numbers or OTP codes.

Suggested fix:

- Replace full payload logging with a redacted projection: provider status code,
  status text, and a hash-prefix recipient reference only.
- Add a redaction helper and tests with a fake provider response containing a
  phone and OTP code.

Verification to add/run:

- `pytest services/sms-worker/tests/ -v`
- Add `GraceLogCapture` or logger capture assertion that phone, OTP, JWT, API key,
  and SMS body never appear.

GRACE/LDD applicability:

- Required. This touches SMS and PII logging.
- Assert `[SmsWorker][send_otp][BLOCK_SMSRU_CALL]` and redaction.

### P2-3: Python dependency audit reports vulnerable `cryptography`

Evidence:

- `uvx --python /usr/bin/python3 pip-audit --progress-spinner off services/core-api`
  reported `cryptography 43.0.3` with `CVE-2024-12797`,
  `CVE-2026-26007`, and `CVE-2026-34073`.
- The same command for `services/sms-worker` reported the same package/CVEs.
- Core lock pins `cryptography` to `43.0.3`
  (`services/core-api/uv.lock:325-326`).
- Core and SMS pyprojects constrain `cryptography>=42.0,<44.0`
  (`services/core-api/pyproject.toml:18`,
  `services/sms-worker/pyproject.toml:13`).

Impact:

`cryptography` is used for AES-GCM phone encryption/decryption in core-api and
sms-worker, so this dependency is in the PII path.

Suggested fix:

- Raise the constraint to a fixed version range that includes the latest safe
  version, for example `cryptography>=46.0.6,<47.0`, after compatibility
  verification.
- Regenerate locks and rebuild containers.

Verification to add/run:

- `uvx --python /usr/bin/python3 pip-audit --progress-spinner off services/core-api`
- `uvx --python /usr/bin/python3 pip-audit --progress-spinner off services/sms-worker`
- `docker compose exec core-api pytest services/core-api/tests/test_user_service.py services/core-api/tests/test_auth_endpoints.py -v`
- `pytest services/sms-worker/tests/ -v`

GRACE/LDD applicability:

- Not required for the dependency bump itself if encryption behavior is unchanged.
- Redaction and auth/OTP tests are still prudent because the dependency sits on
  the PII path.

### P2-4: Staff login has no brute-force throttling

Evidence:

- Staff login is public in `PUBLIC_ROUTES`
  (`services/core-api/src/core_api/rbac_matrix.py:123-130`).
- `StaffAuthService.authenticate` performs DB lookup and bcrypt check, but no
  per-login or per-IP rate limiting
  (`services/core-api/src/core_api/services/staff_auth.py:65-82`).

Impact:

The admin/barista/courier login surface can be brute-forced. Bcrypt slows each
attempt, but without throttling the service can be abused for credential attacks
and CPU pressure.

Suggested fix:

- Add Redis-backed rate limits for staff login by normalized login and source IP.
- Return generic 401 on invalid credentials and 429 with retry-after when
  limited.
- Consider staff account lockout or alerting after repeated failures.

Verification to add/run:

- Add tests for per-login and per-IP throttling.
- Command: `docker compose exec core-api pytest services/core-api/tests/test_staff_auth.py -v`

GRACE/LDD applicability:

- Required. This touches auth and role checks.
- Add redaction assertions for password and JWT values.

### P2-5: Courier available feed exposes full delivery address before assignment

Requirement: INV-010 says courier access is limited to delivery orders and
customer data should be minimized (`docs/PRODUCT_DESIGN_DOCUMENT.md:39`).

Evidence:

- `list_available_for_courier` returns `delivery_address_snapshot` for every
  `AWAITING_COURIER` order
  (`services/core-api/src/core_api/services/delivery_assignment.py:315-349`).
- Courier UI displays the address line in the card
  (`web/admin/src/pages/Courier/AssignmentCard.tsx:55-57`).
- The API type includes address line, coordinates, apartment, floor, entrance,
  and comment (`web/admin/src/api/courier.ts:42-57`).

Impact:

Any authenticated courier can inspect full addresses for all unclaimed delivery
orders, not only orders they accepted. This is a privacy/minimum-privilege risk.

Suggested fix:

- Split available feed and claimed-assignment detail:
  - Available list: order id/short id, rough zone, total, requested time.
  - Mine/detail after `take`: full address and delivery comments.
- Keep phone/name out of courier payloads.

Verification to add/run:

- API tests asserting available feed omits apartment/floor/comment/full address
  and mine/detail includes only the courier's own claimed assignment.
- Frontend tests that available cards do not render full address.

GRACE/LDD applicability:

- Required if API payloads change because this touches role separation and PII.
- Add redaction assertions and RBAC tests for courier/customer/admin roles.

## P3 Findings

### P3-1: FastAPI docs and OpenAPI are always public

Evidence:

- RBAC middleware explicitly skips `/docs`, `/redoc`, and `/openapi.json`
  (`services/core-api/src/core_api/middleware/rbac.py:62-64`,
  `services/core-api/src/core_api/middleware/rbac.py:90-92`).

Impact:

Public schema discovery is useful in dev but should be a conscious production
choice.

Suggested fix:

- Add `EXPOSE_API_DOCS=false` or `AURA_ENV=production` behavior that disables
  docs/openapi or protects them behind admin auth/IP allowlist.

GRACE/LDD applicability:

- Not required if this is only an infra/docs visibility toggle. Add route tests.

### P3-2: Secret scanner found committed dev placeholders and historical specs

Evidence:

- The secret-pattern scan excluding `.env*` found dev placeholders in
  `.env.example`, historical OpenSpec docs, and a dev DB URL default in
  `services/sms-worker/src/sms_worker/settings.py:39`.
- No private key blocks, cloud keys, OpenAI-style keys, or obvious production
  API tokens were found by the patterns used.

Impact:

The immediate risk is not leakage of real secrets, but accidental promotion of
dev defaults into non-dev environments.

Suggested fix:

- Keep placeholders but pair them with fail-fast settings validators.
- Add a CI secret scan using a real scanner such as gitleaks or trufflehog with
  allowlisted example placeholders.

GRACE/LDD applicability:

- Not required for CI scanner wiring. Required if changing runtime secret
  validation in auth/PII paths.

## Positive Controls Observed

- Central RBAC middleware is default-deny for unmapped non-public routes
  (`services/core-api/src/core_api/middleware/rbac.py:118-126`).
- Route matrix separates customer/admin/barista/courier access and has tests
  across many route groups (`services/core-api/src/core_api/rbac_matrix.py:38-132`).
- OTP codes are generated with `secrets.randbelow` and attempts are atomically
  checked in Lua (`services/core-api/src/core_api/services/otp.py:180-190`,
  `services/core-api/src/core_api/services/otp.py:40-72`).
- Dev SMS log transport logs hash-prefix metadata, not raw phone/message
  (`services/sms-worker/src/sms_worker/clients/log.py:47-55`).
- Payment webhook idempotency marks events only after DB transaction success
  (`services/payment-worker/src/payment_worker/webhook.py:495-510`).
- `npm audit --omit=dev --audit-level=moderate` found 0 production
  vulnerabilities in both React apps.

## Suggested Remediation Order

1. Fix account revocation/status checks for customer and staff sessions.
2. Make OTP rate-limit check+increment atomic.
3. Correct payment webhook ingress, trusted proxy handling, and signature tests.
4. Add Core API secret safety rails.
5. Move browser refresh/access tokens out of localStorage.
6. Redact SMS.ru live error logs.
7. Upgrade `cryptography` and add dependency audit to CI.
8. Tighten courier PII exposure and production docs visibility.

## GRACE/LDD Summary

Sensitive fixes in P1-1, P1-2, P1-3, P1-4, P1-5, P2-1, P2-2, P2-4, and P2-5
touch auth, role checks, OTP/SMS, payment webhooks, PII, secrets, or state
transitions. Per `docs/verification-plan.xml:10-12`, they must include LDD
marker assertions where available and redaction assertions for raw phone, OTP,
JWT, password, full PAN, API keys, raw webhook bodies, and full addresses.
