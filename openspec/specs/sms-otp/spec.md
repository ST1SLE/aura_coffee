## ADDED Requirements

### Requirement: OTP generation and storage
The system SHALL generate a 6-digit cryptographically random OTP code upon receiving a send-code request for a valid phone number. The OTP SHALL be stored in Redis at key `otp:{phone_hash}` as JSON `{"code", "attempts", "status"}` with TTL 300 seconds (§6.4).

#### Scenario: Successful OTP creation for new phone
- **WHEN** client sends `POST /api/v1/auth/send-code` with a valid E.164 phone number
- **AND** rate-limit is not exceeded (INV-012)
- **THEN** system creates OTP with status `CREATED`, stores in Redis with TTL 300s, and enqueues SMS task to sms-worker

#### Scenario: OTP creation replaces existing active OTP
- **WHEN** client requests a new OTP for a phone that already has an active OTP in Redis
- **AND** rate-limit is not exceeded
- **THEN** system invalidates the previous OTP and creates a new one

### Requirement: OTP rate-limiting
The system SHALL enforce rate limits per phone number before creating OTP (INV-012): max 1 per 60s, max 5 per 3600s, max 10 per 86400s. Rate-limit counters SHALL be stored in Redis keys `sms_rate:{phone_hash}:min`, `sms_rate:{phone_hash}:hour`, `sms_rate:{phone_hash}:day` (§5.3). Rate-limit check SHALL occur BEFORE OTP creation (§6.4, §7.8).

#### Scenario: Rate limit not exceeded
- **WHEN** client requests OTP and all three rate-limit counters are below their thresholds
- **THEN** system increments all three counters (setting TTL on new keys) and proceeds with OTP creation

#### Scenario: Per-minute rate limit exceeded
- **WHEN** client requests OTP and `sms_rate:{phone_hash}:min` >= 1
- **THEN** system returns HTTP 429 with `retry_after` indicating seconds until the counter expires
- **AND** no OTP is created and no SMS task is enqueued

#### Scenario: Per-hour rate limit exceeded
- **WHEN** client requests OTP and `sms_rate:{phone_hash}:hour` >= 5
- **THEN** system returns HTTP 429 with `retry_after` indicating seconds until the counter expires

#### Scenario: Per-day rate limit exceeded
- **WHEN** client requests OTP and `sms_rate:{phone_hash}:day` >= 10
- **THEN** system returns HTTP 429 with `retry_after` indicating seconds until the counter expires

### Requirement: OTP verification
The system SHALL verify OTP by comparing the submitted code against the stored code in Redis. Verification SHALL use a Redis Lua script to ensure atomicity of check + attempt increment. Maximum 5 attempts allowed (§6.4).

#### Scenario: Correct code submitted
- **WHEN** client sends `POST /api/v1/auth/verify-code` with correct code
- **AND** OTP status is `SENT` and attempts < 5 and TTL has not expired
- **THEN** system transitions OTP to `VERIFIED`, deletes OTP from Redis, and returns JWT tokens

#### Scenario: Incorrect code submitted with remaining attempts
- **WHEN** client submits incorrect code and attempts < 4
- **THEN** system increments attempts counter and returns HTTP 401 with `remaining_attempts`

#### Scenario: Fifth incorrect attempt exhausts OTP
- **WHEN** client submits incorrect code and attempts reaches 5
- **THEN** system transitions OTP to `FAILED`, deletes OTP from Redis, and returns HTTP 401 with message indicating code is invalidated (§6.4: SENT → FAILED)

#### Scenario: Code submitted for expired OTP
- **WHEN** client submits code but OTP key does not exist in Redis (TTL expired)
- **THEN** system returns HTTP 410 indicating code has expired

#### Scenario: Code submitted before SMS sent (status CREATED)
- **WHEN** client submits code while OTP status is still `CREATED`
- **THEN** system returns HTTP 409 indicating code is not yet delivered (§6.4: CREATED → VERIFIED forbidden)
- **AND** HTTP 409 is documented in the endpoint's OpenAPI `responses` dict with `ErrorResponse` model

### Requirement: SMS delivery via sms-worker
The system SHALL dispatch OTP SMS delivery to sms-worker as a Celery task. sms-worker SHALL route the dispatch through a configurable transport selected by the `SMS_BACKEND` environment variable with values `log` and `smsru`.

When `SMS_BACKEND=smsru`, the worker SHALL call SMS.ru `POST /sms/send` with message `"Код подтверждения: {code}. Aura Coffee"` (§8.2, max 70 chars). When `SMS_BACKEND=log`, the worker SHALL write the phone and full message (including the OTP code) to its stdout logger at INFO level and treat the dispatch as successful for the purposes of the OTP state machine — no external HTTP call is made.

Regardless of backend, on success OTP status SHALL transition `CREATED → SENT`, and on failure after 3 retries (backoff 2s/8s/32s) OTP status SHALL transition `CREATED → FAILED` (§7.8). The `log` transport has no transient failure modes and therefore does not trigger retries in practice.

On worker startup, if `SMS_BACKEND=smsru` and `SMSRU_API_KEY` is empty or equals the placeholder `your-smsru-api-key`, the worker SHALL fail fast with a configuration error (INV-015: secrets must be real env values, not placeholders). If `SMS_BACKEND=log`, `SMSRU_API_KEY` SHALL be ignored and MAY be empty.

**Previously:** the worker unconditionally called `https://sms.ru/sms/send` with whatever value was in `SMSRU_API_KEY`. An implicit fallback in `smsru.py` logged the message only when `SMSRU_API_KEY` was empty; any truthy placeholder (e.g. the `your-smsru-api-key` shipped in `.env.example`) bypassed the fallback and produced a real API call that returned `status_text: "Неправильный api_id"`, leaving OTPs stuck in `CREATED` and making customer login impossible in any default dev environment.

**Now:** the backend is selected explicitly via `SMS_BACKEND`; the default `.env.example` ships `SMS_BACKEND=log` with an empty `SMSRU_API_KEY` so a clean `docker compose up` produces working OTP login out of the box. Production overrides `SMS_BACKEND=smsru` and supplies a real `SMSRU_API_KEY` from the secret store (INV-015). Modifies §7.8 (SMS delivery) and §6.4 (OTP state machine transitions CREATED → SENT); does not alter the transition table itself.

#### Scenario: SMS sent successfully via smsru backend
- **WHEN** `SMS_BACKEND=smsru` and sms-worker receives `send_otp_sms` task and SMS.ru returns HTTP 200 with `status: OK`
- **THEN** worker updates OTP status in Redis to `SENT`

#### Scenario: SMS fails after all retries via smsru backend
- **WHEN** `SMS_BACKEND=smsru` and sms-worker exhausts 3 retry attempts (2s, 8s, 32s backoff)
- **THEN** worker updates OTP status in Redis to `FAILED` and logs the error (§7.8)

#### Scenario: SMS fails but retry succeeds via smsru backend
- **WHEN** `SMS_BACKEND=smsru` and the first SMS.ru call fails but a subsequent retry succeeds
- **THEN** worker updates OTP status to `SENT` on the successful attempt

#### Scenario: Dev dispatch via log backend
- **WHEN** `SMS_BACKEND=log` and sms-worker receives `send_otp_sms` task with a decrypted phone and a 6-digit code
- **THEN** worker writes an INFO-level log line containing the phone and the full message `"Код подтверждения: {code}. Aura Coffee"`
- **AND** worker updates OTP status in Redis to `SENT`
- **AND** worker does not perform any outbound HTTP request

#### Scenario: Startup validation with placeholder key
- **WHEN** sms-worker starts with `SMS_BACKEND=smsru` and `SMSRU_API_KEY` either empty or equal to `your-smsru-api-key`
- **THEN** worker SHALL fail startup with a configuration error naming `SMSRU_API_KEY` (INV-015)
- **AND** no Celery task SHALL be consumed

#### Scenario: Log backend ignores missing key
- **WHEN** sms-worker starts with `SMS_BACKEND=log` and `SMSRU_API_KEY` empty
- **THEN** worker starts successfully and consumes `send_otp_sms` tasks using the log transport

### Requirement: OTP state machine enforcement
The system SHALL enforce the OTP state machine (§6.4) exhaustively. Only transitions listed in §6.4 are permitted (INV-016). Forbidden transitions (VERIFIED → any, EXPIRED → any, FAILED → any, CREATED → VERIFIED, CREATED → EXPIRED) SHALL be rejected.

#### Scenario: Attempt forbidden transition
- **WHEN** any operation attempts a transition not in the §6.4 transition table
- **THEN** system rejects the operation and logs the violation

### Requirement: Phase 2 manual test guide documents the real OTP endpoints

The Phase 2 manual test scenario document (`docs/phase2_manual_test_scenarios.md`) SHALL reference the real OTP authentication endpoints `POST /api/v1/auth/send-code` and `POST /api/v1/auth/verify-code` as exposed by `services/core-api/src/core_api/routers/auth.py` (INV-016: state machines exhaustive — only real transitions are documented). The guide SHALL document the dev workflow consistent with the `SMS_BACKEND=log` default established by the archived `2026-04-10-fix-dev-otp-sms-backend` change: the OTP code is read from `docker compose logs sms-worker` (the `[SMS:log]` INFO line), not from direct Redis inspection.

This requirement exists because the previous Part B of the guide referenced `/api/v1/auth/request-otp` and `/api/v1/auth/verify-otp` (which return 404) and a `redis-cli --scan 'otp:*'` workaround that predates the `log` backend — making the Phase 2 manual matrix unrunnable without code-reading. No sms-otp runtime behavior changes; this is a doc-surface addition that pins the guide to the current auth-router contract and the already-existing dev transport scenario.

#### Scenario: Developer follows Part B and obtains a customer JWT on first try

- **WHEN** a developer runs `./scripts/up.sh`, then follows `docs/phase2_manual_test_scenarios.md` Part B step-by-step (curl `POST /api/v1/auth/send-code`, read the code from `docker compose logs sms-worker | grep '\[SMS:log\]'`, curl `POST /api/v1/auth/verify-code` with that code)
- **THEN** `/send-code` returns HTTP 200 with `{message: "OTP sent", phone_hash: ...}`
- **AND** sms-worker logs contain a single `[SMS:log] to=<phone> msg=Код подтверждения: <6 digits>. Aura Coffee` line within 1 second of the `/send-code` call
- **AND** `/verify-code` with that code returns HTTP 200 with `{access_token, refresh_token}`

#### Scenario: Guide warns about multi-worktree port collisions

- **WHEN** a developer runs multiple worktree stacks concurrently and host port `NGINX_PORT` is bound by a sibling compose project
- **THEN** the guide SHALL instruct them to either bump `NGINX_PORT` in the current worktree's `.env` (per `.env.example:22-28`) or run `docker compose logs sms-worker` with an explicit `-p <project>` flag matching the stack that owns the port — so that `curl :8240` and `docker compose logs` target the same stack
