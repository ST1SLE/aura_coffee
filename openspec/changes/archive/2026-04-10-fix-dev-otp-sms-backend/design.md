## Affected Modules

[sms-worker] — primary. Transport abstraction, settings, startup validation, tests.
[infra] — `.env.example` defaults; `docker-compose*.yml` verification (no config change expected).

Not affected: [core-api], [payment-worker], [web-customer], [web-admin], [shared], [database], [redis] schema.

## Context

`services/sms-worker/src/sms_worker/clients/smsru.py` has two branches: if `settings.smsru_api_key` is empty, it logs the message and returns `True` (dev fallback); otherwise it POSTs to SMS.ru. The `.env.example` shipped with the repo sets `SMSRU_API_KEY=your-smsru-api-key` — a truthy placeholder — so the dev fallback is skipped and the real API call is made. SMS.ru rejects the placeholder with `{status:"ERROR", status_text:"Неправильный api_id"}`, `send_sms` returns `False`, the Celery task retries 3×, then `_update_otp_status` sets the Redis OTP to `failed` (deleting the key).

On the core-api side, `services/core-api/src/core_api/services/otp.py` creates OTPs with status `CREATED` and the verify Lua script at lines 31–33 rejects anything where `otp.status ~= "sent"`. So even before the worker gives up, any verify attempt returns `invalid_status`. End result: customer login is impossible in any default dev environment. This blocks all downstream Phase 1 testing.

The existing `sms-otp` spec (§7.8, §6.4) already mandates the `CREATED → SENT` transition upon successful dispatch. Nothing in the spec forbids non-HTTP transports; the current code just hard-codes SMS.ru as the only sender.

Stakeholders: the Phase 1 auth flow owner (primary), anyone running smoke tests or demos from a clean checkout, and ops (production deploys, where a wrong backend would be catastrophic).

## Goals / Non-Goals

**Goals:**
- MUST make `docker compose up` from a clean checkout produce a working customer OTP login flow without requiring a real SMS.ru account.
- MUST preserve the OTP state machine contract: successful dispatch transitions `CREATED → SENT` (INV-016, §6.4) regardless of transport.
- MUST fail fast on production misconfiguration (placeholder api_id with `SMS_BACKEND=smsru`). INV-015 forbids silent degradation on missing/placeholder secrets.
- SHALL keep the transport abstraction minimal — two concrete transports (`log`, `smsru`) and a single selection function. No plugin registry, no DI container.
- SHOULD keep the change reviewable: one settings field, one new file, localized edits to `smsru.py` and `tasks/otp.py`.

**Non-Goals:**
- NOT building a Redis/DB peek endpoint for tests (proposal option #1). The log backend gives the same smoke-test ergonomics without a new API surface.
- NOT provisioning real sms.ru credentials (proposal option #3).
- NOT refactoring retry/backoff, the Lua verify script, or rate-limiting.
- NOT extending the abstraction to order-status notifications (Phase 3). Scope-limited to `send_otp_sms`.
- NOT adding a sandbox sms.ru endpoint, a file-backed transport, or an in-process mock.

## Decisions

### D1. Backend selected by a single enum env var, not by sentinel values

**Decision:** Introduce `SMS_BACKEND: Literal["log", "smsru"] = "log"` on `sms_worker.settings.Settings`. The default value is `"log"` so a blank `.env` produces a working dev flow.

**Rationale:** The current "empty key means dev" convention is invisible and brittle — a one-character typo in `.env` silently changes behaviour. An explicit enum surfaces the choice in config, fails pydantic validation on typos, and reads clearly in logs. The default MUST be `log` so the failure mode for forgetting to configure is "dev-only local flow" rather than "broken login".

**Alternatives considered:**
- *Keep the empty-key sentinel and just blank `.env.example`.* Cheapest diff, but preserves the invisible convention and lets a future `.env.example` regression resurrect the bug. Rejected.
- *Auto-detect by checking `SMSRU_API_KEY` against the literal placeholder.* Fragile — relies on string matching, doesn't help if the placeholder changes.
- *`SMS_BACKEND` as a free string imported via entry points.* Over-engineered for two transports.

### D2. Transport is a callable, not a class hierarchy

**Decision:** Define transports as module-level functions `send_via_smsru(phone, message) -> bool` and `send_via_log(phone, message) -> bool`. In `tasks/otp.py`, select once at module import:

```python
_TRANSPORT = send_via_log if settings.sms_backend == "log" else send_via_smsru
```

The existing `send_sms(...)` function in `smsru.py` is renamed `send_via_smsru` (removing its internal empty-key branch, since selection now lives above it). A new `clients/log.py` holds `send_via_log`.

**Rationale:** There are exactly two transports and no shared state. A `Transport` ABC plus two subclasses would be pure ceremony. Module-level selection at import time also means the worker crashes immediately on an invalid `SMS_BACKEND` value (pydantic catches the `Literal` mismatch at `Settings()` construction) rather than lazily on the first task.

**Alternatives considered:**
- *Protocol + DI via Celery's `worker_init` signal.* Heavier, no benefit here.
- *Keep a single `send_sms` function with an `if settings.sms_backend == "log":` branch at the top.* Smaller diff but mixes concerns in one file and makes it awkward to add a third transport later (if we ever do). Marginal; acceptable if reviewers prefer it.

### D3. Log transport writes at INFO with a distinctive prefix

**Decision:** `send_via_log` SHALL emit one log line per dispatch: `"[SMS:log] to=%s msg=%s"` at `logging.INFO`, carrying the full message including the 6-digit code. It SHALL return `True` unconditionally. It SHALL NOT sleep, retry, or touch Redis (the calling task handles status updates).

**Rationale:** The whole point is that a developer grepping `docker logs sms-worker` can read the code. INFO is the right level — warnings would be noisy in CI, debug would be hidden by default. A distinctive prefix makes it easy to filter. Returning `True` unconditionally lets the rest of the task code stay identical across backends; this is the simplest way to guarantee state-machine parity (D5).

**Trade-off:** This WILL leak OTP codes to worker stdout. That is the intended behaviour in dev and is acceptable because (a) log backend MUST NOT be enabled in production (enforced by D4 + ops convention of setting `SMS_BACKEND=smsru` explicitly), and (b) §6.4 bounds OTP TTL to 300s so leaked codes expire fast. Production logs never contain codes because production uses `smsru`.

### D4. Startup validation uses a pydantic field validator

**Decision:** Add a `model_validator(mode="after")` on `Settings`: when `sms_backend == "smsru"`, `smsru_api_key` MUST be non-empty AND MUST NOT equal the literal placeholder `"your-smsru-api-key"`. Violation SHALL raise `ValueError`, which pydantic surfaces as a validation error on `Settings()` construction, crashing worker startup before Celery binds to the queue.

**Rationale:** Fail fast on misconfigured production beats debugging "OTPs aren't arriving" in a live incident. Matching the literal placeholder string catches the single most likely regression (someone copies `.env.example` to `.env` and forgets to fill it in with `SMS_BACKEND=smsru` set). INV-015 demands secrets be real env values; a placeholder is definitionally not a real secret.

**Alternatives considered:**
- *Check at first task invocation.* The worker would come up healthy, consume one task, burn retries, and only then crash. Worse operator UX.
- *Only check for empty string.* Misses the placeholder case, which is the actual observed bug.

### D5. OTP state machine transitions stay identical

**Decision:** `tasks/otp.py` SHALL continue to call `_update_otp_status(r, phone_hash, "sent")` on transport success and `_update_otp_status(r, phone_hash, "failed")` after exhausting retries. The log transport participates in this flow identically to the sms.ru transport.

**State machine (§6.4) transitions touched:**
- `CREATED → SENT` — still fires on successful dispatch (now via either transport).
- `CREATED → FAILED` — still fires on retry exhaustion (only reachable via the `smsru` transport in practice; `log` never returns `False`).

No new transitions are introduced. INV-016 is preserved: the set of allowed transitions is unchanged.

### D6. `.env.example` defaults to the dev backend

**Decision:**

```
SMS_BACKEND=log
SMSRU_API_KEY=
```

Plus a comment block documenting that production overrides to `SMS_BACKEND=smsru` with a real key from the secret store.

**Rationale:** The point of this whole change is the out-of-the-box UX. Any other default value defeats the purpose. This follows the pattern already used elsewhere in the repo for dev-safe defaults.

## Risks / Trade-offs

- **Risk: A developer runs `SMS_BACKEND=log` in a staging environment where real customers hit the login flow.** → Mitigation: startup validation (D4) only guards the `smsru` path, so `log` starts cleanly everywhere. Counter-mitigation: ops documentation in `services/sms-worker/AGENTS.md` MUST state that any non-dev environment sets `SMS_BACKEND=smsru` explicitly. Deployment configs for staging/prod SHOULD pin `SMS_BACKEND=smsru`. This is a procedural guardrail, not a technical one; acceptable given Aura Coffee has a single production environment and a small operator pool.
- **Risk: OTP codes written to stdout in dev get captured by a log aggregator someone forgot was connected.** → Mitigation: distinctive `[SMS:log]` prefix makes these trivially greppable and redactable at the collector. Since the log backend is dev-only, exposure is bounded.
- **Risk: Someone adds a new transport and forgets to update the `model_validator` in D4.** → Mitigation: the validator explicitly matches on `"smsru"` by name, so a new transport simply won't be validated — which is the safe default (new transports don't gain free validation of a key they don't use). Adding validation for new transports is one isolated edit.
- **Trade-off: Module-level transport selection (D2) means you cannot switch `SMS_BACKEND` per-task at runtime.** → Accepted. No use case in scope requires per-task routing; a worker process is cheap to restart.
- **Risk: Tests that currently rely on `send_sms` being importable from `sms_worker.clients.smsru` break.** → Mitigation: grep existing tests during implementation (task list) and update imports. The existing `services/sms-worker/tests/` directory is small.

## Migration Plan

Forward-only; no database schema impact; no data backfill.

1. Merge the code + `.env.example` change together in one PR.
2. After merge: developers on clean checkouts get working OTP login automatically. Developers on existing checkouts whose `.env` still contains `SMSRU_API_KEY=your-smsru-api-key` and no `SMS_BACKEND` line will have their worker crash on next restart (D4 validation triggers because the default resolves to `smsru` only if we set it that way — but the default in `Settings` is `log`, so they will actually *start working* instead). Net effect: existing broken setups heal themselves on next `docker compose restart sms-worker`.
3. Production deploy configs MUST set `SMS_BACKEND=smsru` explicitly before this change is rolled to prod. Ops checklist item.

**Rollback:** revert the commit. No persistent state is touched; Redis OTP keys are 300s-TTL ephemeral. Worker restart clears any in-flight retries.

## Open Questions

- None blocking. One minor judgment call deferred to implementation: whether `send_via_log` should also write to the `logging.getLogger("sms_worker.dev")` child logger (for easier filtering) or just the module logger. Default to the module logger unless there's a reason to split.
