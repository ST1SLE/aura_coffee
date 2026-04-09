## MODIFIED Requirements

### Requirement: SMS worker Celery app
`services/sms-worker/` SHALL contain a Celery application instance accessible as `sms_worker.main:celery_app`. It SHALL use Redis as the message broker, configured via `REDIS_URL` environment variable (INV-015). The app SHALL discover tasks via `celery_app.autodiscover_tasks(["sms_worker.tasks"])`, scanning all modules within the `sms_worker.tasks` package.

Previously: `autodiscover_tasks(["sms_worker", "sms_worker.tasks"])` with tasks split between `tasks.py` (file) and `tasks/` (package).
Now: `autodiscover_tasks(["sms_worker.tasks"])` with all tasks inside the `tasks/` package only. No `tasks.py` file SHALL exist alongside the `tasks/` directory.

#### Scenario: Start SMS worker
- **WHEN** Celery starts with `celery -A sms_worker.main:celery_app worker`
- **THEN** the worker connects to Redis and discovers all tasks in the `sms_worker.tasks` package (including submodules)

#### Scenario: No namespace collision
- **WHEN** the sms_worker module is imported
- **THEN** there SHALL NOT be both a `tasks.py` file and a `tasks/` directory under `sms_worker/`

### Requirement: Health check tasks
Each Celery worker SHALL register a `health_check` task that returns the string `"ok"`. For the sms-worker, the `health_check` task SHALL be defined in `sms_worker/tasks/__init__.py`.

Previously: sms-worker `health_check` was in `sms_worker/tasks.py` (shadowed by `tasks/` package, unreachable).
Now: sms-worker `health_check` is in `sms_worker/tasks/__init__.py` (part of the package, always discoverable).

#### Scenario: SMS worker health check
- **WHEN** `sms_worker.tasks.health_check.delay()` is called
- **THEN** the task executes and returns `"ok"`
