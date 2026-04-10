## 1. Pre-flight callout

- [x] 1.1 IMPL [core-api]: In `docs/phase2_manual_test_scenarios.md`, insert a short callout immediately after the existing Pre-flight `./scripts/up.sh` block (around line 5–8). State that the dev stack uses `SMS_BACKEND=log` so OTP codes appear in `docker compose logs sms-worker` as `[SMS:log] to=<phone> msg=Код подтверждения: NNNNNN. Aura Coffee` lines, and warn that if another worktree stack is running concurrently, host port `NGINX_PORT=8240` may belong to a sibling compose project — the fix is either to bump ports in the current worktree's `.env` per `.env.example:22-28` or to run `docker compose logs` with `-p <project>` matching the stack that owns the port. Keep the callout under ~8 lines. Touches 1 file.

## 2. Part B — endpoint paths

- [x] 2.1 IMPL [core-api]: In `docs/phase2_manual_test_scenarios.md` Part B, replace the curl command on line 37 (`POST /api/v1/auth/request-otp`) with `POST /api/v1/auth/send-code`. The request body `{"phone":"+79991234567"}` is unchanged. Expected response: HTTP 200, body `{"message":"OTP sent","phone_hash":"<64-hex>"}`. Source of truth: `services/core-api/src/core_api/routers/auth.py:25-30`. Touches 1 file.

- [x] 2.2 IMPL [core-api]: In `docs/phase2_manual_test_scenarios.md` Part B, replace the curl command on line 41 (`POST /api/v1/auth/verify-otp`) with `POST /api/v1/auth/verify-code`. Request body shape: `{"phone":"+79991234567","code":"<code>"}`. Expected response: HTTP 200, body is `TokenResponse` — pipe through `jq -r .access_token`. Source of truth: `services/core-api/src/core_api/routers/auth.py:79-88`. Touches 1 file.

## 3. Part B — OTP code retrieval

- [x] 3.1 IMPL [sms-worker]: In `docs/phase2_manual_test_scenarios.md` Part B, delete the three-line Redis workaround (around lines 28–32: `docker compose exec redis redis-cli --scan --pattern 'otp:*'` and the subsequent `GET`). Replace with a single line: `docker compose logs --tail 20 sms-worker | grep '\[SMS:log\]'` and a one-line instruction that the 6-digit OTP is in the `msg=Код подтверждения: NNNNNN` substring. Touches 1 file (same file as task 1.1, but a different region — treat as a separate sequential edit).

- [x] 3.2 IMPL [sms-worker]: Update the SPA-path instructions in Part B (numbered steps 1–4 around lines 26–34) to match: step 1 unchanged, step 2 unchanged, step 3 now reads "Pull the OTP from `docker compose logs sms-worker` (look for the `[SMS:log]` line)", step 4 unchanged. Keep numbered list structure intact. Touches 1 file.

## 4. Retire stale auto-memory

- [x] 4.1 IMPL [shared]: Delete the auto-memory file `~/.claude/projects/-home-p3tal-Projects-personal-job-learning-projects-aura-coffee/memory/project_sms_worker_otp_broken_in_dev.md`. Rationale per design.md Decision 4: the underlying bug was fixed by commit `42a29a7 fix dev otp sms backed` on 2026-04-10, and a rewritten "was broken, now fixed" note has no informational value for future sessions. This file lives outside the repo and is not tracked by git. Touches 1 file.

- [x] 4.2 IMPL [shared]: In `~/.claude/projects/-home-p3tal-Projects-personal-job-learning-projects-aura-coffee/memory/MEMORY.md`, remove the single index line pointing at `project_sms_worker_otp_broken_in_dev.md`. Leave all other lines intact. If this leaves MEMORY.md with zero entries, that is acceptable — the index is allowed to be empty. Touches 1 file.

## 5. Verify end-to-end

- [x] 5.1 VERIFY [core-api]: From the current worktree CWD, run the updated Part B verbatim (pre-flight → `send-code` curl → read code from worker logs → `verify-code` curl) and confirm: (a) `send-code` returns HTTP 200 with `message: "OTP sent"`, (b) within 1 second, `docker compose logs --since 10s sms-worker` contains exactly one `[SMS:log] to=+79991234567 msg=Код подтверждения: <6 digits>. Aura Coffee` line, (c) `verify-code` with that exact code returns HTTP 200 with a non-empty `access_token` and `refresh_token`. This satisfies the `#### Scenario: Developer follows Part B and obtains a customer JWT on first try` requirement added in `specs/sms-otp/spec.md`. If any step fails, stop and re-open the change — do not archive.

- [x] 5.2 VERIFY [sms-worker]: If multiple worktree stacks are running on the host, repeat task 5.1 after explicitly pinning the command with `docker compose -p aura_coffee logs sms-worker` (or whatever the current worktree's project name is, see `docker compose ps` header). Confirm the callout from task 1.1 is accurate — i.e. without `-p`, the logs come from the CWD's project; with `-p`, they come from the named project. This satisfies the `#### Scenario: Guide warns about multi-worktree port collisions` requirement.

- [x] 5.3 VERIFY [core-api]: Run `openspec validate --change fix-phase2-otp-test-guide` and confirm the change validates cleanly (proposal + design + specs + tasks all parse, no schema violations).
