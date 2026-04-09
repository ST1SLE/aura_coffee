## Context

The Aura Coffee monorepo has the directory structure in place but contains only `.gitkeep` placeholders. No Python packages, no configurations, no runnable services exist. This change bootstraps all backend infrastructure so that Phase 1 (Auth) can begin immediately after.

**Affected modules:** [shared], [database], [core-api], [payment-worker], [sms-worker], [redis]

**Current state:** Empty directories with `.gitkeep` files.

## Goals / Non-Goals

**Goals:**
- All backend services SHALL be runnable locally via `docker compose up`
- Python packages SHALL be installable with standard tooling (`pip install -e .`)
- Database migrations SHALL be executable via Alembic CLI
- Test suite SHALL run with `pytest` and produce a passing result
- Developer onboarding SHALL require only: clone → `cp .env.example .env` → `docker compose up`

**Non-Goals:**
- No business logic, domain models, or real endpoints beyond health checks
- No CI/CD, production deployment, or Nginx configuration
- No frontend tooling — handled by `project-init-frontend`
- No external API integrations (YuKassa, SMS.ru, Yandex.Maps)

## Decisions

### D1: Package manager — pip + pyproject.toml (PEP 621)

Each Python module (`shared`, `core-api`, `payment-worker`, `sms-worker`) SHALL use `pyproject.toml` with standard PEP 621 metadata. No Poetry, no PDM — plain pip with `pip install -e ".[dev]"` for development.

**Why over Poetry/PDM:** Fewer moving parts, no lock file conflicts across services, Docker builds are simpler with plain pip. The project is small enough that advanced dependency resolution isn't needed.

### D2: Shared package — local editable install

`packages/shared/` SHALL be a standalone Python package installed as an editable dependency in all backend services via `pip install -e ../../../packages/shared`. In Docker, it SHALL be copied and installed as a regular package.

**Why over monorepo tool (pants/nx):** Overkill for 4 Python packages. Editable installs are sufficient and zero-config.

### D3: SQLAlchemy 2.0 sync with sessionmaker

`core-api` SHALL use synchronous SQLAlchemy 2.0 with `sessionmaker` and FastAPI's `Depends()` for session injection. No async — Celery workers are sync, and keeping one paradigm reduces complexity.

**Why sync over async:** Celery is inherently synchronous. Using sync SQLAlchemy everywhere avoids two session patterns. FastAPI handles sync endpoints fine via threadpool.

### D4: Alembic — standalone in database/

Alembic SHALL live in `database/` with its own `alembic.ini`. It SHALL import models from `shared` for autogenerate support. The `env.py` SHALL read `DATABASE_URL` from environment (INV-015).

**Why standalone over per-service:** One migration timeline, one source of truth for schema. All services share the same database.

### D5: Celery workers — minimal scaffold with Redis broker

Both `payment-worker` and `sms-worker` SHALL be Celery apps with Redis as broker (configured via `REDIS_URL` env var). Each SHALL have a single `health_check` task that returns `"ok"`. No result backend — tasks are fire-and-forget at this stage.

**Why no result backend:** Not needed for Phase 0. Payment and SMS workers will use database state for tracking, not Celery results.

### D6: Docker Compose — dev-only, all services

`docker-compose.yml` SHALL define: `postgres` (16-alpine), `redis` (7-alpine), `core-api`, `payment-worker`, `sms-worker`. Services SHALL use volume mounts for live reload. PostgreSQL SHALL use named volume for persistence.

**Why no production compose:** Production deployment strategy is out of scope. Dev compose is the only deliverable.

### D7: Settings — pydantic-settings with .env

Each service SHALL use `pydantic-settings` `BaseSettings` to load configuration from environment variables (INV-015). A `.env.example` SHALL document all required variables with safe defaults for local development.

### D8: Linting and formatting — ruff

All Python code SHALL use `ruff` for linting and formatting. A root-level `pyproject.toml` SHALL configure ruff with a shared rule set. No black, no isort, no flake8 — ruff replaces all three.

**Why ruff:** Single tool, fast, covers linting + formatting + import sorting. Reduces dev dependency count.

## Risks / Trade-offs

- **[Risk] Sync SQLAlchemy limits core-api throughput** → Acceptable for a single coffee shop. If needed later, FastAPI can mix sync and async endpoints. Migration to async is incremental.
- **[Risk] No lock files means non-reproducible builds** → Mitigated by pinning major versions in `pyproject.toml`. For production, we SHALL add `pip-compile` or similar before deployment.
- **[Risk] Editable installs break in Docker if paths change** → Mitigated by using `COPY` + regular `pip install` in Dockerfiles, not editable mode.

## Open Questions

- None — this is straightforward scaffolding with well-known tools.
