## Why

`docs/phase2_manual_test_scenarios.md` — Part B (customer JWT) — tells developers to hit `POST /api/v1/auth/request-otp` and `/verify-otp`, which return 404 (real paths are `/send-code` and `/verify-code`, see `services/core-api/src/core_api/routers/auth.py:26,80`). It also tells them to read the OTP out of Redis with `redis-cli --scan 'otp:*'`, a workaround that dates from before commit `42a29a7 fix dev otp sms backed` (2026-04-10) added the `SMS_BACKEND=log` dev transport. Since that fix, the correct way to get the code in dev is `docker compose logs sms-worker`, which prints `[SMS:log] to=… msg=Код подтверждения: NNNNNN. Aura Coffee`. The old instructions make Phase 2 manual tests unrunnable and send new developers down a false trail (as observed in session 2026-04-11 on the `menu_cart` worktree).

## What Changes

- Rewrite Part B of `docs/phase2_manual_test_scenarios.md`:
  - Replace `/api/v1/auth/request-otp` → `/api/v1/auth/send-code` (line 37)
  - Replace `/api/v1/auth/verify-otp` → `/api/v1/auth/verify-code` (line 41)
  - Drop the `redis-cli --scan 'otp:*'` workaround (lines 28–32) and replace with `docker compose logs sms-worker | grep '\[SMS:log\]'`
  - Add a one-line pre-flight note that the dev stack uses `SMS_BACKEND=log` (the OTP code is written to worker logs, not sent over SMS) and a warning that if multiple worktrees run stacks in parallel, `docker compose logs` must be run from the correct worktree CWD (or with `-p <project>`) — the `:8240` port may belong to a sibling stack.
- Retire the stale `project_sms_worker_otp_broken_in_dev.md` auto-memory note (it describes a bug fixed by commit `42a29a7`).

No code changes in `services/sms-worker/`, `services/core-api/`, or anywhere else. This is a documentation-and-memory fix validated against a live stack: `curl /api/v1/auth/send-code` already produces `[SMS:log]` lines in the worker today.

**MVP phase**: Phase 2 — Menu & Cart (the guide this fixes is the manual-test matrix for that phase). No functional impact on Phases 1–6; the underlying sms-otp capability (INV-012 rate limits, INV-015 placeholder-key guardrail) is unchanged.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
None. No spec-level REQUIREMENTS change — this is a dev-facing doc correction and memory hygiene. Existing `sms-otp` spec already documents the `SMS_BACKEND=log` dev transport (see `openspec/specs/sms-otp/spec.md` after the `2026-04-10-fix-dev-otp-sms-backend` change was archived).

## Non-Goals

- **No code changes to `sms-worker` or `core-api`.** The log transport, validator, and Celery wiring already work. Verified live: `curl -X POST /api/v1/auth/send-code` → `[SMS:log]` appears in `docker compose logs sms-worker` within the same second.
- **No fix for the multi-worktree port-collision ergonomics.** When two worktrees both default to `NGINX_PORT=8240`, curl hits whichever `nginx` container bound the port first, while `docker compose logs` targets the CWD's project — producing the exact confusion that triggered this investigation. That's a real dev-ergonomics bug, but it's a separate concern from the Phase 2 guide and is already partially documented in `.env.example:22-28` ("Bump these in your worktree's `.env` by the same offset"). Out of scope here; file a follow-up if we want a hard enforcement.
- **No changes to `.env` or `.env.example`.** The current defaults are correct; the user's local `.env` has a leftover `SMSRU_API_KEY=your-smsru-api-key` line that is harmless (the validator only rejects it when `SMS_BACKEND=smsru`, and the default is `log`).
- **No new automated test.** `services/sms-worker/tests/test_otp_task_log_backend.py` already covers the log-transport happy path. Adding another test would duplicate coverage for zero gain.

## Impact

- **Affected files**: `docs/phase2_manual_test_scenarios.md` (Part B only; Blocks 1–4 untouched).
- **Affected memory**: `~/.claude/projects/.../memory/project_sms_worker_otp_broken_in_dev.md` (retire/update) and its pointer in `MEMORY.md`.
- **APIs**: none changed. The proposal only updates references to already-correct paths.
- **Dependencies**: none added/removed.
- **Downstream**: future Phase 2 manual test runs (and any AI agent following the guide) will be able to obtain a customer JWT on the first try instead of hitting 404s and chasing a nonexistent Redis key.
