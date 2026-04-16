## Why

Phase 3 (Order & Payment) of Aura Coffee needs a notification subsystem that informs customers about order-status transitions per PDD §6.1. Per the project's Two-Change Model (AGENTS.md → "Development Methodology: TDD"), we land the RED cycle first — a failing test suite that pins down the contract for the notification service (core-api) and SMS delivery task (sms-worker) before any implementation. Tests freeze the status→channel matrix, RU/EN message texts, `short_id` derivation, SMS length rule, Celery task name/payload, retry semantics (§7.8), and DB status transitions on the `notifications` table.

## What Changes

- Add `services/core-api/tests/test_notification_service.py` — tests for `send_order_notification(order_id, user_id, new_status, db_session, cancelled_by=None)`:
  - IN_APP Notification row is always created with `status = SENT`, bilingual `message_ru` / `message_en`, correct `channel`, `type = order_status_change`, FK to user/order.
  - SMS Notification row is created with `status = PENDING` only for statuses in the "SMS + in-app" matrix; no SMS row for `IN_DELIVERY`, `COMPLETED pickup`.
  - `short_id` = first 8 chars of order UUID.
  - Encrypted phone is loaded from `user_profiles` and passed to Celery by hex string (INV-013 — no raw phone on the queue).
  - Celery task dispatched by name `sms_worker.send_order_notification_sms` with positional/kw args `(notification_id, encrypted_phone_hex, message)`.
  - `preferred_language` from `user_profiles` selects which text is logged to the IN_APP row's primary channel representation (both columns remain populated — language preference is an orthogonal display choice per PDD §8.2 "Bilingual").
- Add `services/core-api/tests/test_notification_messages.py` — parametrized matrix freezing RU + EN message strings and required channels for every `(status, order_type, cancelled_by)` triple from PDD §6.1.
- Add `services/sms-worker/tests/test_notification_task.py` — tests for `send_order_notification_sms(notification_id, encrypted_phone_hex, message)`:
  - Reuses `_decrypt_phone` + `_TRANSPORT` established by `tasks/otp.py`.
  - On transport success: `Notification.status = SENT`, `sent_at = now` (UTC).
  - On repeated transport failure (3 attempts, backoff 2s/8s/32s per §7.8): final attempt flips `Notification.status = FAILED` and logs error. Intermediate attempts raise to let Celery retry.
  - Does NOT block order flow — failure is local to the Notification row.
- All new tests perform imports of the not-yet-existing modules INSIDE function bodies so pytest can still collect the file. Every test MUST fail with `ImportError`/`AttributeError`/assertion until the GREEN cycle implements the modules.

## Capabilities

### New Capabilities
- `order-notifications-tests`: RED-cycle test suite that pins the Phase 3 order-notification contract (core-api `send_order_notification` service + sms-worker `send_order_notification_sms` task) from PDD §6.1 (status transitions/channels), §7.8 (SMS delivery chain / retries), §8.2 (SMS content & length). Lives in `services/core-api/tests/` and `services/sms-worker/tests/`.

### Modified Capabilities
<!-- None. No existing spec's requirements change. -->

## Impact

- Affected code: `services/core-api/tests/` and `services/sms-worker/tests/` (new test files only).
- Affected tooling: `pytest` test suite gains new failing tests (expected during RED).
- Affected dependencies: none — tests use existing pytest, SQLAlchemy, Celery test utilities already in the project.
- Not affected in this cycle: production code under `services/core-api/src/core_api/services/notification.py`, `services/sms-worker/src/sms_worker/tasks/notification.py`, shared modules, Alembic migrations, or seeds — those ship in the GREEN cycle.

## MVP Phase

- Phase 3: Order & Payment (PDD §7.1).

## Non-Goals

- No production implementation of the notification service or SMS task (GREEN cycle).
- No HTTP endpoints, routes, or IN_APP delivery transport (polling/WebSocket) — the IN_APP row is the source of truth; UI retrieval is a separate capability.
- No Order/Payment state-machine transition logic (§6.1 behavior tests are owned by order-lifecycle changes).
- No rate-limit changes — status notifications are not rate-limited (§7.8: "rate-limit НЕ проверяется").
- No frontend work (customer/admin SPAs) — no tests for rendering the notifications feed.
- No migrations — the `notifications` table already ships with Phase 3 schema (change `2026-04-16-phase3-schema-green`).
- No YuKassa / payment-worker integration.
