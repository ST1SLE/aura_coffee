## Context

The RED cycle (`2026-04-16-order-notifications-red`) shipped 84 failing tests that pin the Phase 3 notification contract across three files:

- `services/core-api/tests/test_notification_service.py` (31 tests, + 2 fixture smokes) — DB side effects of `send_order_notification`, Celery dispatch args.
- `services/core-api/tests/test_notification_messages.py` (44 tests, + 1 trivial matrix-count) — frozen RU/EN/SMS-body matrix across all 9 §6.1 cases.
- `services/sms-worker/tests/test_notification_task.py` (9 tests) — retry config, success/failure DB transitions, PII non-leakage.

GREEN implements the two production modules the tests import inside their bodies:

- `services/core-api/src/core_api/services/notification.py` — service + pure helpers.
- `services/sms-worker/src/sms_worker/tasks/notification.py` — Celery task.

The existing `services/sms-worker/src/sms_worker/tasks/otp.py` already contains `_decrypt_phone` (AES-256-GCM) and `_TRANSPORT` (dev: log, prod: SMS.ru). Both need to be reused by the new notification task. The `notifications` table ships with Phase 3 schema and exposes `channel`, `type`, `status`, `message_ru`, `message_en`, `user_id`, `order_id`, `sent_at`, `created_at`.

Affected modules: **[core-api]** (new service module), **[sms-worker]** (new task module + minor refactor of `otp.py` imports).

## Goals / Non-Goals

**Goals:**

- Every RED test flips green with no test-code edits (the tests ARE the spec).
- The core-api service MUST remain the only place that reads `user_profiles.phone_encrypted`; the hex crosses the Celery boundary unchanged (INV-013).
- The sms-worker task MUST reuse the exact decryption + transport path already validated by `tasks/otp.py` — no second implementation of AES-GCM or transport selection.
- The notification subsystem MUST NOT block order flow: transport failure, broker failure, and decryption failure MUST NOT propagate past the task boundary (task owns its own FAILED status).
- All §6.1 message strings live in ONE place in the codebase — the service module — and are referenced by both IN_APP row writes and SMS dispatch.

**Non-Goals:**

- No HTTP endpoints to read notifications (consumers poll the table directly in a later change).
- No order state-machine wiring — callers of `send_order_notification` (webhook handlers, barista actions) belong to order-lifecycle changes.
- No frontend rendering of the notification feed.
- No new Alembic migrations.
- No changes to the OTP SMS flow beyond moving `_decrypt_phone` / `_TRANSPORT` to shared sibling modules (behavior-preserving refactor).
- No localization of SMS bodies (§8.2 pins a single Russian format).

## Decisions

### D1 — Extract `_decrypt_phone` and `_TRANSPORT` into shared sibling modules

**Decision:** Create `services/sms-worker/src/sms_worker/tasks/crypto.py` containing `decrypt_phone(encrypted_hex: str) -> str` and `services/sms-worker/src/sms_worker/tasks/transport.py` containing the `SMSTransport` protocol + `get_transport() -> SMSTransport` factory that reads `settings.sms_backend`. Update `tasks/otp.py` to import from these. The new `tasks/notification.py` imports the same symbols.

**Why X over Y:** Alternative — copy the code into `notification.py` — creates two AES-GCM implementations that can drift silently and makes transport-swap tests inconsistent. Alternative — `from sms_worker.tasks.otp import _decrypt_phone` — couples two tasks by implementation name (the leading underscore is a signal the author intended module-private).

**RED test compatibility:** The RED worker tests patch `notif_module._TRANSPORT` and `notif_module.settings`. To keep this working, `tasks/notification.py` re-binds `_TRANSPORT = get_transport()` at module import time as a module-level name — the same pattern `otp.py` already uses. Tests patch the name on `notif_module`; the task's call site MUST read `_TRANSPORT` via module-level lookup (`from sms_worker.tasks import notification as _n; _n._TRANSPORT.send(...)` from within the module itself, i.e., `from . import transport as _transport; _TRANSPORT = _transport.get_transport()` at module top and `_TRANSPORT.send(...)` inside the task body so `unittest.mock.patch.object` can replace the binding).

### D2 — `resolve_notification_text` is a pure function returning a dataclass

**Decision:** Define `@dataclass(frozen=True) class NotificationText` with fields `message_ru: str, message_en: str, sms_status_ru: str | None, sms_status_en: str | None, requires_sms: bool`. `resolve_notification_text(new_status, order_type, cancelled_by, short_id) -> NotificationText` matches against the §6.1 matrix and returns the populated dataclass (with `short_id` already substituted into `message_ru`/`message_en`). Unknown transitions raise `ValueError` (INV-016). `CANCELLED` with `cancelled_by=None` raises `ValueError`.

**Why X over Y:** The RED matrix tests assert `result.message_ru`, `result.message_en`, `result.requires_sms`, `result.sms_status_ru`, `result.sms_status_en` — the attribute names come directly from the test. A dataclass is the most direct shape that satisfies those accesses. Alternative — `TypedDict` — loses equality/repr ergonomics; alternative — tuple — breaks the attribute-access contract.

### D3 — `build_sms_body` is a second pure function

**Decision:** `build_sms_body(status_text: str, short_id: str) -> str` returns `f"{status_text}. Заказ №{short_id}. Aura Coffee"`. It does NOT take `new_status` / `order_type` / `cancelled_by` — the caller runs `resolve_notification_text` first and passes `result.sms_status_ru`.

**Why X over Y:** Keeps the two concerns (matrix lookup vs. format string) independently testable. Matches the RED test file structure: one test pins the matrix outputs; a separate test pins the SMS format string and its ≤70-char budget. Alternative — single function returning everything — fails the RED test `test_sms_body_substitutes_short_id` which invokes `build_sms_body("Оплачен", short_id="c0ffee11")` directly.

### D4 — IN_APP text always uses RU as the "primary" row text; EN is mirrored in `message_en`

**Decision:** The `Notification` row stores both `message_ru` and `message_en` unconditionally. `preferred_language` on `user_profiles` is NOT consulted by the service — bilingual storage is the source of truth; the consumer (SPA) picks the language at render time. For the SMS body, RU is used unconditionally (PDD §8.2 does not define an EN SMS format).

**Why X over Y:** Matches `test_in_app_row_text_matches_preferred_language_selection` which asserts "both `message_ru` and `message_en` are populated (both columns are written regardless of preference)". Also matches the RED `send_order_notification` tests that never pass `preferred_language` as a parameter. Alternative — parameterize on language — contradicts the RED contract.

### D5 — Dispatcher is a module-level callable named `send_order_notification_sms`

**Decision:** The service module contains the line `from sms_worker.tasks.notification import send_order_notification_sms` at module top level. The `send_order_notification` function calls `send_order_notification_sms.delay(notification_id, encrypted_phone_hex, message)`.

**Why X over Y:** The RED test patches `core_api.services.notification.send_order_notification_sms` with `MagicMock` and asserts `.delay(...)` was called with the expected args. Only a module-level symbol patched on the service module satisfies this. Alternative — `from celery import current_app; current_app.send_task("sms_worker.send_order_notification_sms", ...)` — would break `test_celery_task_is_dispatched_by_registered_name` which asserts `send_order_notification_sms.name == "..."`.

### D6 — Commit Notification rows before `.delay()`

**Decision:** Inside `send_order_notification`, after `db_session.add(sms_row); db_session.flush(); db_session.commit()`, THEN call `.delay(...)`. If the caller passes a session in an outer transaction that they want to roll back, they should not call the notification service (notifications are side effects — §6.1 treats them as informational).

**Why X over Y:** Matches `test_sms_row_committed_before_dispatch` which asserts the dispatcher sees a row already visible via a fresh query. Also aligns with the Atomicity Analysis from RED: notification failure MUST NOT roll back order flow, so the notification commit is its own unit. Alternative — flush-only, caller commits — risks the worker looking up an id that has been rolled back.

**Session contract:** the RED tests hand the service a `db_session` fixture that is itself a short transaction rolled back at test exit. In production, callers MUST pass a committed-or-about-to-be-committed session. This is documented in the service docstring.

### D7 — `short_id` derivation

**Decision:** `short_id = str(order.id).replace("-", "")[:8]` where `order.id` is a `uuid.UUID`. For UUID `c0ffee11-1234-4567-89ab-cdefdeadbeef` this yields `"c0ffee11"`.

**Why X over Y:** Matches `test_short_id_is_first_8_hex_chars_of_uuid` — the test uses that exact UUID and expects `"c0ffee11"`. Equivalent to `order.id.hex[:8]`. Chose `.hex[:8]` in the implementation (no intermediate dashes, more explicit).

### D8 — Celery task configuration

**Decision:** `@shared_task(bind=True, name="sms_worker.send_order_notification_sms", max_retries=3, default_retry_delay=2, retry_backoff=True, retry_backoff_max=32)`.

**Why X over Y:** Every attribute name + value is asserted literally by `test_task_retry_configuration_matches_pdd_7_8`. Task name is asserted by `test_task_is_registered_under_expected_name`. No alternatives are viable.

### D9 — Retry decision: raise on intermediate failure, mark FAILED on exhaustion

**Decision:** Inside the task, after `_TRANSPORT.send(phone, message)` returns:

- `True` → set `status=SENT`, `sent_at=datetime.now(UTC)`, commit, return.
- `False` and `self.request.retries < self.max_retries` → raise `self.retry(exc=RuntimeError("sms transport returned False"))`. Celery re-schedules with backoff. Notification row stays `PENDING`.
- `False` and `self.request.retries >= self.max_retries` → set `status=FAILED`, commit, log `logger.error(...)` with notification-id prefix, return normally.
- Row not found by id → log warning, return normally.

Exceptions from the transport bubble up to trigger Celery retry the same way `False` on an intermediate attempt does (Celery's built-in retry handles any unhandled exception; explicit `self.retry()` is only used for the `False` branch).

**Why X over Y:** Matches `test_intermediate_failure_raises_for_retry` (raise), `test_exhausted_retries_marks_failed_and_does_not_raise` (no raise, status FAILED), `test_missing_notification_row_logs_and_returns` (warn, return). Alternative — always `self.retry()` — fails the exhaustion test that asserts the task returns normally.

### D10 — PII non-leakage in logs

**Decision:** All log lines emitted by the task reference the notification only by `str(notification_id)[:8]` prefix. The decrypted phone is held in a local variable and passed to `_TRANSPORT.send()`; it is never formatted into a log record. The `_TRANSPORT` itself (dev: log-writer) MUST also mask the phone — but that is outside this change's scope (already true in `otp.py`'s log transport).

**Why X over Y:** Matches `test_plaintext_phone_not_in_logs` which runs both success and failure paths with `caplog` and asserts no record contains `"+79991234567"`. INV-013 mandates this.

## State machine impact

The GREEN service implements the NOTIFICATION side effect of §6.1 state transitions; it does NOT mutate order state. Transitions that MUST produce notifications (matches D9 of the RED design and the RED test matrix):

- `CREATED → PAID` (SMS+in-app)
- `PAID → PREPARING` (SMS+in-app)
- `PREPARING → READY` (SMS+in-app; two variants by order.type)
- `READY → IN_DELIVERY` (in-app only)
- `IN_DELIVERY → COMPLETED` (SMS+in-app for delivery)
- `READY → COMPLETED` pickup (in-app only)
- `* → CANCELLED` (SMS+in-app; two variants by `cancelled_by`)

Per INV-016 the service raises `ValueError` on any other `new_status` and on `CANCELLED` without `cancelled_by`.

## 152-FZ Compliance (INV-013)

- The service reads `UserProfile.phone_encrypted` (bytes) from the DB and passes it to the worker as `.hex()`. Plaintext phone NEVER crosses the Celery boundary.
- The worker decrypts inside its own process; plaintext phone is held in a local variable and passed to `_TRANSPORT.send(...)`. It is never formatted into a log record (D10).
- Tests verify: service dispatch payload matches `^[0-9a-f]+$` with length > 24 (RED `test_plaintext_phone_never_passed_to_task`); worker success+failure paths contain no `+79991234567` in `caplog` (RED `test_plaintext_phone_not_in_logs`).

## Atomicity Analysis

INV-004 does not apply — notifications are side effects, not financial state. The GREEN implementation enforces:

1. Notification rows are committed in their own short transaction BEFORE `.delay()` is called (D6). This guarantees the worker can always find the row the Celery message refers to.
2. A failure to enqueue (broker down) MUST NOT roll back the notification row. The GREEN service catches `Exception` around `.delay(...)`, logs an error, and returns normally. (The row stays `PENDING` forever, which is acceptable — a follow-up reconciliation job can mark stale rows `FAILED`, but that is out of scope for this change.)
3. The outer caller's order-status mutation runs in its own transaction; notification failure MUST NOT propagate. The service never re-raises broker/DB errors to the caller. Exceptions from `resolve_notification_text` (INV-016 violations) DO propagate — but those are programmer errors, not runtime failures.

## Risks / Trade-offs

- **[Risk]** Module-level `_TRANSPORT = get_transport()` at import time freezes the transport choice for the lifetime of the worker process. Swapping `settings.sms_backend` at runtime requires a worker restart. → **Mitigation:** acceptable — matches `otp.py` behavior and the operational model (docker-compose reloads workers on settings change).
- **[Risk]** Committing the notification row before `.delay()` means a broker outage leaves `PENDING` rows with no enqueued task. → **Mitigation:** log the broker error with the notification id; operators can re-enqueue via a management command (not implemented here, but the data shape supports it). Alternative — write row AFTER dispatch — worse: worker receives an id that doesn't exist.
- **[Risk]** Moving `_decrypt_phone` / `_TRANSPORT` out of `otp.py` could regress the OTP flow. → **Mitigation:** refactor preserves behavior (re-export via `from .crypto import decrypt_phone as _decrypt_phone`, same for transport). Existing `test_otp_task.py` MUST still pass without modification.
- **[Trade-off]** `send_order_notification` reads and writes in one transaction, then calls `.delay()`. This blocks the caller on the commit. Async variant (enqueue a prep task that does the DB write + dispatch) is out of scope — HTTP handlers already tolerate a single extra commit.

## Migration Plan

No database migration. No seed changes. Deploy is strictly code:

1. Land GREEN branch.
2. Rebuild `core-api` and `sms-worker` images.
3. `./scripts/up.sh --build core-api sms-worker` to reload.
4. Rollback: revert the two new files + the `otp.py` import changes. The `notifications` table is unaffected.

## Open Questions

None — RED tests and PDD §6.1/§7.8/§8.2 fully specify the contract. Any ambiguity the GREEN-cycle agent encounters must surface as a question before assuming.
