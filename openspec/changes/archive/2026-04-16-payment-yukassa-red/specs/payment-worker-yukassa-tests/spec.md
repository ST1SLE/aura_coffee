## ADDED Requirements

<!-- All requirements below reference PDD §4.2 (Payment Worker architecture), §6.2 (Payment Lifecycle), §7.9 (Webhook Processing Chain), §8.1 (YuKassa compliance), and INV-001, INV-004, INV-015. -->

### Requirement: Payment Worker settings expose YuKassa and infrastructure environment

The Payment Worker `Settings` class SHALL load five new environment variables: `YUKASSA_SHOP_ID`, `YUKASSA_SECRET_KEY`, `YUKASSA_WEBHOOK_IPS` (comma-separated list), `YUKASSA_BASE_URL` (defaults to the ЮKassa test endpoint), and `DATABASE_URL`. The existing `REDIS_URL` MUST remain available. Secrets MUST be read from the environment only (INV-015).

#### Scenario: All fields load from the environment

- **WHEN** `YUKASSA_SHOP_ID=123`, `YUKASSA_SECRET_KEY=test_key`, `YUKASSA_WEBHOOK_IPS=185.71.76.0/27,185.71.77.0/27`, `DATABASE_URL=postgresql://x/y`, and `REDIS_URL=redis://r:6379/0` are set in the environment
- **THEN** instantiating `Settings()` exposes `.yukassa_shop_id == "123"`, `.yukassa_secret_key == "test_key"`, `.yukassa_webhook_ips` contains the two CIDR strings, `.database_url == "postgresql://x/y"`, and `.redis_url == "redis://r:6379/0"`

#### Scenario: Base URL defaults to the ЮKassa test endpoint

- **WHEN** `YUKASSA_BASE_URL` is NOT set in the environment
- **THEN** `Settings().yukassa_base_url` equals `"https://api.yookassa.ru/v3"` (official base)

### Requirement: YukassaClient wraps the ЮKassa REST API

A `YukassaClient` class SHALL expose three methods — `create_payment`, `get_payment`, `create_refund` — that call the YuKassa REST API over HTTP Basic auth (`shopId:secretKey`), send amounts as strings with two decimal places (e.g. `"123.45"` from `12345` kopecks), and attach an `Idempotency-Key` header on every create request (PDD §8.1). Network timeouts MUST be 10s connect / 30s read.

#### Scenario: create_payment hits POST /v3/payments with HTTP Basic and idempotency key

- **WHEN** a test calls `YukassaClient(...).create_payment(amount_kopecks=12345, idempotency_key="uuid-1", return_url="https://shop/return", description="Order #42")`
- **THEN** exactly one HTTP request is issued to `POST {base_url}/payments`, the JSON body contains `amount.value == "123.45"` and `amount.currency == "RUB"`, the `Authorization` header is HTTP Basic of `shop_id:secret_key`, and the `Idempotency-Key` header equals `"uuid-1"`

#### Scenario: get_payment hits GET /v3/payments/{id}

- **WHEN** `YukassaClient(...).get_payment("pay_abc")` is called
- **THEN** the request is `GET {base_url}/payments/pay_abc` with HTTP Basic auth and NO `Idempotency-Key` header

#### Scenario: create_refund posts full-amount refund with idempotency key

- **WHEN** `YukassaClient(...).create_refund(payment_id="pay_abc", amount_kopecks=12345, idempotency_key="uuid-2")` is called
- **THEN** exactly one `POST {base_url}/refunds` is issued, the JSON body includes `payment_id == "pay_abc"` and `amount.value == "123.45"`, and `Idempotency-Key == "uuid-2"`

#### Scenario: Timeouts configured to 10/30 seconds

- **WHEN** the client sends any request
- **THEN** the underlying `httpx.Client` is configured with a timeout whose `connect == 10.0` and `read == 30.0`

### Requirement: create_payment Celery task persists success state

The `create_payment` Celery task SHALL, on a successful ЮKassa response, update the `Payment` row to `status = AWAITING_CONFIRMATION`, set `yukassa_payment_id`, and set `confirmation_url`. The Order row MUST remain in `CREATED` until a webhook advances it (PDD §6.1, §6.2).

#### Scenario: Happy path updates Payment row

- **WHEN** the task runs with a fake YukassaClient whose `create_payment` returns `{"id": "pay_xyz", "confirmation_url": "https://yoo/confirm", "status": "pending"}`
- **THEN** after the task returns, the `Payment` row has `yukassa_payment_id == "pay_xyz"`, `confirmation_url == "https://yoo/confirm"`, and `status == PaymentStatus.AWAITING_CONFIRMATION`, and the `Order` row is still `OrderStatus.CREATED`

### Requirement: create_payment Celery task is retried on transient httpx failures

The `create_payment` task SHALL be configured to auto-retry on `httpx.HTTPError` / `httpx.RequestError`, with `max_retries=3` and exponential backoff.

#### Scenario: Task decorator exposes retry policy

- **WHEN** introspecting the `create_payment` task
- **THEN** `create_payment.max_retries == 3`, `create_payment.autoretry_for` includes `httpx.RequestError`, and `create_payment.retry_backoff` is truthy

### Requirement: create_payment task compensates on exhausted retries

When the ЮKassa API call fails after 3 retries, the task MUST, atomically (INV-004), set `Payment.status = PAYMENT_FAILED`, set `Order.status = CANCELLED`, insert a `LoyaltyTransaction` of type `REVERSAL` for any previously reserved points, and decrement `Promocode.current_uses` by 1 if a promocode was applied to the order.

#### Scenario: Exhausted retries cancel the order and unreserve loyalty + promo

- **GIVEN** an Order with `points_used == 100`, `promocode_id` referencing a Promocode with `current_uses == 1`
- **WHEN** the task's compensation path runs (simulated by calling the compensation helper directly with the seeded DB session)
- **THEN** the `Payment` row is `PaymentStatus.PAYMENT_FAILED`, the `Order` row is `OrderStatus.CANCELLED`, a `LoyaltyTransaction` with `type == LoyaltyTransactionType.REVERSAL` and `amount == +100` exists, and the `Promocode.current_uses == 0`

### Requirement: initiate_refund Celery task marks refund pending on success, swallows failure

The `initiate_refund` task SHALL call `YukassaClient.create_refund`, and on a 2xx response set the Payment row to `status = REFUND_PENDING`. On any exception the task MUST log and return without mutating the Payment status (admin handles manually).

#### Scenario: Successful refund call flips Payment to REFUND_PENDING

- **GIVEN** a Payment row with `status = SUCCEEDED`
- **WHEN** `initiate_refund.run(payment_id, amount_kopecks)` runs against a fake client that returns a successful refund response
- **THEN** the Payment row is `PaymentStatus.REFUND_PENDING`

#### Scenario: Failed refund call leaves Payment unchanged

- **GIVEN** a Payment row with `status = SUCCEEDED`
- **WHEN** `initiate_refund.run(payment_id, amount_kopecks)` runs against a fake client that raises `httpx.RequestError`
- **THEN** the Payment row remains `PaymentStatus.SUCCEEDED`, the task does not raise, and the failure is logged

### Requirement: Webhook endpoint rejects unknown source IPs

`POST /webhooks/yukassa` SHALL return HTTP 403 and write a security log when the caller IP is not in `YUKASSA_WEBHOOK_IPS`. No DB or Redis mutation may occur for rejected requests (PDD §4.2, §7.9 step 1).

#### Scenario: Request from outside the whitelist is rejected

- **GIVEN** `YUKASSA_WEBHOOK_IPS=185.71.76.1,185.71.76.2` and a valid `payment.succeeded` JSON body
- **WHEN** a POST arrives from `203.0.113.9`
- **THEN** the response is HTTP 403 and no Payment/Order row mutations occur

### Requirement: Webhook endpoint is idempotent on event_id

The endpoint SHALL check `event_id` against the idempotency store before dispatching. Already-processed events MUST return HTTP 200 without side effects (PDD §7.9 step 2).

#### Scenario: Duplicate event_id returns 200 with no mutation

- **GIVEN** `event_id="evt-123"` already marked processed
- **WHEN** a new POST arrives with the same `event_id` and a valid whitelisted IP
- **THEN** the response is HTTP 200 and no Payment/Order row mutations occur

### Requirement: payment.succeeded webhook advances Payment and Order

A `payment.succeeded` webhook SHALL, atomically (INV-004), set Payment → `SUCCEEDED`, Order → `PAID`, convert the reserved loyalty row to a REDEMPTION, mark the promocode usage as confirmed, delete the cart from Redis (`cart:{user_id}`), and enqueue both a `sms` and `in_app` notification ("Заказ оплачен"). The response MUST be HTTP 200.

#### Scenario: payment.succeeded happy path

- **GIVEN** a Payment in `AWAITING_CONFIRMATION` for Order in `CREATED`, a RESERVATION loyalty row for 100 pts, and a Redis cart key `cart:{user_id}`
- **WHEN** a whitelisted webhook arrives with `{"event": "payment.succeeded", "object": {"id": "<yukassa_payment_id>"}}` and a fresh `event_id`
- **THEN** response is 200, Payment is `SUCCEEDED`, Order is `PAID`, the reserved loyalty row's type is `REDEMPTION` (or an offsetting pair exists), the Redis `cart:{user_id}` key is removed, and a notification row of each channel (`sms`, `in_app`) with body containing `"Заказ оплачен"` is queued

### Requirement: payment.canceled webhook cancels Order and releases reservations

A `payment.canceled` webhook SHALL set Payment → `PAYMENT_FAILED`, Order → `CANCELLED`, insert a `LoyaltyTransaction(type=REVERSAL)` for the reserved points, decrement `Promocode.current_uses` by 1 if a promocode was applied, and enqueue an in-app notification ("Платёж не прошёл"). The response MUST be HTTP 200.

#### Scenario: payment.canceled happy path

- **GIVEN** a Payment in `AWAITING_CONFIRMATION`, Order in `CREATED` with `points_used == 50` and a promocode whose `current_uses == 1`
- **WHEN** a whitelisted webhook arrives with `{"event": "payment.canceled", ...}`
- **THEN** response is 200, Payment is `PAYMENT_FAILED`, Order is `CANCELLED`, a REVERSAL loyalty row with `amount == +50` exists, `Promocode.current_uses == 0`, and an `in_app` notification contains "Платёж не прошёл"

### Requirement: refund.succeeded webhook marks Payment refunded

A `refund.succeeded` webhook SHALL set Payment → `REFUNDED` and return HTTP 200.

#### Scenario: refund.succeeded flips Payment to REFUNDED

- **GIVEN** a Payment in `REFUND_PENDING`
- **WHEN** a whitelisted webhook arrives with `{"event": "refund.succeeded", ...}`
- **THEN** response is 200 and Payment is `PaymentStatus.REFUNDED`

### Requirement: refund.canceled webhook marks Payment refund_failed

A `refund.canceled` webhook SHALL set Payment → `REFUND_FAILED`, log the error, and enqueue an admin notification. The response MUST be HTTP 200.

#### Scenario: refund.canceled flips Payment to REFUND_FAILED and notifies admin

- **GIVEN** a Payment in `REFUND_PENDING`
- **WHEN** a whitelisted webhook arrives with `{"event": "refund.canceled", ...}`
- **THEN** response is 200, Payment is `PaymentStatus.REFUND_FAILED`, and an admin notification is enqueued

### Requirement: Unknown webhook event type is acknowledged without side effects

Unknown `event` values MUST be logged and the endpoint MUST return HTTP 200 with no DB mutations (PDD §7.9 step 3).

#### Scenario: Unknown event returns 200 with no mutation

- **WHEN** a whitelisted webhook arrives with `{"event": "payment.waiting_for_capture", ...}`
- **THEN** response is 200 and no Payment/Order row mutations occur

### Requirement: Webhook surface propagates processing errors as 500

If the handler raises an unexpected exception during event dispatch, the endpoint MUST NOT return 200 — it MUST surface a 5xx so that ЮKassa retries (PDD §7.9 step 4).

#### Scenario: Unhandled exception surfaces as 500

- **GIVEN** an event dispatcher monkey-patched to raise `RuntimeError`
- **WHEN** a valid whitelisted webhook is posted
- **THEN** the response status is ≥ 500 and the exception is visible in logs
