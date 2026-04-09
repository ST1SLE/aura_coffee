## ADDED Requirements

### Requirement: Docker Compose stack
A `docker-compose.yml` at the repo root SHALL define services: `postgres` (PostgreSQL 16), `redis` (Redis 7), `core-api`, `payment-worker`, `sms-worker`. All services SHALL start with `docker compose up`. The core-api service SHALL mount `./database:/app/database` so that Alembic migrations can be executed inside the container.

#### Scenario: Full stack startup
- **WHEN** a developer runs `docker compose up` from the repo root
- **THEN** all 5 services start and reach a healthy state

#### Scenario: PostgreSQL is accessible
- **WHEN** the stack is running
- **THEN** `core-api` can connect to PostgreSQL on the internal Docker network

#### Scenario: Run migrations inside container
- **WHEN** a developer runs `docker compose exec core-api sh -c "cd /app/database && alembic upgrade head"`
- **THEN** Alembic connects to PostgreSQL and applies all pending migrations

#### Scenario: Redis is accessible
- **WHEN** the stack is running
- **THEN** `payment-worker` and `sms-worker` can connect to Redis on the internal Docker network

### Requirement: Persistent PostgreSQL data
PostgreSQL SHALL use a named Docker volume for data persistence. Stopping and restarting the stack SHALL NOT lose database data.

#### Scenario: Data survives restart
- **WHEN** a developer runs `docker compose down` followed by `docker compose up`
- **THEN** previously created database tables and data are still present

### Requirement: Environment configuration
A `.env.example` file SHALL document all required environment variables with safe local-development defaults. `docker-compose.yml` SHALL reference `.env` for variable substitution.

#### Scenario: Copy and run
- **WHEN** a developer copies `.env.example` to `.env` without modifications
- **THEN** `docker compose up` starts all services with working defaults

### Requirement: Live reload for development
Backend services in Docker Compose SHALL mount source code as volumes so that code changes are reflected without rebuilding containers. `core-api` SHALL use uvicorn's `--reload` flag.

#### Scenario: Code change triggers reload
- **WHEN** a developer edits a Python file in `services/core-api/src/`
- **THEN** uvicorn detects the change and restarts the application automatically

### Requirement: Service Dockerfiles
Each backend service SHALL have a `Dockerfile` that installs the `shared` package and the service's own dependencies, then runs the service entry point.

#### Scenario: Build core-api image
- **WHEN** `docker build` is run on the core-api Dockerfile
- **THEN** the image builds without errors and contains a runnable FastAPI application
