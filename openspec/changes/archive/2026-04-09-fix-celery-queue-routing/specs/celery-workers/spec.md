## MODIFIED Requirements

### Requirement: SMS worker Celery app
`services/sms-worker/` SHALL contain a Celery application instance accessible as `sms_worker.main:celery_app`. It SHALL use Redis as the message broker, configured via `REDIS_URL` environment variable (INV-015). The app SHALL discover tasks via `celery_app.autodiscover_tasks(["sms_worker.tasks"])`. The app SHALL consume exclusively from a dedicated `sms` queue by setting `task_queues = [Queue("sms")]` and `task_default_queue = "sms"`. No `tasks.py` file SHALL exist alongside the `tasks/` directory.

- **Previously:** Worker consumed from the default `celery` queue (implicit Celery default).
- **Now:** Worker SHALL consume exclusively from the `sms` queue.

#### Scenario: Start SMS worker
- **WHEN** Celery starts with `celery -A sms_worker.main:celery_app worker`
- **THEN** the worker connects to Redis and consumes tasks only from the `sms` queue

#### Scenario: SMS worker ignores default queue
- **WHEN** a task is published to the default `celery` queue
- **THEN** the sms-worker SHALL NOT consume it

### Requirement: Payment worker Celery app
`services/payment-worker/` SHALL contain a Celery application instance accessible as `payment_worker.main:celery_app`. It SHALL use Redis as the message broker, configured via `REDIS_URL` environment variable (INV-015). The app SHALL consume exclusively from a dedicated `payments` queue by setting `task_queues = [Queue("payments")]` and `task_default_queue = "payments"`.

- **Previously:** Worker consumed from the default `celery` queue (implicit Celery default).
- **Now:** Worker SHALL consume exclusively from the `payments` queue.

#### Scenario: Start payment worker
- **WHEN** Celery starts with `celery -A payment_worker.main:celery_app worker`
- **THEN** the worker connects to Redis and consumes tasks only from the `payments` queue

#### Scenario: Payment worker ignores SMS tasks
- **WHEN** an SMS task is published to the `sms` queue
- **THEN** the payment-worker SHALL NOT consume it

## ADDED Requirements

### Requirement: Core-API routes tasks to named queues
When core-api publishes Celery tasks via `send_task()`, it SHALL specify the target queue explicitly. SMS tasks SHALL be routed to the `sms` queue. Payment tasks SHALL be routed to the `payments` queue.

#### Scenario: OTP task routed to SMS queue
- **WHEN** core-api calls `send_task("sms_worker.tasks.otp.send_otp_sms", ...)`
- **THEN** the task message SHALL be published to the `sms` queue (`queue="sms"`)

#### Scenario: Payment task routed to payments queue
- **WHEN** core-api calls `send_task()` for a payment worker task
- **THEN** the task message SHALL be published to the `payments` queue (`queue="payments"`)
