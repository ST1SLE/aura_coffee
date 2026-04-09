## ADDED Requirements

### Requirement: Payment worker Celery app
`services/payment-worker/` SHALL contain a Celery application instance accessible as `payment_worker.main:celery_app`. It SHALL use Redis as the message broker, configured via `REDIS_URL` environment variable (INV-015).

#### Scenario: Start payment worker
- **WHEN** Celery starts with `celery -A payment_worker.main:celery_app worker`
- **THEN** the worker connects to Redis and begins consuming tasks

### Requirement: SMS worker Celery app
`services/sms-worker/` SHALL contain a Celery application instance accessible as `sms_worker.main:celery_app`. It SHALL use Redis as the message broker, configured via `REDIS_URL` environment variable (INV-015). The app SHALL discover tasks via `celery_app.autodiscover_tasks(["sms_worker.tasks"])`, scanning all modules within the `sms_worker.tasks` package. No `tasks.py` file SHALL exist alongside the `tasks/` directory.

#### Scenario: Start SMS worker
- **WHEN** Celery starts with `celery -A sms_worker.main:celery_app worker`
- **THEN** the worker connects to Redis and discovers all tasks in the `sms_worker.tasks` package (including submodules)

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
