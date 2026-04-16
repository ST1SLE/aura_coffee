## ADDED Requirements

### Requirement: RED test module for core-api notification service

The system SHALL ship a pytest test module `services/core-api/tests/test_notification_service.py` that captures the DB-level contract of `core_api.services.notification.send_order_notification`. Every test MUST fail (import-time or assertion-time) until the GREEN cycle lands the implementation. Imports of the target module MUST occur inside test function bodies so pytest can still collect the file.

**PDD refs:** §6.1 (Order Lifecycle notification column), §7.8 (SMS Delivery Chain), §8.2 (SMS content / length). **INV refs:** INV-013, INV-016.

#### Scenario: Import pins target module existence

- **WHEN** pytest runs a test that does `from core_api.services.notification import send_order_notification` inside its body
- **THEN** the test MUST fail with `ImportError` or `ModuleNotFoundError` during RED (module does not exist yet) and MUST pass after GREEN implements it

#### Scenario: IN_APP Notification row is always written with status=SENT

- **WHEN** `send_order_notification` is called for any transition listed in PDD §6.1 that produces a notification
- **THEN** exactly one `Notification` row with `channel = IN_APP`, `type = ORDER_STATUS_CHANGE`, `status = SENT`, populated `message_ru`, `message_en`, and FKs to the user and order MUST be committed to the DB session

#### Scenario: SMS Notification row is written only for SMS-required statuses

- **WHEN** `send_order_notification` is called for a status whose PDD §6.1 cell starts with "SMS + in-app"
- **THEN** a second `Notification` row with `channel = SMS`, `type = ORDER_STATUS_CHANGE`, `status = PENDING`, populated `message_ru`/`message_en`, FKs to the user and order MUST be committed

#### Scenario: No SMS row for in-app-only statuses

- **WHEN** `send_order_notification` is called for `IN_DELIVERY` or for `COMPLETED` with `order.type = PICKUP`
- **THEN** only the IN_APP row MUST be created; no SMS Notification row is written and the Celery dispatcher MUST NOT be called

#### Scenario: Celery task enqueued by name with correct payload

- **WHEN** an SMS-required transition causes dispatch
- **THEN** the task registered as `sms_worker.send_order_notification_sms` MUST be enqueued with positional/keyword arguments `(notification_id, encrypted_phone_hex, message)` where `notification_id` equals the committed SMS-row UUID, `encrypted_phone_hex` is the hex string read from `user_profiles.phone_encrypted`, and `message` equals the SMS body produced for that status

#### Scenario: Phone never crosses Celery boundary in plaintext (INV-013)

- **WHEN** the service dispatches the SMS task
- **THEN** the second positional argument MUST be hex-encoded ciphertext (matches `^[0-9a-f]+$`, length > 24) and MUST NOT equal the user's plaintext phone

#### Scenario: cancelled_by selects the right CANCELLED text

- **WHEN** `send_order_notification(..., new_status=CANCELLED, cancelled_by="customer")` is called
- **THEN** the notification text MUST be "Заказ №{short_id} отменён, средства возвращены"; and when `cancelled_by="admin"` the text MUST be "Заказ №{short_id} отменён кофейней"

#### Scenario: Unknown transition rejected (INV-016)

- **WHEN** `send_order_notification` is called with `new_status=CREATED` (no incoming-transition notification per §6.1) or with `CANCELLED` and `cancelled_by=None`
- **THEN** the service MUST raise `ValueError` and MUST NOT write any row

#### Scenario: short_id is first 8 hex chars of order UUID

- **WHEN** an order's UUID is `c0ffee11-1234-4567-89ab-cdefdeadbeef`
- **THEN** the `short_id` substituted into both RU and EN texts MUST equal `c0ffee11`

#### Scenario: SMS row committed before dispatch

- **WHEN** the dispatcher's `.delay()` is patched to capture call order
- **THEN** the captured `notification_id` MUST match a row already visible in the DB session at the moment `.delay()` is invoked (row committed/flushed before dispatch)

### Requirement: RED test module for message matrix

The system SHALL ship `services/core-api/tests/test_notification_messages.py` that exhaustively pins, per PDD §6.1, the tuple `(channels, message_ru, message_en, sms_body, requires_sms)` for every combination of `(new_status, order_type, cancelled_by)`. Strings MUST appear as literals in the test (not derived from the implementation) to act as a copy-freeze.

**PDD refs:** §6.1, §8.2.

#### Scenario: Matrix covers all 9 notification-emitting cases

- **WHEN** pytest collects this module
- **THEN** a `@pytest.mark.parametrize` decorator MUST enumerate exactly these 9 cases: `PAID`, `PREPARING`, `READY+pickup`, `READY+delivery`, `IN_DELIVERY`, `COMPLETED+pickup`, `COMPLETED+delivery`, `CANCELLED+customer`, `CANCELLED+admin`

#### Scenario: Frozen RU texts match PDD §6.1 verbatim

- **WHEN** each matrix case is resolved
- **THEN** `message_ru` MUST equal, letter for letter:
  - PAID: "Заказ №{short_id} оплачен"
  - PREPARING: "Заказ №{short_id} готовится"
  - READY+pickup: "Заказ №{short_id} готов, заберите"
  - READY+delivery: "Заказ №{short_id} готов"
  - IN_DELIVERY: "Курьер забрал заказ №{short_id}"
  - COMPLETED+pickup: "Заказ №{short_id} завершён"
  - COMPLETED+delivery: "Заказ №{short_id} доставлен"
  - CANCELLED+customer: "Заказ №{short_id} отменён, средства возвращены"
  - CANCELLED+admin: "Заказ №{short_id} отменён кофейней"

#### Scenario: Frozen EN texts exist for every case

- **WHEN** each matrix case is resolved
- **THEN** `message_en` MUST be a non-empty string, MUST NOT be equal to `message_ru`, and MUST contain the literal substring `#{short_id}` or the short_id value when rendered

#### Scenario: requires_sms flag matches PDD matrix

- **WHEN** each matrix case is resolved
- **THEN** `requires_sms` MUST be `True` for PAID, PREPARING, both READY variants, COMPLETED+delivery, CANCELLED+customer, CANCELLED+admin; and MUST be `False` for IN_DELIVERY, COMPLETED+pickup

#### Scenario: SMS body length ≤ 70 characters (§8.2)

- **WHEN** each matrix case with `requires_sms == True` is rendered with a worst-case `short_id` of 8 hex chars
- **THEN** `sms_body = f"{status_text}. Заказ №{short_id}. Aura Coffee"` MUST satisfy `len(sms_body) <= 70`

### Requirement: RED test module for sms-worker notification task

The system SHALL ship `services/sms-worker/tests/test_notification_task.py` that pins the contract of `sms_worker.tasks.notification.send_order_notification_sms`. Tests MUST fail at RED with ImportError and pass after GREEN.

**PDD refs:** §7.8 (retry 2s/8s/32s), §8.2. **INV refs:** INV-013.

#### Scenario: Task registered under Celery name

- **WHEN** the sms_worker Celery app is introspected
- **THEN** a task named exactly `sms_worker.send_order_notification_sms` MUST be registered (the test imports the task and asserts `task.name == "sms_worker.send_order_notification_sms"`)

#### Scenario: Success path flips Notification to SENT

- **WHEN** the transport (monkeypatched to return `True`) succeeds on the first attempt
- **THEN** the task MUST load the Notification row by id, set `status = SENT`, set `sent_at` to a UTC datetime within the last few seconds, and commit

#### Scenario: Decrypted phone is what reaches the transport

- **WHEN** the task is invoked with an encrypted hex produced by `AESGCM` encrypt over a known phone
- **THEN** the transport MUST be called with the matching decrypted phone string (full roundtrip with `_decrypt_phone` or equivalent)

#### Scenario: Intermediate failure raises to trigger Celery retry

- **WHEN** the transport returns `False` and `self.request.retries < self.max_retries`
- **THEN** the task MUST raise an exception (so Celery reschedules with backoff) and MUST NOT flip the Notification status

#### Scenario: Exhausted retries flip Notification to FAILED

- **WHEN** the transport returns `False` and `self.request.retries >= self.max_retries`
- **THEN** the task MUST set `Notification.status = FAILED`, log an error containing the notification_id, and MUST NOT raise to the caller

#### Scenario: Retry configuration is 3 attempts with 2s/8s/32s backoff (§7.8)

- **WHEN** the Celery task is introspected (attributes `max_retries`, `default_retry_delay`, `retry_backoff`, `retry_backoff_max`)
- **THEN** `max_retries == 3`, `default_retry_delay == 2`, `retry_backoff is True`, `retry_backoff_max == 32`

#### Scenario: No plaintext phone leaks to logs (INV-013)

- **WHEN** the task runs end-to-end (success or failure path) with `caplog`
- **THEN** no captured log record MUST contain the decrypted phone string; only truncated notification identifiers are permitted in log output
