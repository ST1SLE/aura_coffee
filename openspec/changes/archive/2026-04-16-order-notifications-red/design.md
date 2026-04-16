## Context

Aura Coffee's order lifecycle (PDD §6.1) requires a notification subsystem that informs customers about every state transition through two channels:

- **in-app** — always, via a row in the `notifications` table that the customer SPA reads.
- **SMS** — only for "key" statuses (explicit matrix in §6.1), delivered by `sms-worker` through SMS.ru (§8.2).

The `notifications` table already exists (shipped by change `2026-04-16-phase3-schema-green`). It has columns `id, user_id, order_id, channel (in_app|sms), type (order_status_change|otp), message_ru, message_en, status (pending|sent|failed), sent_at, created_at`. No Phase 3 business logic writes to it yet.

The `sms-worker` already handles OTP SMS via `services/sms-worker/src/sms_worker/tasks/otp.py`:

- `_decrypt_phone(encrypted_hex)` — AES-256-GCM decryption of phone stored encrypted in `user_profiles` (INV-013).
- `_TRANSPORT` — module-level binding to `send_via_log` (dev) or `send_via_smsru` (prod), selected by `settings.sms_backend`.
- Retry contract: 3 attempts with backoff 2s/8s/32s (Celery `max_retries=3, default_retry_delay=2, retry_backoff=True, retry_backoff_max=32`).

Per the project's Two-Change Model (AGENTS.md → "Development Methodology: TDD"), order-notifications ships in two sequential OpenSpec changes on branch `feat/order-notifications`:

1. `order-notifications-red` (this change) — only failing tests land.
2. `order-notifications-green` — the same tests turn green.

Stakeholders: the RED suite is the executable contract. The GREEN-cycle agent reads it to know what to build; human reviewers read it to verify PDD conformance before any code lands.

Affected modules: **[core-api]** (tests target future `services/core-api/src/core_api/services/notification.py`), **[sms-worker]** (tests target future `services/sms-worker/src/sms_worker/tasks/notification.py`). **[shared]** and **[database]** are NOT touched — the `notifications` SQLAlchemy model and enums already exist.

## Goals / Non-Goals

**Goals:**

- RED suite MUST pin the complete status→(channels, RU text, EN text) matrix from PDD §6.1, including the two `CANCELLED` variants driven by `cancelled_by` and the two variants of `READY`/`COMPLETED` driven by `order.type`.
- RED suite MUST assert that every SMS text in the format `{status_text}. Заказ №{short_id}. Aura Coffee` is ≤ 70 Cyrillic chars (§8.2).
- RED suite MUST assert `short_id == order_id.hex[:8]` (stringified UUID, no dashes — first 8 hex chars).
- RED suite MUST assert that IN_APP `Notification` rows are always written with `status = SENT`, bilingual text populated, `type = order_status_change`.
- RED suite MUST assert that SMS `Notification` rows are written with `status = PENDING` and that the Celery task `sms_worker.send_order_notification_sms` is enqueued with `(notification_id, encrypted_phone_hex, message)`; for in-app-only statuses, no SMS row is written and no task is enqueued.
- RED suite MUST pin the worker contract: success path updates `Notification.status = SENT` and `sent_at = utc_now`; exhausted retries update `Notification.status = FAILED`; failure MUST NOT raise to the caller of the service — the task isolates failure.
- All RED tests MUST be importable by pytest (failures only inside function bodies, not at collection).

**Non-Goals:**

- No production implementation (GREEN cycle).
- No Order/Payment lifecycle trigger wiring — callers of `send_order_notification` (e.g., webhook handlers, barista actions) are the responsibility of order-lifecycle changes.
- No IN_APP read path (HTTP endpoint / polling / WebSocket).
- No notification-list/pagination API.
- No migration — the `notifications` table already exists (phase3-schema-green).
- No changes to rate-limiting — order-status notifications are not rate-limited (§7.8).
- No refactor of `tasks/otp.py` — whether the GREEN cycle extracts `_decrypt_phone`/`_TRANSPORT` into a shared helper is an implementation decision; the RED suite pins OUTCOMES, not sharing structure.

## Decisions

### D1 — Test file layout mirrors existing phase patterns

**Decision:** Three test files, each owned by the module it exercises:

- `services/core-api/tests/test_notification_service.py` — DB-level effects of `send_order_notification`: Notification rows written, Celery task enqueued (mocked), arguments captured.
- `services/core-api/tests/test_notification_messages.py` — pure-function matrix: for every `(status, order_type, cancelled_by)` triple from PDD §6.1, the computed RU text, EN text, SMS-required flag, and SMS body string are frozen.
- `services/sms-worker/tests/test_notification_task.py` — worker-level behavior of `send_order_notification_sms`: transport called with decrypted phone, DB side-effects on success/failure, retry raises on intermediate failures.

**Why X over Y:** Matches `test_models_order.py` / `test_schemas_order.py` / `test_migration_0005_phase3_schema.py` split from `phase3-schema-red`. Alternative — a single monster file — rejected for review-diff readability, failure localization, and fixture-scope separation (worker tests need a `CELERY_ALWAYS_EAGER`-style sync execution path; service tests need a DB session + mocked `delay()`).

### D2 — Import the target modules INSIDE test function bodies

**Decision:** RED tests MUST NOT import `core_api.services.notification` or `sms_worker.tasks.notification` at module top level. Each test function imports what it needs in its body.

**Why X over Y:** Keeps the test module importable by pytest's collector even though the production modules don't exist yet. Matches the pattern already used in `phase3-schema-red` (see `test_models_order.py` design note D2). Alternative — skipping the whole module with `pytest.importorskip` — rejected because RED tests MUST fail (ImportError is the failure), not skip.

### D3 — Celery dispatch is mocked at the service-test boundary

**Decision:** `test_notification_service.py` tests MUST patch `send_order_notification_sms.delay` (or an equivalent dispatcher the implementation settles on) via `unittest.mock.patch` and assert (1) call count, (2) positional/keyword args. Service tests MUST NOT start a worker process, configure a broker, or rely on Celery EAGER mode.

**Why X over Y:** Fast, deterministic, unit-scope. EAGER mode is used where relevant in `test_notification_task.py` to exercise the worker's own logic — not in service tests. Alternative — full Celery broker + inspect queue — rejected as too heavy for a unit test.

### D4 — Worker tests execute the task function directly, not through Celery

**Decision:** `test_notification_task.py` invokes `send_order_notification_sms.run(...)` (or calls the underlying function directly) with a `self`-like stub that carries `self.request.retries` and `self.max_retries`. Retry behavior is asserted by (a) forcing the transport to return `False` and (b) asserting that the task raises on intermediate attempts and marks `FAILED` on the final attempt.

**Why X over Y:** Matches the pattern already established in `services/sms-worker/tests/test_otp_task.py`. Alternative — spin up a Celery EAGER app — rejected because a Celery fixture already exists in the sms-worker tests (`test_log_transport.py`, `test_otp_task.py`), and direct invocation is simpler for the retry-branch assertion.

### D5 — Freeze RU + EN texts in the tests (do not derive them)

**Decision:** Each text variant MUST appear as a literal string in `test_notification_messages.py`. The GREEN-cycle implementation derives them from a matrix of its choice, but the RED suite pins the exact user-facing wording.

**Why X over Y:** User-facing text is a product decision — PDD §6.1 specifies the wording. Putting it in the test prevents accidental rewording during GREEN. Alternative — derive in the test — defeats the purpose of a contract test.

### D6 — SMS length assertion runs on all SMS-emitting branches

**Decision:** A parametrized test iterates every `(status, order_type, cancelled_by)` triple whose `requires_sms == True`, builds the SMS body with a real 32-char hex UUID (max `short_id` length = 8), and asserts `len(sms_body) <= 70`. This proves §8.2 compliance across the matrix, not just a single happy path.

**Why X over Y:** §8.2 "Не более 70 символов" is a hard constraint; a single SMS segment for Cyrillic is 70 chars. Alternative — test one representative string — rejected because each status has a different length and regression risk is per-status.

### D7 — IN_APP writes `status = SENT` at creation time

**Decision:** The contract for IN_APP is synchronous: the row is the delivery. There is no separate "deliver" step — the customer SPA reads the row. Therefore the RED test asserts `status == SENT` for every IN_APP row produced by `send_order_notification`.

**Why X over Y:** PDD §6.1 and §8.2 differentiate SMS (async, retry-capable) from in-app (row = delivery). The `status` enum values `pending / sent / failed` map naturally: SMS starts `pending`, IN_APP starts `sent`. Alternative — start IN_APP as `pending` and flip later — rejected because there is no later step to flip it.

### D8 — Phone is loaded inside the service and passed as `encrypted_phone_hex`

**Decision:** The service reads `UserProfile.phone_encrypted` (hex string) and passes it through to the Celery task. The task decrypts internally. Raw decrypted phone MUST NOT cross the Celery boundary.

**Why X over Y:** INV-013 (PII isolation) — plaintext phone does not belong on a queue. Matches the pattern already in `tasks/otp.py` where the OTP call site passes `encrypted_phone_hex`. Alternative — decrypt in core-api and pass plaintext — rejected as an INV-013 violation.

### D9 — `cancelled_by` is an optional parameter, not inferred

**Decision:** `send_order_notification` takes `cancelled_by: Literal["customer", "admin"] | None = None`. The caller of the service knows who triggered the cancellation (self-serve endpoint vs admin endpoint); the service does not try to derive it from the DB.

**Why X over Y:** Explicit > implicit. §6.1's two `CANCELLED` rows are distinguished by actor, not by any column on `orders` at the moment of transition. Alternative — parse from `orders.cancelled_by` column — adds a DB round-trip and order of operations dependencies with the caller.

### D10 — `type = order_status_change` is hard-coded in the service

**Decision:** The service writes `type = NotificationType.ORDER_STATUS_CHANGE` on every row. The enum has `order_status_change` and `otp`; only OTP flow sets the other value.

**Why X over Y:** Follows from the `notifications` table schema. No branching required. Alternative — pass `type` as a parameter — creates misuse risk.

## State machine impact

This RED cycle pins tests for a service that implements the **Notification-emission side effect** of the state transitions in PDD §6.1 (Order Lifecycle). It does NOT mutate order state. Affected transitions (all emit notifications):

- `CREATED → PAID`
- `PAID → PREPARING`
- `PAID → CANCELLED` (×2: customer vs admin)
- `PREPARING → READY`
- `PREPARING → CANCELLED` (admin only)
- `READY → CANCELLED` (admin only)
- `READY → IN_DELIVERY`
- `READY → COMPLETED` (pickup)
- `IN_DELIVERY → COMPLETED`

Per INV-016, the service MUST NOT produce notifications for transitions not in §6.1. Tests cover the "forbidden transition" case by asserting that `send_order_notification` raises `ValueError` (or an equivalent) when called with a status not in the matrix.

## 152-FZ Compliance (INV-013)

- The service MUST load phone only as the `phone_encrypted` hex string from `user_profiles` and pass the hex through to the worker unchanged.
- The worker MUST decrypt phone inside its own process (reusing the established `_decrypt_phone` path) and MUST NOT log the decrypted value.
- RED tests MUST assert (a) that the service passes an encrypted hex, not plaintext, and (b) that `_TRANSPORT` is called with the decrypted phone but no log statement emits it (log lines include only a prefix of `notification_id`).

## Atomicity Analysis

INV-004 does not apply — notifications are not financial state. They are side effects whose failure MUST NOT propagate:

- Failing to enqueue a Celery task MUST NOT roll back the order-status transition in the caller. The GREEN cycle achieves this by (a) committing the Notification row in a short transaction, (b) catching broker errors around `.delay()` and logging them, and (c) letting the caller commit its own transaction independently.
- RED tests DO assert one thing: that the SMS Notification row is committed to the DB before the Celery task is enqueued (so the worker can find the row by id on the other side). Order of operations is part of the contract.

## Risks / Trade-offs

- **[Risk]** RED tests that patch `celery.Task.delay` can easily drift from the real task path once GREEN wires things up. → **Mitigation:** assert the dispatch by **task name string** (`sms_worker.send_order_notification_sms`), not by reference identity, and add a structural test that `send_order_notification_sms` is registered as a Celery task under that exact name.
- **[Risk]** Frozen RU/EN strings make copy changes painful. → **Mitigation:** the strings come from PDD §6.1, which is authoritative. Any copy change requires an OpenSpec change that updates both PDD and the frozen strings in the test — exactly the review gate we want.
- **[Risk]** Worker tests that call `.run(...)` bypass Celery's retry machinery and re-implement it in-test, diverging from production. → **Mitigation:** also add one integration-style test that uses the existing EAGER-broker fixture pattern from `test_otp_task.py` to confirm real retry wiring, while leaning on direct-call tests for per-branch assertions.
- **[Trade-off]** This RED suite does not cover FE rendering of the notifications feed. That is owned by a later customer-facing change.

## Migration Plan

No database migration. The `notifications` table already exists. This change only introduces test files.

## Open Questions

None — the PDD §6.1 matrix and §7.8/§8.2 constraints are explicit. Any edge case the GREEN-cycle agent discovers should trigger a follow-up question, not an assumption.
