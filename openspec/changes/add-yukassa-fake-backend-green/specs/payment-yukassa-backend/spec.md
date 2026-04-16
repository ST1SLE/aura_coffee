## ADDED Requirements

### Requirement: Fake callback task non-retrying contract

The Celery task that posts the self-driven webhook (registered name `yukassa_fake_callback`) SHALL be `max_retries=0` and SHALL log HTTP failures without re-raising. This keeps test failures loud (asserted by pytest on the side that matters — the webhook handler) and prevents silent retry storms during development.

#### Scenario: Webhook POST failure does not re-raise
- **WHEN** `yukassa_fake_callback` is invoked and its `httpx.post` raises `httpx.ConnectError`
- **THEN** the task logs the error at WARNING level and returns `None`; no Celery retry is scheduled

#### Scenario: Webhook POST non-2xx does not re-raise
- **WHEN** the webhook responds with HTTP 403 or 500
- **THEN** the callback task logs and returns; the caller sees no exception

### Requirement: Core-api health reports yukassa backend without coupling

The core-api `/health` endpoint SHALL include `yukassa_backend` read directly from the `YUKASSA_BACKEND` environment variable (default `"live"`), without importing any symbol from `payment_worker`. This preserves core-api's independence from payment-worker's Python package graph.

#### Scenario: core-api health has no payment_worker import
- **WHEN** core-api starts
- **THEN** `sys.modules` contains no entry under `payment_worker` after `core_api.main` is imported

#### Scenario: Health value tracks env var
- **WHEN** `YUKASSA_BACKEND=fake` is exported before core-api starts
- **THEN** `GET /health` returns JSON where `yukassa_backend == "fake"`
