## 1. Settings and validation

- [x] 1.1 [sms-worker] Add `sms_backend: Literal["log", "smsru"] = "log"` to `services/sms-worker/src/sms_worker/settings.py` `Settings` class (pydantic-settings picks it up from `SMS_BACKEND` env var).
- [x] 1.2 [sms-worker] Add a `model_validator(mode="after")` on `Settings` that raises `ValueError` when `sms_backend == "smsru"` and `smsru_api_key` is empty or equals the literal `"your-smsru-api-key"`. Error message MUST name `SMSRU_API_KEY` and reference INV-015.
- [x] 1.3 [sms-worker] Write unit test `tests/test_settings.py::test_smsru_backend_rejects_placeholder_key` that instantiates `Settings(sms_backend="smsru", smsru_api_key="your-smsru-api-key")` and asserts it raises.
- [x] 1.4 [sms-worker] Write unit test `test_log_backend_accepts_empty_key` that instantiates `Settings(sms_backend="log", smsru_api_key="")` and asserts it succeeds.
- [x] 1.5 [sms-worker] Write unit test `test_smsru_backend_requires_nonempty_key` covering the empty-string case separately.

## 2. Transport layer

- [x] 2.1 [sms-worker] Rename `send_sms` in `services/sms-worker/src/sms_worker/clients/smsru.py` to `send_via_smsru`. Keep the signature `(phone: str, message: str) -> bool` and the existing SMS.ru HTTP call, but remove the in-function empty-key dev-fallback branch (lines 14–16 in the current file) — backend selection now lives above the transport.
- [x] 2.2 [sms-worker] Create `services/sms-worker/src/sms_worker/clients/log.py` with `send_via_log(phone: str, message: str) -> bool` that emits one `logging.INFO` line with prefix `[SMS:log]` carrying `to=<phone> msg=<message>` and returns `True`. No HTTP, no Redis, no sleep.
- [x] 2.3 [sms-worker] In `services/sms-worker/src/sms_worker/tasks/otp.py`, import both transports and select once at module scope: `_TRANSPORT = send_via_log if settings.sms_backend == "log" else send_via_smsru`. Replace the `send_sms(phone, message)` call in `send_otp_sms` with `_TRANSPORT(phone, message)`.
- [x] 2.4 [sms-worker] Write unit test `tests/test_log_transport.py::test_send_via_log_logs_message_and_returns_true` asserting the log line contains the phone and the full `"Код подтверждения: {code}. Aura Coffee"` message and that the function returns `True`.
- [x] 2.5 [sms-worker] Write unit test `test_send_via_log_never_calls_httpx` patching `httpx.post` and asserting zero calls.

## 3. OTP task integration

- [x] 3.1 [sms-worker] Write integration test `tests/test_otp_task_log_backend.py::test_send_otp_sms_transitions_created_to_sent_via_log`: using fakeredis, pre-populate an OTP with status `CREATED`, invoke `send_otp_sms` with `sms_backend="log"`, assert Redis OTP status is `sent` after the call.
- [x] 3.2 [sms-worker] Write integration test `test_send_otp_sms_log_backend_does_not_retry`: assert the Celery task completes on first invocation without raising and without touching `httpx`.
- [x] 3.3 [sms-worker] Update any existing test in `services/sms-worker/tests/` that imports `send_sms` from `smsru` — rename imports to `send_via_smsru`. Run `grep -rn "send_sms\b" services/sms-worker/tests` to find them.
- [x] 3.4 [sms-worker] Run `pytest services/sms-worker/tests/` locally and confirm all tests pass.

## 4. Config and docs

- [x] 4.1 [infra] Update `.env.example`: set `SMS_BACKEND=log` (new line) and change `SMSRU_API_KEY=your-smsru-api-key` to `SMSRU_API_KEY=` (empty). Add a short comment above the block stating that production overrides `SMS_BACKEND=smsru` with a real key from the secret store.
- [x] 4.2 [infra] Check `docker-compose.yml` and any `docker-compose.*.yml` for hard-coded `SMSRU_API_KEY` or `SMS_BACKEND` values that would override `.env`; remove or update as needed. If no hard-codes exist, note that in the PR description.
- [x] 4.3 [sms-worker] Update `services/sms-worker/AGENTS.md` with a short section `## SMS_BACKEND` documenting: default `log` for dev, required `smsru` for production, the startup-validation guarantee, and the security note that `log` writes OTP codes to stdout.

## 5. End-to-end verification

- [x] 5.1 [infra] On a clean worktree, run `cp .env.example .env && docker compose up -d` and verify `sms-worker` starts without errors.
- [x] 5.2 [infra] Hit `POST /api/v1/auth/send-code` with a test phone via curl or the OpenAPI client, then `docker compose logs sms-worker` and confirm the `[SMS:log]` line appears with a 6-digit code.
- [x] 5.3 [infra] Submit the code via `POST /api/v1/auth/verify-code` and confirm the response is `verified` (i.e., the OTP state actually reached `sent` and the Lua script accepted it).
- [x] 5.4 [sms-worker] Manually verify the production path locally: set `SMS_BACKEND=smsru` and `SMSRU_API_KEY=your-smsru-api-key` and confirm `docker compose up sms-worker` exits with a pydantic validation error naming `SMSRU_API_KEY`.
