## Context

**Affected modules:** documentation only (`docs/phase2_manual_test_scenarios.md`). No code in `[core-api]`, `[sms-worker]`, `[web-customer]`, `[web-admin]`, `[shared]`, `[database]`, `[redis]` is touched. Included in the modules declaration per OpenSpec rule only for completeness: `[none]`.

Phase 2 (Menu & Cart) shipped a manual test matrix for smoke-checking the full admin + customer flow against a running stack. Its "Part B — Get customer JWT" depends on OTP login. Between Phase 2 test-guide authorship and today, two things changed without the guide being updated:

1. The OTP routes were renamed (or always were) `POST /api/v1/auth/send-code` and `POST /api/v1/auth/verify-code` (see `services/core-api/src/core_api/routers/auth.py:26,80`). The guide still references `request-otp` and `verify-otp` — 404 paths.
2. Commit `42a29a7 fix dev otp sms backed` (2026-04-10) added a `SMS_BACKEND=log` dev transport to `sms-worker`, making the OTP code observable in `docker compose logs sms-worker` (`[SMS:log] ...` lines) and obsoleting the pre-existing "read OTP from Redis" workaround the guide still documents.

During investigation on 2026-04-11, the root cause of "sms-worker logs don't show the code" was confirmed to be *not* a code bug: the `menu_cart` worktree shared host port `:8240` with a sibling worktree (`aura_coffee-fix-dev-stack-auto-apply-migrations`), so curl hit the sibling's nginx while `docker compose logs` (run from `menu_cart` CWD) showed `menu_cart`'s idle worker. A live curl against the real endpoint produced `[SMS:log] to=+79991234567 msg=Код подтверждения: 613362. Aura Coffee` in the sibling's worker logs within the same second, confirming the log backend works as designed.

Stakeholders: any developer (human or agent) running Phase 2 manual tests. Also: the auto-memory note `project_sms_worker_otp_broken_in_dev.md`, which was written BEFORE `42a29a7` landed on the same day and now incorrectly claims the dev OTP flow is broken.

## Goals / Non-Goals

**Goals:**
- Part B of `docs/phase2_manual_test_scenarios.md` SHALL produce a working customer JWT on the first try for any developer following it against a clean dev stack.
- The guide SHALL document the `SMS_BACKEND=log` dev workflow (read the code from worker logs, not from Redis).
- The guide SHALL warn about the multi-worktree `:8240` port-collision foot-gun that caused this investigation, and point to `.env.example:22-28` for the port-offset convention.
- The stale `project_sms_worker_otp_broken_in_dev.md` memory note SHALL be retired (deleted or rewritten) so future sessions do not anchor on a fixed bug.

**Non-Goals:**
- No code changes to `sms-worker`, `core-api`, `docker-compose.yml`, or `.env.example`. Runtime verified healthy on 2026-04-11.
- No hard enforcement against multi-worktree port collisions. `.env.example:22-28` already documents the convention; programmatic enforcement (e.g. per-worktree port auto-offset in `scripts/up.sh`) is a separate concern.
- No new automated test. `services/sms-worker/tests/test_otp_task_log_backend.py` already covers the log-transport path. The new spec scenarios are documentation-grounding statements, not gates — the doc itself is the testable artifact.
- No changes to Blocks 1–4 of the guide (admin menu CRUD, customer menu, cart, cross-cutting). Only Part B.

## Decisions

### Decision 1: Fix the guide in place; no new doc file

**Chosen:** Edit `docs/phase2_manual_test_scenarios.md` Part B with targeted replacements and a short pre-flight note. Leave the file's structure, heading hierarchy, and Blocks 1–4 untouched.

**Rationale:** The problem is localized to ~15 lines. Rewriting the whole guide or splitting Part B into a separate doc would churn diff for zero benefit to readers. Targeted edits MUST preserve the existing `---`-separated section structure so the rest of the Phase 2 matrix continues to work unchanged.

**Alternative considered and rejected:** create a new `docs/phase2_dev_login.md` and have Part B link to it. Rejected — indirection without purpose; the guide is already a single file that new devs read top-to-bottom.

### Decision 2: Replace Redis workaround with `docker compose logs sms-worker`, not keep both

**Chosen:** The new Part B MUST instruct developers to read the OTP code from `docker compose logs sms-worker --tail 20 | grep '\[SMS:log\]'`. The `redis-cli --scan 'otp:*'` path MUST be removed entirely (not kept as a fallback).

**Rationale:** The log transport is the default (`SMS_BACKEND=log` in `.env.example`), it's faster to type, it doesn't depend on hashed phone keys, and the OTP lives in Redis only briefly before the worker flips its status to `SENT` and the Lua verify script DELs it on success. Documenting both paths invites confusion about which to use when.

**Alternative considered and rejected:** keep the Redis command as a "troubleshooting" fallback under a "If the log line doesn't appear" subsection. Rejected on the first pass because the primary cause of "log line doesn't appear" turned out to be multi-worktree port collision, not a Redis/worker issue — and the correct fix for that is the warning in Decision 3, not a fallback curl.

### Decision 3: Add a pre-flight callout about multi-worktree port collisions

**Chosen:** Insert a short callout immediately under the existing Pre-flight section (before Part A) that (a) states the dev stack uses `SMS_BACKEND=log` so OTP codes appear in worker logs and (b) warns that if the developer runs multiple worktree stacks concurrently, `:8240` may be bound by a sibling compose project — and the fix is either to bump `NGINX_PORT` in the worktree's `.env` per `.env.example:22-28` or to pin `docker compose logs` with `-p <project>`.

**Rationale:** This was the actual root cause of the 2026-04-11 investigation. Without the warning, the next developer (or agent) will hit the exact same dead-end and waste the same hour debugging "broken" OTP delivery. Putting it at pre-flight means it's seen before the curl commands run, not discovered after the fact.

**Alternative considered and rejected:** add the warning only to Part B instead of pre-flight. Rejected — the footgun also applies to Part A (admin login via `/staff/auth/login` through the same `:8240` nginx) and Blocks 1–4 (all the admin/customer SPA URLs). Pre-flight is the single right place to scope it.

### Decision 4: Retire the stale auto-memory note rather than rewrite it

**Chosen:** Delete `project_sms_worker_otp_broken_in_dev.md` from the auto-memory directory and remove its pointer from `MEMORY.md`. Do not leave a rewritten note saying "this was fixed" — that's a non-fact, not a fact.

**Rationale:** The memory note's entire purpose (warning about an unusable dev OTP flow) is obsolete. A rewritten "FYI, this used to be broken" note would just take up budget in future contexts and force the next session to re-verify the historical claim. If a new session needs context on the log backend, it can read the archived `2026-04-10-fix-dev-otp-sms-backend` change or grep `services/sms-worker/src/sms_worker/settings.py`. Git history is authoritative.

**Alternative considered and rejected:** rewrite the note to describe the multi-worktree foot-gun instead of the old OTP bug. Rejected — that's a different concern; if we want to capture it, write a fresh note (`project_multi_worktree_port_collision.md` or similar) rather than overloading the old one. Not in scope here.

## Risks / Trade-offs

- **[Risk] Guide drifts again if auth routes are renamed.** → **Mitigation**: the `sms-otp` spec delta added in this change now pins `POST /api/v1/auth/send-code` and `/verify-code` as the documented developer-facing contract in an ADDED requirement with a concrete scenario. Future renames will produce a spec drift that shows up in `openspec validate`, not a silent doc rot.

- **[Risk] A developer still runs `docker compose logs` in the wrong worktree and sees no output despite the warning.** → **Mitigation**: the callout explicitly names `-p <project>` and links to `.env.example:22-28`. Not bulletproof, but the same failure mode now has a documented recovery path two lines above the curl commands. Hard enforcement is explicitly a Non-Goal.

- **[Trade-off] Removing the Redis workaround means if the worker is actually down, developers lose a fallback.** → **Acceptable**: if `sms-worker` is down, `docker compose ps sms-worker` catches it immediately and is a more honest signal than a weird Redis scan that may or may not return a key depending on whether the Lua verify script has already DELed it. The existing `./scripts/up.sh` pre-flight banner also already checks worker health.

- **[Risk] The auto-memory deletion is irreversible in the current session.** → **Mitigation**: the memory is file-based at `~/.claude/projects/.../memory/`; if deletion is regretted, `git log` on that directory (if versioned) or simply re-adding a fresh note works. Not a production-data risk — memory is per-user, per-project.

## Migration Plan

Not applicable — no data model, no schema, no runtime behavior change. A single doc file and a single auto-memory file are edited. Rollback is `git revert` on the commit that changes `docs/phase2_manual_test_scenarios.md` (plus manual restore of the memory file if needed).
