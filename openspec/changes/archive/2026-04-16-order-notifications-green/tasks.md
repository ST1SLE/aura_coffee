## 1. sms-worker: extract shared crypto + transport helpers

- [x] 1.1 [sms-worker] GREEN: create `services/sms-worker/src/sms_worker/tasks/crypto.py` with `decrypt_phone(encrypted_hex: str) -> str` (moves the AES-256-GCM decryption implementation from `otp.py`; reads `settings.encryption_key` as 64-char hex → 32-byte key; accepts nonce+ciphertext as hex). Preserve existing behavior exactly.
- [x] 1.2 [sms-worker] GREEN: create `services/sms-worker/src/sms_worker/tasks/transport.py` with the `SMSTransport` protocol (one method `send(phone: str, message: str) -> bool`), plus `get_transport() -> SMSTransport` factory that returns `LogTransport` when `settings.sms_backend == "log"` and `SMSRuTransport` otherwise. Move implementations from `otp.py`.
- [x] 1.3 [sms-worker] REFACTOR: update `services/sms-worker/src/sms_worker/tasks/otp.py` to import `_decrypt_phone` and `_TRANSPORT` from the new sibling modules; keep names as module-level re-bindings (`from .crypto import decrypt_phone as _decrypt_phone` + `from .transport import get_transport; _TRANSPORT = get_transport()`) so existing tests that patch `otp._TRANSPORT` still work.
- [x] 1.4 [sms-worker] VERIFY: run `docker compose exec sms-worker pytest services/sms-worker/tests/test_otp_task.py services/sms-worker/tests/test_log_transport.py -v` — all existing tests MUST pass with NO test-code changes.

## 2. core-api: notification service pure helpers

- [x] 2.1 [core-api] GREEN: create `services/core-api/src/core_api/services/notification.py` with:
  - `@dataclass(frozen=True) class NotificationText` with fields `message_ru: str, message_en: str, sms_status_ru: str | None, sms_status_en: str | None, requires_sms: bool`.
  - Module-level `_MATRIX: dict[tuple, tuple]` keyed by `(new_status, order_type, cancelled_by)` (with `None` for cancelled_by when not applicable, and normalized order_type for READY/COMPLETED). Values hold the raw template strings + `requires_sms` flag from PDD §6.1.
  - `resolve_notification_text(new_status, order_type, cancelled_by, short_id) -> NotificationText` — matches against `_MATRIX`; raises `ValueError` for unknown keys and for `CANCELLED` with `cancelled_by=None`; returns `NotificationText` with `short_id` substituted into `message_ru`/`message_en`.
  - `build_sms_body(status_text: str, short_id: str) -> str` returning `f"{status_text}. Заказ №{short_id}. Aura Coffee"`.
- [x] 2.2 [core-api] VERIFY: run `docker compose exec core-api pytest services/core-api/tests/test_notification_messages.py -v` — all 45 tests MUST pass (44 that were failing + the pre-existing `test_matrix_has_nine_cases`).

## 3. core-api: notification service main entrypoint

- [x] 3.1 [core-api] GREEN: in `services/core-api/src/core_api/services/notification.py` add `from sms_worker.tasks.notification import send_order_notification_sms` at module top (the Celery task is a registered name; importing it gives the `.delay()` dispatcher and satisfies the RED patch target `core_api.services.notification.send_order_notification_sms`).
- [x] 3.2 [core-api] GREEN: implement `send_order_notification(order_id, user_id, new_status, db_session, cancelled_by=None) -> None`:
  1. Load `Order` and `UserProfile` by id via the provided session. Raise `ValueError` if either missing.
  2. Compute `short_id = order.id.hex[:8]`.
  3. Call `resolve_notification_text(new_status, order.type, cancelled_by, short_id)` — propagates `ValueError` for invalid transitions.
  4. Insert IN_APP row: `Notification(user_id=user_id, order_id=order_id, channel=IN_APP, type=ORDER_STATUS_CHANGE, status=SENT, message_ru=result.message_ru, message_en=result.message_en, sent_at=datetime.now(UTC))`. `flush()`.
  5. If `result.requires_sms`:
     a. Read `profile.phone_encrypted` (bytes) → `encrypted_hex = profile.phone_encrypted.hex()` (handle both `bytes` and already-hex `str` inputs defensively).
     b. Build SMS body: `message = build_sms_body(result.sms_status_ru, short_id)`.
     c. Insert SMS row: `Notification(user_id=..., order_id=..., channel=SMS, type=ORDER_STATUS_CHANGE, status=PENDING, message_ru=result.message_ru, message_en=result.message_en)`. `flush()`. `commit()`.
     d. Dispatch: `send_order_notification_sms.delay(str(sms_row.id), encrypted_hex, message)`. Catch broker exceptions around `.delay()` (log + swallow) — notification failure MUST NOT propagate.
- [x] 3.3 [core-api] VERIFY: run `docker compose exec core-api pytest services/core-api/tests/test_notification_service.py -v` — all 33 tests MUST pass (31 that were failing + the 2 pre-existing fixture smokes).

## 4. sms-worker: notification task

- [x] 4.1 [sms-worker] GREEN: create `services/sms-worker/src/sms_worker/tasks/notification.py` with module-level:
  - `from .crypto import decrypt_phone as _decrypt_phone`
  - `from .transport import get_transport`
  - `_TRANSPORT = get_transport()` (bound at import so tests can patch `notif_module._TRANSPORT`)
  - `from sms_worker.app import app` (or the existing Celery app reference).
- [x] 4.2 [sms-worker] GREEN: implement the task:
  ```python
  @app.task(bind=True, name="sms_worker.send_order_notification_sms",
            max_retries=3, default_retry_delay=2, retry_backoff=True, retry_backoff_max=32)
  def send_order_notification_sms(self, notification_id: str, encrypted_phone_hex: str, message: str) -> None:
      with SessionLocal() as session:
          row = session.get(Notification, UUID(notification_id))
          if row is None:
              logger.warning("notification %s missing, skipping", str(notification_id)[:8])
              return
          phone = _decrypt_phone(encrypted_phone_hex)
          ok = _TRANSPORT.send(phone, message)
          if ok:
              row.status = NotificationStatus.SENT
              row.sent_at = datetime.now(UTC)
              session.commit()
              return
          if self.request.retries < self.max_retries:
              raise RuntimeError("sms transport returned False")
          row.status = NotificationStatus.FAILED
          session.commit()
          logger.error("notification %s delivery exhausted retries", str(notification_id)[:8])
  ```
  No log line MUST format the phone into the record (INV-013).
- [x] 4.3 [sms-worker] VERIFY: run `docker compose exec sms-worker pytest services/sms-worker/tests/test_notification_task.py -v` — all 9 tests MUST pass.

## 5. Integration verification

- [x] 5.1 [core-api] VERIFY: run `docker compose exec core-api pytest services/core-api/tests/ -v` — entire core-api suite passes, no regressions.
- [x] 5.2 [sms-worker] VERIFY: run `docker compose exec sms-worker pytest services/sms-worker/tests/ -v` — entire sms-worker suite passes.
- [x] 5.3 VERIFY: restart workers via `./scripts/up.sh --build core-api sms-worker` and confirm the sms-worker logs `"[INFO] Task sms_worker.send_order_notification_sms registered"` on startup (proves autodiscover picked up the new task module).
