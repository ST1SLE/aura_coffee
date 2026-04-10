## ADDED Requirements

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
