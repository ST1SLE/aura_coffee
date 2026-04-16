## Why

The RED cycle (`2026-04-16-order-notifications-red`) shipped a failing test suite that pins the Phase 3 order-notification contract from PDD §6.1 / §7.8 / §8.2. GREEN now implements the two production modules those tests exercise: the core-api `notification` service that writes `Notification` rows + dispatches SMS, and the sms-worker `notification` task that decrypts the phone, calls the SMS transport, and flips row status. The tests are the spec — this cycle makes them pass without modifying them (except for trivial whitespace/assertion-lookup fixes that do not weaken what is asserted).

## What Changes

- Add `services/core-api/src/core_api/services/notification.py`:
  - `resolve_notification_text(new_status, order_type, cancelled_by, short_id) -> NotificationText` — pure lookup against the frozen §6.1 matrix. Returns a dataclass with `message_ru`, `message_en`, `sms_status_ru`, `sms_status_en`, `requires_sms`.
  - `build_sms_body(status_text, short_id) -> str` — pure formatter `"{status_text}. Заказ №{short_id}. Aura Coffee"` (§8.2, ≤70 chars for the frozen matrix).
  - `send_order_notification(order_id, user_id, new_status, db_session, cancelled_by=None) -> None`:
    1. Validate transition (raise `ValueError` for unknown transitions and for `CANCELLED` without `cancelled_by`, per INV-016).
    2. Resolve text; derive `short_id = str(order.id)[:8]`.
    3. Insert `Notification(channel=IN_APP, type=ORDER_STATUS_CHANGE, status=SENT, message_ru, message_en, user_id, order_id, sent_at=now)`; flush.
    4. If `requires_sms`: load encrypted phone hex from `user_profiles`, insert `Notification(channel=SMS, type=ORDER_STATUS_CHANGE, status=PENDING, …)`; flush + commit; enqueue Celery task `sms_worker.send_order_notification_sms` with `(notification_id, encrypted_phone_hex, message)`. RU SMS body is used — `preferred_language` is ignored for SMS (PDD §8.2 pins SMS format, not language).
  - Expose `send_order_notification_sms` as a module-level attribute so tests can patch it.
- Add `services/sms-worker/src/sms_worker/tasks/notification.py`:
  - `send_order_notification_sms(self, notification_id, encrypted_phone_hex, message)` — Celery task with `name="sms_worker.send_order_notification_sms"`, `max_retries=3`, `default_retry_delay=2`, `retry_backoff=True`, `retry_backoff_max=32` (§7.8).
  - Load `Notification` row; decrypt phone via `_decrypt_phone` (promoted to `sms_worker.tasks.crypto` module, reused by `otp.py`); call `_TRANSPORT.send(phone, message)`.
  - Success → `status=SENT`, `sent_at=now`, commit.
  - Transport returns `False` and `self.request.retries < max_retries` → raise `Retry` (or generic `Exception`) so Celery backs off; status stays `PENDING`.
  - Exhausted retries (`retries >= max_retries`) → `status=FAILED`, log error with first-8 chars of notification id, return normally (don't blow up the worker).
  - Missing row → log warning, return; don't raise.
  - No plaintext phone appears in any log record (INV-013).
- Refactor `services/sms-worker/src/sms_worker/tasks/otp.py` to import `_decrypt_phone` and `_TRANSPORT` from a shared sibling module (`sms_worker.tasks.crypto`, `sms_worker.tasks.transport`) so both tasks share a single implementation.
- Register the new task via existing `autodiscover_tasks(["sms_worker.tasks"])` — no Celery app changes needed beyond ensuring import on startup.

## Capabilities

### New Capabilities
- `order-notifications`: Production notification pipeline for Phase 3 — core-api notification service + sms-worker SMS delivery task. Emits Notification rows per PDD §6.1 and delivers SMS per §7.8 / §8.2.

### Modified Capabilities
<!-- None. The RED capability `order-notifications-tests` is complete and archived; GREEN does not modify its tests. -->

## Impact

- Affected code:
  - `services/core-api/src/core_api/services/notification.py` (new).
  - `services/sms-worker/src/sms_worker/tasks/notification.py` (new).
  - `services/sms-worker/src/sms_worker/tasks/crypto.py` + `services/sms-worker/src/sms_worker/tasks/transport.py` (new; extracted from `otp.py`).
  - `services/sms-worker/src/sms_worker/tasks/otp.py` (import paths updated; no behavior change).
- Affected tooling: the 84 RED tests flip from red to green. `docker compose exec core-api pytest` + `docker compose exec sms-worker pytest` both pass for the notification modules.
- Affected dependencies: none (reuses `cryptography.AESGCM`, Celery, SQLAlchemy already in the stack).
- Not affected: Alembic migrations (Notification model already shipped in `2026-04-16-phase3-schema-green`), HTTP routes (no endpoint added — consumers will query `notifications` directly in a later phase), YuKassa / payment-worker, frontend SPAs.

## MVP Phase

- Phase 3: Order & Payment (PDD §7.1) — completes the notification sub-pipeline that Phase 3 order-status transitions rely on.

## Non-Goals

- No IN_APP delivery transport (polling / WebSocket / push) — UI retrieval is a separate capability. IN_APP row is the source of truth; clients poll `notifications` via their own endpoint.
- No order state-machine logic — `send_order_notification` is called BY order transitions, not TO them. The caller is wired in by the order-lifecycle change.
- No rate-limiting on status notifications (§7.8: "rate-limit НЕ проверяется" for order SMS).
- No new HTTP routes, OpenAPI changes, or SPA work.
- No new migrations — Notification table already ships in Phase 3 schema.
- No changes to OTP SMS flow behavior (only file layout refactor to share helpers).
- No i18n of SMS bodies — §8.2 pins a single Russian format for the one-segment length budget.
