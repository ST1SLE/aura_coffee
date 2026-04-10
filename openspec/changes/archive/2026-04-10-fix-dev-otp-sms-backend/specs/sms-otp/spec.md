## MODIFIED Requirements

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
