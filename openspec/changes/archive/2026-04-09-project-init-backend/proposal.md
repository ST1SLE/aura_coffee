## Why

The monorepo contains only `.gitkeep` placeholders — no runnable code exists yet. Before any feature work (Phase 1+) can begin, we need working project scaffolding: installable Python packages, a running FastAPI app, Celery workers, database migrations, and a Docker Compose stack that brings everything up with one command. This is Phase 0 (PDD §7.1).

## What Changes

- **[shared]** Initialize `packages/shared/` as a Python package with `pyproject.toml`, base Pydantic models, and shared enums/constants skeleton
- **[database]** Initialize Alembic inside `database/`, configure it against PostgreSQL, create initial empty migration
- **[core-api]** Scaffold `services/core-api/` as a FastAPI application: entry point, health-check endpoint, CORS config, settings via env vars (INV-015), SQLAlchemy 2.0 session setup
- **[payment-worker]** Scaffold `services/payment-worker/` as a Celery application: entry point, Redis broker config, health-check task
- **[sms-worker]** Scaffold `services/sms-worker/` as a Celery application: entry point, Redis broker config, health-check task
- **[infra]** Docker Compose with PostgreSQL 16, Redis 7, core-api, payment-worker, sms-worker services; `.env.example` with all required variables
- **[dev]** Basic pytest setup for core-api with httpx test client; `scripts/` dev utilities (lint, format)

## Non-Goals

- No business logic, domain endpoints, or real database tables — this is scaffolding only
- No frontend work — that's `project-init-frontend` (Terminal B)
- No CI/CD pipeline — will be added when deployment is scoped
- No Nginx config — not needed until frontend exists

## MVP Phase

Phase 0: Project Initialization

## Capabilities

### New Capabilities
- `backend-scaffold`: Python package structure, dependency management, shared package, dev tooling (linting, formatting, pytest)
- `fastapi-app`: FastAPI application skeleton with health check, CORS, settings, SQLAlchemy session factory
- `celery-workers`: Celery worker scaffolds for payment-worker and sms-worker with Redis broker
- `database-setup`: Alembic migrations infrastructure, PostgreSQL connection, initial migration
- `docker-dev-env`: Docker Compose stack for local development (PostgreSQL, Redis, all backend services)

### Modified Capabilities
<!-- None — this is the first change, no existing specs -->

## Impact

- **Code:** All backend directories (`packages/shared/`, `services/core-api/`, `services/payment-worker/`, `services/sms-worker/`, `database/`) gain real Python packages replacing `.gitkeep` files
- **Dependencies:** Python 3.12+, FastAPI, SQLAlchemy 2.0, Celery, Redis, Alembic, Pydantic v2, pytest, httpx
- **Infrastructure:** Docker Compose becomes the primary dev environment entry point
- **APIs:** Single `GET /health` endpoint on core-api (no auth required)
