## MODIFIED Requirements

### Requirement: Docker Compose stack
A `docker-compose.yml` at the repo root SHALL define services: `postgres` (PostgreSQL 16), `redis` (Redis 7), `db-migrate` (one-shot), `db-seed` (one-shot), `core-api`, `payment-worker`, `sms-worker`, `web-customer`, `web-admin`, `nginx`. All services SHALL start with `docker compose up`. The `core-api` service SHALL mount `./database:/app/database` so that Alembic migrations can be executed inside the container.

The `db-migrate` service SHALL use the existing `services/core-api/Dockerfile` with `target: dev` (no separate Dockerfile), mount `./packages/shared/src`, `./services/core-api/src`, and `./database` as volumes, load `.env` via `env_file: .env`, run `sh -c "cd /app/database && alembic upgrade head"` as its command, declare `depends_on: postgres: condition: service_healthy`, and declare `restart: "no"` so a successful exit is terminal.

The `db-seed` service SHALL use the same image and volume mounts as `db-migrate`, load `.env` to pick up `ADMIN_LOGIN` and `ADMIN_PASSWORD`, run `python -m database.seeds.initial_admin` as its command, declare `depends_on: db-migrate: condition: service_completed_successfully` so it runs only after migrations have finished, and declare `restart: "no"`.

The `core-api` service SHALL declare `depends_on: db-seed: condition: service_completed_successfully` (in addition to its existing `postgres` and `redis` health dependencies), so `core-api` only starts after the schema is at `head` and the initial admin row exists.

Services that run tests (currently `core-api`; extensible to `payment-worker` and `sms-worker` when their test suites land) SHALL continue to use `build.target: dev` and SHALL mount their `tests/` directory as a volume so that new test files are picked up without rebuilding the image.

- **Previously:** The stack relied on a manual `docker compose exec core-api sh -c "cd /app/database && alembic upgrade head"` step (scenario "Run migrations inside container") to apply pending migrations, and an analogous manual `docker compose exec -e ADMIN_LOGIN=... core-api python -m database.seeds.initial_admin` to seed the initial admin. Neither step was referenced from the bring-up flow, so every branch pull that added a migration silently left the dev DB at the previous revision.
- **Now:** The stack SHALL converge the dev DB to `alembic head` automatically on every `docker compose up`, via the one-shot `db-migrate` and `db-seed` services described above. `core-api` SHALL NOT start until both one-shots have exited with code 0. No manual Alembic or seed commands are required in the normal bring-up path.

#### Scenario: Worker test directory is live-mounted
- **WHEN** a developer creates a new test file under `services/payment-worker/tests/`
- **AND** runs `docker compose exec payment-worker pytest /app/services/payment-worker/tests/`
- **THEN** the new test file is discovered and executed without a container rebuild

#### Scenario: Full stack startup applies pending migrations automatically
- **WHEN** a developer runs `docker compose up -d` from the repo root on a worktree where `alembic_version` is behind the `head` defined by `database/migrations/versions/`
- **THEN** the `db-migrate` service SHALL start after PostgreSQL is healthy, run `alembic upgrade head`, exit with code 0, and `core-api` SHALL then start with the schema at the new head

#### Scenario: Failed migration blocks core-api startup
- **GIVEN** a migration file under `database/migrations/versions/` that raises on `upgrade()`
- **WHEN** `docker compose up -d` is run
- **THEN** `db-migrate` SHALL exit with a non-zero code, `db-seed` SHALL NOT run (its `service_completed_successfully` dependency is unmet), `core-api` SHALL NOT start, and `docker compose logs db-migrate` SHALL contain the Alembic traceback

#### Scenario: PostgreSQL is accessible
- **WHEN** the stack is running
- **THEN** `core-api` can connect to PostgreSQL on the internal Docker network

#### Scenario: Initial admin is seeded automatically on first bring-up
- **GIVEN** a fresh worktree with `.env` copied from `.env.example` and no prior `staff_accounts` rows
- **WHEN** `docker compose up -d` is run
- **THEN** `db-seed` SHALL run after `db-migrate` completes and insert one `staff_accounts` row with login `admin` and the bcrypt hash of `admin123`, and the admin SPA at `http://localhost:${NGINX_PORT}/admin/` SHALL accept the `admin` / `admin123` credentials

#### Scenario: Seed is idempotent across restarts
- **GIVEN** a worktree where `db-seed` has already run once and the `staff_accounts` table contains one admin row
- **WHEN** `docker compose up -d` is run a second time
- **THEN** `db-seed` SHALL run again, the `ON CONFLICT (login) DO NOTHING` clause in `database/seeds/initial_admin.py` SHALL prevent a duplicate, the seed SHALL exit 0, and the `staff_accounts` table SHALL still contain exactly one admin row

#### Scenario: Migrations self-heal after pulling a branch with new revisions
- **GIVEN** a worktree whose `pgdata` volume is at `alembic_version = 0003` because the previous branch ended at revision `0003`
- **AND** the developer checks out a branch whose `database/migrations/versions/` directory contains `0004_menu_tables.py`
- **WHEN** the developer runs `./scripts/up.sh` or `docker compose up -d`
- **THEN** `db-migrate` SHALL apply `0004`, `alembic_version` SHALL advance to `0004`, and admin menu CRUD endpoints SHALL return 2xx on valid requests instead of `500 UndefinedTable`

#### Scenario: Redis is accessible
- **WHEN** the stack is running
- **THEN** `payment-worker` and `sms-worker` can connect to Redis on the internal Docker network

### Requirement: Environment configuration
A `.env.example` file SHALL document all required environment variables with safe local-development defaults. `docker-compose.yml` SHALL reference `.env` for variable substitution. `.env.example` SHALL additionally declare `ADMIN_LOGIN` and `ADMIN_PASSWORD` under a `# Initial admin seed (dev-only defaults)` section, with values `admin` and `admin123` respectively, and an inline comment stating that these are consumed by the `db-seed` one-shot service on `docker compose up` and MUST be overridden in any non-dev environment.

- **Previously:** `.env.example` did not declare `ADMIN_LOGIN` / `ADMIN_PASSWORD`. Devs who wanted to seed the initial admin had to pass those vars inline (`docker compose exec -e ADMIN_LOGIN=admin -e ADMIN_PASSWORD=admin123 core-api python -m database.seeds.initial_admin`), which was invisible from the bring-up flow.
- **Now:** `.env.example` SHALL declare both vars with committed dev defaults, matching the privacy posture of the existing committed `POSTGRES_PASSWORD` and `JWT_SECRET` placeholders, so `docker compose up` on a fresh worktree produces a logged-in-capable stack without manual exec commands.

#### Scenario: Copy and run
- **WHEN** a developer copies `.env.example` to `.env` without modifications
- **THEN** `docker compose up` SHALL start all services with working defaults, `db-migrate` SHALL apply migrations, `db-seed` SHALL insert the `admin`/`admin123` admin row, and `core-api` SHALL become reachable

#### Scenario: Admin credentials are overridable per environment
- **GIVEN** a developer sets `ADMIN_LOGIN=alice` and `ADMIN_PASSWORD=correct-horse-battery-staple` in their `.env` before the first bring-up
- **WHEN** `docker compose up -d` is run
- **THEN** `db-seed` SHALL insert a single `staff_accounts` row with login `alice` and the bcrypt hash of `correct-horse-battery-staple`, and no `admin` / `admin123` row SHALL be created

### Requirement: Dev stack up-wrapper prints real host URLs
The repo SHALL provide `scripts/up.sh`, a wrapper around `docker compose up -d` that brings the full stack up and prints a banner listing the host-side URLs for the customer app, the admin app, the core API, and the nginx canonical entry point, derived from the current `.env`. The wrapper SHALL (1) require a `.env` file in the repo root and exit non-zero with an actionable message if missing; (2) run `docker compose up -d` and forward any extra arguments verbatim; (3) after compose returns, poll `docker compose ps` up to 30 seconds, excluding the one-shot services `db-migrate` and `db-seed` from the "bad state" check — a one-shot service in state `exited` with exit code 0 SHALL NOT be considered unhealthy; (4) after the health wait, inspect the `db-migrate` service's exit code, and if non-zero the banner SHALL include a `⚠ Migrations FAILED — see: docker compose logs db-migrate` line in place of the success line and the wrapper SHALL exit non-zero; (5) on success, include a `Migrations: applied ✓` line in the banner before the URL block; (6) read `WEB_CUSTOMER_PORT`, `WEB_ADMIN_PORT`, `CORE_API_PORT`, and `NGINX_PORT` from `.env` without sourcing the file; (7) print a clearly demarcated banner listing the canonical entry point `http://localhost:${NGINX_PORT}/` followed by the direct URLs for customer, admin, and core-api; (8) include in the banner an explicit warning that the `localhost:5173` / `localhost:5174` URLs printed by Vite inside the web containers are container-internal and MUST be ignored.

- **Previously:** `wait_for_healthy` treated any service in state `exited` as unhealthy, so the new one-shot services (which are expected to end in `exited (0)`) would stall the wait loop for the full 30-second deadline. The banner also had no migration-status line, so a failed migration produced a superficially normal banner pointing at a broken stack.
- **Now:** The helper SHALL skip `db-migrate` and `db-seed` by name when checking for bad states, and the banner SHALL explicitly report migration status so failure is loud and success is confirmed.

#### Scenario: Banner reflects current .env ports
- **GIVEN** a `.env` with `WEB_CUSTOMER_PORT=5333`, `WEB_ADMIN_PORT=5334`, `CORE_API_PORT=8160`, `NGINX_PORT=8240`
- **WHEN** `./scripts/up.sh` is run
- **THEN** the stack comes up and the banner contains `http://localhost:8240/`, `http://localhost:5333/`, `http://localhost:5334/`, and `http://localhost:8160/`

#### Scenario: Successful migration shows explicit confirmation in the banner
- **WHEN** `./scripts/up.sh` is run against a worktree where `db-migrate` exits 0
- **THEN** the banner SHALL contain a `Migrations: applied ✓` line and the wrapper SHALL exit 0

#### Scenario: Failed migration is surfaced loudly
- **GIVEN** a worktree with a broken migration that causes `db-migrate` to exit non-zero
- **WHEN** `./scripts/up.sh` is run
- **THEN** the banner SHALL contain `⚠ Migrations FAILED — see: docker compose logs db-migrate`, the URL block SHALL either be suppressed or clearly marked "stack incomplete", and the wrapper SHALL exit non-zero

#### Scenario: One-shot exited services do not stall wait_for_healthy
- **GIVEN** `db-migrate` has exited 0 and `db-seed` has exited 0 before `wait_for_healthy` is entered
- **WHEN** the helper polls `docker compose ps`
- **THEN** it SHALL NOT match `db-migrate` or `db-seed` as "bad state", SHALL return as soon as all long-running services are healthy, and SHALL NOT spin until the 30-second deadline

#### Scenario: Missing .env is an actionable error
- **GIVEN** a worktree with no `.env` file
- **WHEN** `./scripts/up.sh` is run
- **THEN** the script SHALL exit non-zero and its error message SHALL instruct the developer to run `./scripts/setup-worktree-env.sh`

#### Scenario: Extra arguments are forwarded to docker compose
- **WHEN** `./scripts/up.sh --build core-api` is run
- **THEN** the underlying `docker compose up -d` invocation SHALL receive `--build core-api` and the banner SHALL still print on success
