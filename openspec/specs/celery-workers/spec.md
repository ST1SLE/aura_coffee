## ADDED Requirements

### Requirement: Payment worker Celery app
`services/payment-worker/` SHALL contain a Celery application instance accessible as `payment_worker.main:celery_app`. It SHALL use Redis as the message broker, configured via `REDIS_URL` environment variable (INV-015). The app SHALL consume exclusively from a dedicated `payments` queue by setting `task_queues = [Queue("payments")]` and `task_default_queue = "payments"`.

#### Scenario: Start payment worker
- **WHEN** Celery starts with `celery -A payment_worker.main:celery_app worker`
- **THEN** the worker connects to Redis and consumes tasks only from the `payments` queue

#### Scenario: Payment worker ignores SMS tasks
- **WHEN** an SMS task is published to the `sms` queue
- **THEN** the payment-worker SHALL NOT consume it

### Requirement: SMS worker Celery app
`services/sms-worker/` SHALL contain a Celery application instance accessible as `sms_worker.main:celery_app`. It SHALL use Redis as the message broker, configured via `REDIS_URL` environment variable (INV-015). The app SHALL discover tasks via `celery_app.autodiscover_tasks(["sms_worker.tasks"])`, scanning all modules within the `sms_worker.tasks` package. The app SHALL consume exclusively from a dedicated `sms` queue by setting `task_queues = [Queue("sms")]` and `task_default_queue = "sms"`. No `tasks.py` file SHALL exist alongside the `tasks/` directory.

#### Scenario: Start SMS worker
- **WHEN** Celery starts with `celery -A sms_worker.main:celery_app worker`
- **THEN** the worker connects to Redis and consumes tasks only from the `sms` queue

#### Scenario: SMS worker ignores default queue
- **WHEN** a task is published to the default `celery` queue
- **THEN** the sms-worker SHALL NOT consume it

#### Scenario: No namespace collision
- **WHEN** the sms_worker module is imported
- **THEN** there SHALL NOT be both a `tasks.py` file and a `tasks/` directory under `sms_worker/`

### Requirement: Health check tasks
Each Celery worker SHALL register a `health_check` task that returns the string `"ok"`. This task SHALL be callable from any service that imports the worker's task module. For the sms-worker, the `health_check` task SHALL be defined in `sms_worker/tasks/__init__.py`.

#### Scenario: Payment worker health check
- **WHEN** `payment_worker.tasks.health_check.delay()` is called
- **THEN** the task executes and returns `"ok"`

#### Scenario: SMS worker health check
- **WHEN** `sms_worker.tasks.health_check.delay()` is called
- **THEN** the task executes and returns `"ok"`

### Requirement: Worker settings via pydantic-settings
Each worker SHALL load configuration from environment variables via `pydantic-settings` `BaseSettings`. Required settings: `REDIS_URL`. No secrets SHALL be hardcoded (INV-015).

#### Scenario: Worker starts with valid config
- **WHEN** `REDIS_URL` is set to a valid Redis connection string
- **THEN** the Celery app initializes and connects to Redis without errors

### Requirement: Core-API routes tasks to named queues
When core-api publishes Celery tasks via `send_task()`, it SHALL specify the target queue explicitly. SMS tasks SHALL be routed to the `sms` queue. Payment tasks SHALL be routed to the `payments` queue.

#### Scenario: OTP task routed to SMS queue
- **WHEN** core-api calls `send_task("sms_worker.tasks.otp.send_otp_sms", ...)`
- **THEN** the task message SHALL be published to the `sms` queue (`queue="sms"`)

#### Scenario: Payment task routed to payments queue
- **WHEN** core-api calls `send_task()` for a payment worker task
- **THEN** the task message SHALL be published to the `payments` queue (`queue="payments"`)

### MODIFIED: SMS delivery with dev-mode bypass
- **Previously:** `send_sms()` always calls SMS.ru API; fails silently if API key is invalid
- **Now:** `send_sms()` checks `smsru_api_key` first; if empty, logs phone + message at WARNING level with "DEV" prefix and returns `True` without HTTP call
