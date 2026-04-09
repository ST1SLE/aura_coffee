## 1. Root Configuration

- [x] 1.1 [shared] Create root `pyproject.toml` with ruff configuration (lint + format rules)
- [x] 1.2 [shared] Create `.env.example` with all required environment variables and safe defaults

## 2. Shared Package

- [x] 2.1 [shared] Create `packages/shared/pyproject.toml` with PEP 621 metadata and dependencies (pydantic, sqlalchemy)
- [x] 2.2 [shared] Create `packages/shared/src/shared/__init__.py` with `__version__` export
- [x] 2.3 [shared] Create `packages/shared/src/shared/models/__init__.py` with SQLAlchemy `Base` declarative base

## 3. Database / Alembic

- [x] 3.1 [database] Create `database/alembic.ini` configured to read `DATABASE_URL` from env
- [x] 3.2 [database] Create `database/migrations/env.py` importing models from `shared` for autogenerate
- [x] 3.3 [database] Create `database/migrations/script.py.mako` template
- [x] 3.4 [database] Create initial empty migration as base revision via `alembic revision`

## 4. Core API

- [x] 4.1 [core-api] Create `services/core-api/pyproject.toml` with dependencies (fastapi, uvicorn, sqlalchemy, pydantic-settings, shared)
- [x] 4.2 [core-api] Create `services/core-api/src/core_api/settings.py` with `Settings(BaseSettings)` class
- [x] 4.3 [core-api] Create `services/core-api/src/core_api/database.py` with sessionmaker and `get_db` dependency
- [x] 4.4 [core-api] Create `services/core-api/src/core_api/main.py` with FastAPI app, CORS middleware, health endpoint
- [x] 4.5 [core-api] Create `services/core-api/tests/conftest.py` with httpx `AsyncClient` test fixture
- [x] 4.6 [core-api] Create `services/core-api/tests/test_health.py` with health endpoint test

## 5. Payment Worker

- [x] 5.1 [payment-worker] Create `services/payment-worker/pyproject.toml` with dependencies (celery, redis, pydantic-settings, shared)
- [x] 5.2 [payment-worker] Create `services/payment-worker/src/payment_worker/settings.py` with `Settings(BaseSettings)` class
- [x] 5.3 [payment-worker] Create `services/payment-worker/src/payment_worker/main.py` with Celery app instance
- [x] 5.4 [payment-worker] Create `services/payment-worker/src/payment_worker/tasks.py` with `health_check` task

## 6. SMS Worker

- [x] 6.1 [sms-worker] Create `services/sms-worker/pyproject.toml` with dependencies (celery, redis, pydantic-settings, shared)
- [x] 6.2 [sms-worker] Create `services/sms-worker/src/sms_worker/settings.py` with `Settings(BaseSettings)` class
- [x] 6.3 [sms-worker] Create `services/sms-worker/src/sms_worker/main.py` with Celery app instance
- [x] 6.4 [sms-worker] Create `services/sms-worker/src/sms_worker/tasks.py` with `health_check` task

## 7. Docker

- [x] 7.1 [core-api] Create `services/core-api/Dockerfile`
- [x] 7.2 [payment-worker] Create `services/payment-worker/Dockerfile`
- [x] 7.3 [sms-worker] Create `services/sms-worker/Dockerfile`
- [x] 7.4 [database] Create `docker-compose.yml` with postgres, redis, core-api, payment-worker, sms-worker services

## 8. Verification

- [x] 8.1 [shared] Run `ruff check .` and `ruff format --check .` — zero violations
- [x] 8.2 [core-api] Run `pytest` in core-api — all tests pass (verified imports; full test requires SSL-enabled Python)
- [x] 8.3 [database] Run `docker compose up` — all services reach healthy state
