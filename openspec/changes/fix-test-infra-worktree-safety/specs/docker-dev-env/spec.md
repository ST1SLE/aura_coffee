## MODIFIED Requirements

### Requirement: Service Dockerfiles
Each backend service SHALL have a `Dockerfile` that installs the `shared` package and the service's own dependencies in **editable mode** (`pip install -e`), then runs the service entry point. Editable installs are REQUIRED so that `docker-compose.yml` volume mounts on `./packages/shared/src` are honored at runtime. Non-editable installs copy source into `site-packages` and silently ignore volume mounts, causing the worker's view of shared code to diverge from core-api's.

Each backend service Dockerfile SHALL additionally define a `FROM base AS dev` stage that installs the service's `[dev]` extras (pytest and related test dependencies). The production image built without `target: dev` remains lean; the development image with `target: dev` can run the test suite without a rebuild.

Previously: `payment-worker` and `sms-worker` Dockerfiles used `pip install <path>` (non-editable) with no `dev` target. `core-api` was correct.

Now: all three Dockerfiles use `pip install -e <path>` and provide a `dev` target.

#### Scenario: Build core-api image
- **WHEN** `docker build --target base` is run on the core-api Dockerfile
- **THEN** the image builds without errors and contains a runnable FastAPI application

#### Scenario: Worker honors shared-package volume mount
- **WHEN** `docker compose build payment-worker --target dev` is run
- **AND** `docker compose run --rm payment-worker python -c "import shared; print(shared.__file__)"` is executed
- **THEN** the printed path points inside `/app/packages/shared/src`, confirming the import resolves through the volume mount and not a copied `site-packages` entry

#### Scenario: Dev target installs test dependencies
- **WHEN** `docker compose build payment-worker --target dev` is run
- **THEN** the resulting image contains `pytest` and can execute `python -m pytest --version`

### Requirement: Docker Compose stack
A `docker-compose.yml` at the repo root SHALL define services: `postgres` (PostgreSQL 16), `redis` (Redis 7), `core-api`, `payment-worker`, `sms-worker`. All services SHALL start with `docker compose up`. The core-api service SHALL mount `./database:/app/database` so that Alembic migrations can be executed inside the container.

Services that run tests (currently `core-api`; extensible to `payment-worker` and `sms-worker` when their test suites land) SHALL use `build.target: dev` and SHALL mount their `tests/` directory as a volume so that new test files are picked up without rebuilding the image.

Previously: only `core-api` used `target: dev` and mounted `tests/`. Workers had no test affordances.

Now: `payment-worker` and `sms-worker` also use `target: dev` and mount `./services/<worker>/tests:/app/services/<worker>/tests`.

#### Scenario: Worker test directory is live-mounted
- **WHEN** a developer creates a new test file under `services/payment-worker/tests/`
- **AND** runs `docker compose exec payment-worker pytest /app/services/payment-worker/tests/`
- **THEN** the new test file is discovered and executed without a container rebuild

#### Scenario: Full stack startup
- **WHEN** a developer runs `docker compose up` from the repo root
- **THEN** all services start and reach a healthy state

#### Scenario: PostgreSQL is accessible
- **WHEN** the stack is running
- **THEN** `core-api` can connect to PostgreSQL on the internal Docker network

#### Scenario: Run migrations inside container
- **WHEN** a developer runs `docker compose exec core-api sh -c "cd /app/database && alembic upgrade head"`
- **THEN** Alembic connects to PostgreSQL and applies all pending migrations

#### Scenario: Redis is accessible
- **WHEN** the stack is running
- **THEN** `payment-worker` and `sms-worker` can connect to Redis on the internal Docker network
