## Why

Bringing the stack up with the shipped `.env.example` breaks customer OTP login end-to-end. `.env.example` sets `SMSRU_API_KEY=your-smsru-api-key` (a truthy placeholder), so `services/sms-worker/src/sms_worker/clients/smsru.py:14` skips its existing empty-key dev fallback and POSTs to `https://sms.ru/sms/send`, which responds `{"status":"ERROR","status_text":"Неправильный api_id"}`. The Celery task retries 3× then returns `None`, leaving the Redis OTP in status `CREATED` — but the verify Lua script in `services/core-api/src/core_api/services/otp.py:31` requires status `sent`, so every verification returns `invalid_status` and the customer can never log in. This blocks MVP Phase 1 (Auth) from being usable in any dev/smoke environment that does not have a real sms.ru account.

## What Changes

- Add an explicit `SMS_BACKEND` setting to `sms-worker` settings with values `log` (dev default) and `smsru` (production). The current implicit "empty key → log" branch is replaced by explicit backend selection.
- Introduce a small transport abstraction in `services/sms-worker/src/sms_worker/clients/`: a `LogTransport` that writes the phone + full message (including the OTP code) to worker stdout at INFO level, and the existing sms.ru call wrapped as `SmsRuTransport`. `send_otp_sms` task selects the transport based on `settings.sms_backend`.
- Update `.env.example` so that out-of-the-box `docker compose up` uses `SMS_BACKEND=log` and ships `SMSRU_API_KEY=` empty. Add a comment documenting how to switch to `smsru` for production.
- On `SMS_BACKEND=smsru` with an empty/placeholder `SMSRU_API_KEY`, `sms-worker` SHALL fail fast on startup (pydantic-settings validator) rather than silently degrading — this catches misconfigured production deploys.
- **BREAKING (config only):** the implicit "empty `SMSRU_API_KEY` falls back to log" behaviour in `smsru.py` is removed; operators must set `SMS_BACKEND` explicitly. No breaking change to API, DB, or Celery task signatures.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `sms-otp`: the "SMS delivery via sms-worker" requirement gains a backend-selection clause so that dev environments can transition OTP status `CREATED → SENT` via a log transport without calling SMS.ru. Production behaviour (status transitions, retries, failure handling) is unchanged.

## Impact

- **Code:** `services/sms-worker/src/sms_worker/settings.py`, `services/sms-worker/src/sms_worker/clients/smsru.py`, new `services/sms-worker/src/sms_worker/clients/log.py`, `services/sms-worker/src/sms_worker/tasks/otp.py` (select transport), `services/sms-worker/tests/` (add log-backend test + startup-validation test).
- **Config:** `.env.example` (`SMS_BACKEND`, blank `SMSRU_API_KEY`), `docker-compose*.yml` if it hard-codes the old var (verify during implementation).
- **Docs:** `services/sms-worker/AGENTS.md` should mention the backend switch.
- **No impact on:** core-api, database schema, Celery task signatures, rate-limiting, OTP Lua verify script, frontend, or any other worker. The OTP state machine contract is preserved.
- **Secrets (INV-015):** production still sources `SMSRU_API_KEY` from env only; dev no longer needs a real secret to run the login flow.

## Non-Goals

- Not adding a Redis/DB peek endpoint for tests to read OTP codes directly (proposal path #1 from the task). Log-backend is cleaner because it keeps the existing OTP state machine as the single source of truth and needs no new API surface.
- Not provisioning or documenting how to obtain a real sms.ru api_id (proposal path #3). Operators who want live SMS in dev can set `SMS_BACKEND=smsru` and supply their own key; this proposal does not take a position on procurement.
- Not refactoring the existing retry/backoff logic, Lua verify script, or rate-limit counters.
- Not touching order-status SMS notifications (Phase 3) — this change only covers the OTP flow in Phase 1. The transport abstraction is scoped to the OTP task; extending it to notifications is a follow-up.
- Not adding a "staging" backend that routes to a sandbox sms.ru endpoint.

## MVP Phase

Phase 1 — Auth (§7.1). This is a blocking dev-ergonomics fix for Phase 1: without it, Phase 1 cannot be smoke-tested or demoed from a clean checkout. Relates to `sms-otp` spec and INV-015 (secrets in env only).
