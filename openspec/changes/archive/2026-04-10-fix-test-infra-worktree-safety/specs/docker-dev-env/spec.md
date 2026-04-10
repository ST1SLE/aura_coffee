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

## ADDED Requirements

### Requirement: Parameterized host ports for multi-worktree coexistence
Every host port binding in `docker-compose.yml` SHALL be declared as `${VAR:-default}` so that each git worktree running the stack can override it via its own `.env` without editing shared files. The six variables SHALL be `POSTGRES_PORT`, `REDIS_PORT`, `CORE_API_PORT`, `WEB_CUSTOMER_PORT`, `WEB_ADMIN_PORT`, `NGINX_PORT`. Defaults SHALL match the pre-existing hardcoded values (`5433 / 6379 / 8000 / 5173 / 5174 / 80`) so single-worktree usage is unchanged.

`.env.example` SHALL declare all six variables under a `# Host port bindings` section with an inline comment explaining the per-worktree offset convention (bump every port by the same offset).

#### Scenario: Defaults preserve single-worktree behavior
- **GIVEN** a worktree with `.env` copied verbatim from `.env.example`
- **WHEN** `docker compose up -d` is run
- **THEN** host ports bind to `5433 / 6379 / 8000 / 5173 / 5174 / 80`, matching the pre-parameterization defaults

#### Scenario: Two worktrees coexist on distinct ports
- **GIVEN** two worktrees each with their own `.env` using port offsets `+0` and `+10` respectively
- **WHEN** both run `docker compose up -d`
- **THEN** both stacks start successfully with no host port conflicts

### Requirement: Bootstrap script for per-worktree environment
The repo SHALL provide `scripts/setup-worktree-env.sh` that generates a per-worktree `.env` from `.env.example` with a collision-free host port offset. The script SHALL:

1. Derive a deterministic starting offset from `sha1sum` of the worktree path, in the range `[0, 200)` stepped by 10.
2. Probe each candidate port set (`POSTGRES_PORT`, `REDIS_PORT`, `CORE_API_PORT`, `WEB_CUSTOMER_PORT`, `WEB_ADMIN_PORT`, `NGINX_PORT` with the offset applied) against `127.0.0.1` via bash `/dev/tcp`. If any port is bound, bump offset by +10 and retry, up to 20 attempts.
3. On the first free set, write `.env` from `.env.example` with every port replaced and `CORS_ORIGINS` patched to match the chosen `WEB_CUSTOMER_PORT` and `WEB_ADMIN_PORT`.
4. Be idempotent — re-running SHALL pick a fresh offset if the current `.env` ports have since been taken by another stack.

The script SHALL refuse to run on a host marked as production, to prevent clobbering prod config with dev defaults. Production markers SHALL be any of: a `.env.production` file at repo root, `AURA_PRODUCTION_HOST=1` in the environment, or a `/etc/aura-coffee/production` marker file. The production guard SHALL be overridable only via explicit `FORCE=1`.

#### Scenario: Script picks a free offset deterministically
- **GIVEN** a worktree whose path hashes to starting offset `+N`
- **AND** no other stack is bound on any of the six ports at offset `+N`
- **WHEN** `./scripts/setup-worktree-env.sh` is run
- **THEN** `.env` is written with all six ports at offset `+N` and `CORS_ORIGINS` patched to match, and the same worktree path always produces the same starting offset

#### Scenario: Script skips collisions and picks the next free offset
- **GIVEN** another stack is already bound on at least one port at starting offset `+N`
- **WHEN** `./scripts/setup-worktree-env.sh` is run
- **THEN** the script detects the collision, bumps offset by +10, re-probes, and writes `.env` with the first fully-free offset it finds

#### Scenario: Production guard refuses to run
- **GIVEN** a `.env.production` file exists at repo root (or `AURA_PRODUCTION_HOST=1`, or `/etc/aura-coffee/production` exists)
- **WHEN** `./scripts/setup-worktree-env.sh` is run without `FORCE=1`
- **THEN** the script exits with status 1 and does not modify `.env`
