## ADDED Requirements

<!-- References: PDD §4.2 (Payment Worker architecture), §6.1 (Order Lifecycle), §6.2 (Payment Lifecycle), §7.9 (Webhook Processing Chain), §8.1 (YuKassa compliance), INV-001 (single source of truth), INV-004 (atomic compensation), INV-016 (no status downgrades). -->

### Requirement: Payment Worker settings load YuKassa and infrastructure environment

The `Settings` class SHALL read the following environment variables with these semantics:

- `YUKASSA_SHOP_ID` (string, required in production — tests inject via monkeypatch)
- `YUKASSA_SECRET_KEY` (string, required in production)
- `YUKASSA_WEBHOOK_IPS` (comma-separated list; whitespace around each entry trimmed)
- `YUKASSA_BASE_URL` (string; defaults to `"https://api.yookassa.ru/v3"` when unset)
- `DATABASE_URL` (string)
- `REDIS_URL` (string; existing behavior preserved)

#### Scenario: Full environment round-trips into the model

- **WHEN** all five new env vars are set (plus the pre-existing `REDIS_URL`)
- **THEN** the `Settings` instance exposes `.yukassa_shop_id`, `.yukassa_secret_key`, `.yukassa_webhook_ips` (list), `.yukassa_base_url`, `.database_url`, and `.redis_url` with the corresponding values

#### Scenario: Default base URL when not set

- **WHEN** `YUKASSA_BASE_URL` is absent
- **THEN** `Settings().yukassa_base_url == "https://api.yookassa.ru/v3"`

#### Scenario: Comma list is trimmed and split

- **WHEN** `YUKASSA_WEBHOOK_IPS = "185.71.76.1, 185.71.76.2"`
- **THEN** `Settings().yukassa_webhook_ips == ["185.71.76.1", "185.71.76.2"]`

### Requirement: YukassaClient wraps the ЮKassa REST API

A `YukassaClient` class under `payment_worker.yukassa_client` SHALL expose `create_payment`, `get_payment`, and `create_refund`. It MUST use HTTP Basic auth (`shop_id:secret_key`), send amounts as strings with two decimal places (derived from an integer kopecks amount), attach an `Idempotency-Key` header on every create (PDD §8.1), and configure an `httpx.Client` with `connect = 10.0s` and `read = 30.0s`.

#### Scenario: create_payment posts to /v3/payments with full envelope

- **WHEN** `create_payment(amount_kopecks=12345, idempotency_key="uuid-1", return_url="https://r", description="Order #1")` is called
- **THEN** exactly one `POST {base_url}/payments` request is issued with `Authorization: Basic {b64(shop_id:secret_key)}`, `Idempotency-Key: uuid-1`, and JSON body `{"amount": {"value": "123.45", "currency": "RUB"}, "confirmation": {"type": "redirect", "return_url": "https://r"}, "capture": true, "description": "Order #1"}`

#### Scenario: create_payment returns a flat dict with id / confirmation_url / status

- **WHEN** ЮKassa returns `{"id": "pay_xyz", "status": "pending", "confirmation": {"confirmation_url": "https://yoo/confirm"}}`
- **THEN** the method's return value exposes `payment_id == "pay_xyz"`, `confirmation_url == "https://yoo/confirm"`, and `status == "pending"`

#### Scenario: get_payment uses GET and omits Idempotency-Key

- **WHEN** `get_payment("pay_abc")` is called
- **THEN** exactly one `GET {base_url}/payments/pay_abc` request is issued with HTTP Basic auth and no `Idempotency-Key` header

#### Scenario: create_refund posts a full-amount refund

- **WHEN** `create_refund(payment_id="pay_abc", amount_kopecks=12345, idempotency_key="uuid-2")` is called
- **THEN** exactly one `POST {base_url}/refunds` request is issued with `Idempotency-Key: uuid-2` and JSON body `{"payment_id": "pay_abc", "amount": {"value": "123.45", "currency": "RUB"}}`

#### Scenario: Amount formatting preserves two decimals for all ranges

- **WHEN** `amount_kopecks` is one of `100`, `12345`, `1`, `100000`
- **THEN** the JSON body's `amount.value` is `"1.00"`, `"123.45"`, `"0.01"`, `"1000.00"` respectively

#### Scenario: Client timeout is 10s connect / 30s read

- **WHEN** a `YukassaClient` is constructed with defaults
- **THEN** the underlying `httpx.Client` timeout has `connect == 10.0` and `read == 30.0`

### Requirement: create_payment Celery task persists success state

On a successful ЮKassa response, the task SHALL set `Payment.yukassa_payment_id`, `Payment.confirmation_url`, and `Payment.status = AWAITING_CONFIRMATION`. The Order MUST remain in `CREATED` until a webhook advances it (PDD §6.1, §6.2).

#### Scenario: Happy path updates Payment row

- **GIVEN** a seeded Order in `CREATED` and Payment in `PENDING`
- **WHEN** the task runs with a stubbed YukassaClient that returns `{"payment_id": "pay_xyz", "confirmation_url": "https://yoo/confirm", "status": "pending"}`
- **THEN** after the task returns, `Payment.yukassa_payment_id == "pay_xyz"`, `Payment.confirmation_url == "https://yoo/confirm"`, `Payment.status == AWAITING_CONFIRMATION`, and `Order.status == CREATED`

### Requirement: create_payment Celery task auto-retries transient failures

The task decorator SHALL expose `max_retries == 3`, `autoretry_for` including `httpx.RequestError`, and a truthy `retry_backoff`.

#### Scenario: Retry policy is introspectable

- **WHEN** the test reads the task attributes
- **THEN** `create_payment.max_retries == 3`, `httpx.RequestError in create_payment.autoretry_for`, and `bool(create_payment.retry_backoff) is True`

### Requirement: create_payment task compensates atomically on exhausted retries

A module-level helper `_fail_payment_and_cancel_order(order_id: str, payment_id: str) -> None` SHALL exist in `payment_worker.tasks`. It MUST, inside a single database transaction, set `Payment.status = PAYMENT_FAILED`, `Order.status = CANCELLED`, insert `LoyaltyTransaction(type=REVERSAL, amount=+points_used, balance_after=latest_balance + points_used)` when `points_used > 0`, and decrement `Promocode.current_uses` by 1 when a promocode is linked. The transaction MUST roll back on any exception.

#### Scenario: Helper cancels the order and unreserves loyalty + promo

- **GIVEN** an Order with `points_used = 100`, a RESERVATION loyalty row with `balance_after = 0`, and a Promocode with `current_uses = 1`
- **WHEN** `_fail_payment_and_cancel_order(order_id, payment_id)` runs
- **THEN** `Payment.status == PAYMENT_FAILED`, `Order.status == CANCELLED`, exactly one `LoyaltyTransaction` of type `REVERSAL` exists for that order with `amount == 100` and `balance_after == 100`, and `Promocode.current_uses == 0`

#### Scenario: Compensation rolls back when the promo step fails

- **GIVEN** the same seeded state as above
- **WHEN** `_decrement_promocode` is monkey-patched to raise `RuntimeError` mid-transaction
- **THEN** `Payment.status` remains `PENDING`, `Order.status` remains `CREATED`, and no new `LoyaltyTransaction` rows were committed

### Requirement: initiate_refund Celery task flips Payment on success and swallows failure

`initiate_refund(payment_id: str, amount_kopecks: int) -> None` SHALL call `YukassaClient.create_refund`; on any 2xx result it sets `Payment.status = REFUND_PENDING`; on any `Exception` it logs and returns without mutating Payment status and without re-raising.

#### Scenario: Successful refund flips Payment to REFUND_PENDING

- **GIVEN** a Payment in `SUCCEEDED`
- **WHEN** the task runs with a stubbed client that returns a refund response
- **THEN** `Payment.status == REFUND_PENDING`

#### Scenario: Failed refund leaves Payment untouched

- **GIVEN** a Payment in `SUCCEEDED`
- **WHEN** the task runs with a stubbed client that raises `httpx.RequestError`
- **THEN** the task does not raise, and `Payment.status == SUCCEEDED`

### Requirement: Webhook endpoint rejects untrusted source IPs

`POST /webhooks/yukassa` SHALL return HTTP 403 when the caller IP (from `X-Forwarded-For` or `request.client.host`) is not in `settings.yukassa_webhook_ips`. No DB or Redis mutation may occur.

#### Scenario: Untrusted IP returns 403 with no mutation

- **GIVEN** `YUKASSA_WEBHOOK_IPS` does not include `203.0.113.9`
- **WHEN** a valid `payment.succeeded` body arrives with `X-Forwarded-For: 203.0.113.9`
- **THEN** the response is 403 and the referenced Payment/Order rows are unchanged

### Requirement: Webhook endpoint is idempotent on event_id

The endpoint SHALL consult Redis key `yukassa:event:{event_id}` before dispatching. If the key exists the response is 200 with no side effects. On successful dispatch the key is written with a 24h TTL. On unhandled exception the key is NOT written (ЮKassa retries).

#### Scenario: Duplicate event_id short-circuits

- **GIVEN** `fake_redis` already holds `yukassa:event:evt-dup`
- **WHEN** a valid whitelisted POST arrives with `X-Event-Id: evt-dup`
- **THEN** the response is 200 and no Payment/Order rows change

### Requirement: payment.succeeded webhook advances Payment, Order, loyalty, cart, and notifications

A `payment.succeeded` event SHALL, atomically: set `Payment.status = SUCCEEDED`, `Order.status = PAID`, insert a `LoyaltyTransaction(type=REDEMPTION)` consuming the RESERVATION, delete the Redis key `cart:{user_id}`, and insert two `Notification` rows (channels `SMS` and `IN_APP`) whose `message_ru` contains `"Заказ оплачен"`. The response MUST be 200.

#### Scenario: Happy path payment.succeeded

- **GIVEN** Payment in `AWAITING_CONFIRMATION` tied to `yukassa_payment_id == "pay_xyz"`, Order in `CREATED`, RESERVATION loyalty row, and Redis cart key `cart:{user_id}`
- **WHEN** a whitelisted POST arrives with `{"event": "payment.succeeded", "object": {"id": "pay_xyz"}}` and a fresh `X-Event-Id`
- **THEN** 200, `Payment.status == SUCCEEDED`, `Order.status == PAID`, at least one `LoyaltyTransaction` of type `REDEMPTION` exists for that order, Redis `cart:{user_id}` is gone, and two `Notification` rows (SMS + IN_APP) exist with `"Заказ оплачен"` in `message_ru`

### Requirement: payment.canceled webhook cancels Order and unreserves

A `payment.canceled` event SHALL run the same atomic compensation as `_fail_payment_and_cancel_order` and additionally insert a `Notification(channel=IN_APP)` whose `message_ru` contains `"Платёж не прошёл"`.

#### Scenario: Happy path payment.canceled

- **GIVEN** Payment in `AWAITING_CONFIRMATION`, Order in `CREATED` with `points_used = 50`, Promocode with `current_uses = 1`
- **WHEN** a whitelisted POST arrives with `{"event": "payment.canceled", "object": {"id": "pay_xyz"}}`
- **THEN** 200, `Payment.status == PAYMENT_FAILED`, `Order.status == CANCELLED`, a `LoyaltyTransaction(type=REVERSAL, amount=50)` exists, `Promocode.current_uses == 0`, and at least one `IN_APP` notification contains `"Платёж не прошёл"`

### Requirement: refund.succeeded webhook marks Payment refunded

A `refund.succeeded` event SHALL set `Payment.status = REFUNDED`.

#### Scenario: Refund success

- **GIVEN** Payment in `REFUND_PENDING`
- **WHEN** a whitelisted POST arrives with `{"event": "refund.succeeded", "object": {"payment_id": "pay_xyz"}}`
- **THEN** 200 and `Payment.status == REFUNDED`

### Requirement: refund.canceled webhook marks refund failed and notifies admin

A `refund.canceled` event SHALL set `Payment.status = REFUND_FAILED` and insert at least one `Notification` row for the owning Order (admin-destined).

#### Scenario: Refund failure persists and notifies

- **GIVEN** Payment in `REFUND_PENDING`
- **WHEN** a whitelisted POST arrives with `{"event": "refund.canceled", "object": {"payment_id": "pay_xyz"}}`
- **THEN** 200, `Payment.status == REFUND_FAILED`, and at least one `Notification` row exists for the Order

### Requirement: Unknown webhook event types are acknowledged without mutation

Unknown `event` values MUST return 200 with no DB or Redis mutation.

#### Scenario: Unknown event no-ops

- **WHEN** a whitelisted POST arrives with `{"event": "payment.waiting_for_capture", "object": {"id": "pay_xyz"}}`
- **THEN** 200, Payment and Order rows unchanged

### Requirement: Webhook surfaces handler exceptions as 5xx and leaves event unprocessed

If the dispatcher raises an unhandled exception, the endpoint MUST NOT return 2xx and MUST NOT write the idempotency key. ЮKassa will retry.

#### Scenario: Dispatcher crash does not mark event processed

- **GIVEN** `dispatch_event` monkey-patched to raise `RuntimeError`
- **WHEN** a valid whitelisted POST arrives with `X-Event-Id: evt-crash`
- **THEN** the response is ≥ 500 (FastAPI re-raises under TestClient default) AND `fake_redis.get("yukassa:event:evt-crash") is None`
