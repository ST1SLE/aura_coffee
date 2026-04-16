# order-notifications Specification

## Purpose
TBD - created by archiving change order-notifications-green. Update Purpose after archive.
## Requirements
### Requirement: Core-API notification service emits Notification rows per PDD §6.1

The system SHALL provide `core_api.services.notification.send_order_notification(order_id, user_id, new_status, db_session, cancelled_by=None) -> None` that writes an IN_APP Notification row for every transition listed in PDD §6.1 and, for SMS-required transitions, writes a second SMS Notification row and dispatches a Celery task to `sms-worker`. Notification failure MUST NOT propagate to the caller (INV-004 does not apply — notifications are side effects).

**PDD refs:** §6.1 (Order Lifecycle), §8.2 (SMS format). **INV refs:** INV-013, INV-016.

#### Scenario: IN_APP row always created with status=SENT

- **WHEN** `send_order_notification` is called for any §6.1 transition
- **THEN** exactly one `Notification` row MUST be committed with `channel = IN_APP`, `type = ORDER_STATUS_CHANGE`, `status = SENT`, populated `message_ru` + `message_en`, and FKs to the user and order

#### Scenario: SMS row created for SMS-required transitions

- **WHEN** `send_order_notification` is called for a transition whose §6.1 cell starts with "SMS + in-app"
- **THEN** a second `Notification` row MUST be committed with `channel = SMS`, `type = ORDER_STATUS_CHANGE`, `status = PENDING`, populated `message_ru` + `message_en`, AND the Celery task `sms_worker.send_order_notification_sms` MUST be dispatched with positional args `(notification_id, encrypted_phone_hex, message)`

#### Scenario: No SMS row for in-app-only transitions

- **WHEN** `send_order_notification` is called with `new_status=IN_DELIVERY` or with `new_status=COMPLETED` and `order.type=PICKUP`
- **THEN** only the IN_APP row MUST be committed; no SMS Notification row is written and no Celery task is dispatched

#### Scenario: Unknown transition rejected (INV-016)

- **WHEN** `send_order_notification` is called with `new_status=CREATED` (no notification per §6.1), or with `new_status=CANCELLED` and `cancelled_by=None`
- **THEN** the service MUST raise `ValueError` and MUST NOT write any Notification row

#### Scenario: cancelled_by discriminates CANCELLED wording

- **WHEN** `send_order_notification(..., new_status=CANCELLED, cancelled_by="customer")` is called
- **THEN** the IN_APP row's `message_ru` MUST equal `"Заказ №{short_id} отменён, средства возвращены"`, and for `cancelled_by="admin"` it MUST equal `"Заказ №{short_id} отменён кофейней"`

#### Scenario: short_id is first 8 hex chars of order UUID

- **WHEN** an order with `id = UUID("c0ffee11-1234-4567-89ab-cdefdeadbeef")` triggers a notification
- **THEN** the substituted `short_id` in both `message_ru` and `message_en` MUST be `"c0ffee11"`

### Requirement: Service passes only encrypted phone across Celery boundary (INV-013)

The system SHALL read phone data as the hex-encoded ciphertext stored on `user_profiles.phone_encrypted` and pass it unchanged to the Celery task. Plaintext phone MUST NOT cross the Celery boundary.

**PDD refs:** §7.8. **INV refs:** INV-013.

#### Scenario: Dispatch payload is hex ciphertext

- **WHEN** `send_order_notification` dispatches the SMS task
- **THEN** the `encrypted_phone_hex` argument MUST match the regex `^[0-9a-f]+$`, have length > 24, and MUST NOT equal the plaintext phone

#### Scenario: SMS row committed before dispatch

- **WHEN** the Celery task's `.delay(...)` is invoked
- **THEN** the SMS Notification row referenced by the `notification_id` argument MUST already exist in the database with `status = PENDING` (committed before dispatch, so the worker can find it)

### Requirement: Pure helpers freeze PDD §6.1 matrix and §8.2 SMS format

The system SHALL provide `resolve_notification_text(new_status, order_type, cancelled_by, short_id) -> NotificationText` that returns the frozen RU/EN IN_APP text, short SMS status phrase (RU/EN), and `requires_sms` flag for every §6.1 case; and `build_sms_body(status_text, short_id) -> str` that formats `"{status_text}. Заказ №{short_id}. Aura Coffee"` within the 70-char single-Cyrillic-segment budget.

**PDD refs:** §6.1, §8.2.

#### Scenario: resolve returns frozen matrix for all 9 cases

- **WHEN** `resolve_notification_text` is called with any of the 9 §6.1 triples (PAID, PREPARING, READY+pickup, READY+delivery, IN_DELIVERY, COMPLETED+pickup, COMPLETED+delivery, CANCELLED+customer, CANCELLED+admin)
- **THEN** it MUST return a `NotificationText` whose `message_ru`/`message_en` match the frozen literals after `short_id` substitution, `requires_sms` matches the §6.1 matrix (True for 7 cases, False for IN_DELIVERY and COMPLETED+pickup), and `sms_status_ru`/`sms_status_en` are populated for SMS-required cases and `None` otherwise

#### Scenario: build_sms_body length budget (§8.2)

- **WHEN** `build_sms_body(status_text, short_id)` is called with any SMS-required `status_text` from the matrix and any 8-hex-char `short_id`
- **THEN** the returned string MUST satisfy `len(body) <= 70`, end with `. Aura Coffee`, and contain `Заказ №{short_id}`

#### Scenario: build_sms_body exact format

- **WHEN** `build_sms_body("Оплачен", short_id="c0ffee11")` is called
- **THEN** it MUST return exactly `"Оплачен. Заказ №c0ffee11. Aura Coffee"`

### Requirement: sms-worker notification task delivers SMS and updates Notification row

The system SHALL provide a Celery task `sms_worker.tasks.notification.send_order_notification_sms` registered under the name `"sms_worker.send_order_notification_sms"` that loads a Notification row, decrypts the phone, invokes the SMS transport, and updates `status` / `sent_at` based on outcome. The task MUST retry on transient failure and MUST NOT block the order flow.

**PDD refs:** §7.8 (retry 3× backoff 2s/8s/32s), §8.2. **INV refs:** INV-013.

#### Scenario: Task registered under expected name

- **WHEN** the Celery app is introspected
- **THEN** `send_order_notification_sms.name` MUST equal `"sms_worker.send_order_notification_sms"`

#### Scenario: Retry configuration matches §7.8

- **WHEN** the task's attributes are inspected
- **THEN** `max_retries == 3`, `default_retry_delay == 2`, `retry_backoff is True`, `retry_backoff_max == 32`

#### Scenario: Success updates Notification to SENT

- **WHEN** the transport returns `True`
- **THEN** the task MUST set `Notification.status = SENT`, set `sent_at` to a UTC datetime within the last few seconds, and commit

#### Scenario: Decrypted phone is what reaches the transport

- **WHEN** the task is invoked with an `encrypted_phone_hex` produced by AES-256-GCM over a known plaintext phone
- **THEN** the SMS transport MUST be called with the matching decrypted phone string

#### Scenario: Intermediate failure raises for retry

- **WHEN** the transport returns `False` and `self.request.retries < self.max_retries`
- **THEN** the task MUST raise an exception (so Celery reschedules with backoff) and the Notification row's `status` MUST remain `PENDING`

#### Scenario: Exhausted retries mark FAILED and return normally

- **WHEN** the transport returns `False` and `self.request.retries >= self.max_retries`
- **THEN** the task MUST set `Notification.status = FAILED`, log an error containing a prefix of the `notification_id`, and return without raising

#### Scenario: Missing notification row logged and skipped

- **WHEN** the task is invoked with a `notification_id` that does not exist in the database
- **THEN** the task MUST log a warning and return without raising

#### Scenario: Plaintext phone never leaks to logs (INV-013)

- **WHEN** the task runs end-to-end on either the success or failure path with `caplog` capturing all records
- **THEN** no captured record MUST contain the plaintext phone string

