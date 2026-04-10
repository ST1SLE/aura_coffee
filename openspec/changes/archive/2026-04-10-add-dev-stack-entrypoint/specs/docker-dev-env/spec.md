## MODIFIED Requirements

### Requirement: Parameterized host ports for multi-worktree coexistence
Every host port binding in `docker-compose.yml` SHALL be declared as `${VAR:-default}` so that each git worktree running the stack can override it via its own `.env` without editing shared files. The six variables SHALL be `POSTGRES_PORT`, `REDIS_PORT`, `CORE_API_PORT`, `WEB_CUSTOMER_PORT`, `WEB_ADMIN_PORT`, `NGINX_PORT`. Defaults SHALL be `5433 / 6379 / 8000 / 5173 / 5174 / 8240`. `.env.example` SHALL declare all six variables under a `# Host port bindings` section with an inline comment explaining the per-worktree offset convention (bump every port by the same offset).

**Previously:** `NGINX_PORT` default was `80` (privileged). The six defaults were `5433 / 6379 / 8000 / 5173 / 5174 / 80`.

**Now:** `NGINX_PORT` default is `8240` (non-privileged) so nginx binds without root on developer machines and can serve as the canonical local entry point without privilege escalation. The other five defaults are unchanged.

Relates to: PDD §7 (dev infrastructure, cross-cutting — no INV-XXX impact).

#### Scenario: Defaults preserve single-worktree behavior
- **GIVEN** a worktree with `.env` copied verbatim from `.env.example`
- **WHEN** `docker compose up -d` is run
- **THEN** host ports bind to `5433 / 6379 / 8000 / 5173 / 5174 / 8240`

#### Scenario: Two worktrees coexist on distinct ports
- **GIVEN** two worktrees each with their own `.env` using port offsets `+0` and `+10` respectively
- **WHEN** both run `docker compose up -d`
- **THEN** both stacks start successfully with no host port conflicts

#### Scenario: Nginx binds without elevated privileges
- **GIVEN** a developer machine where ports `<1024` are not bindable by unprivileged processes
- **WHEN** `docker compose up -d` is run with the default `NGINX_PORT=8240`
- **THEN** the `nginx` service binds successfully and `http://localhost:8240/` is reachable

### Requirement: Bootstrap script for per-worktree environment
The repo SHALL provide `scripts/setup-worktree-env.sh` that generates a per-worktree `.env` from `.env.example` with a collision-free host port offset. The script SHALL:

1. Derive a deterministic starting offset from `sha1sum` of the worktree path, in the range `[0, 200)` stepped by 10.
2. Probe each candidate port set (`POSTGRES_PORT`, `REDIS_PORT`, `CORE_API_PORT`, `WEB_CUSTOMER_PORT`, `WEB_ADMIN_PORT`, `NGINX_PORT` with the offset applied to the `.env.example` baselines) against `127.0.0.1` via bash `/dev/tcp`. If any port is bound, bump offset by +10 and retry, up to 20 attempts.
3. On the first free set, write `.env` from `.env.example` with every port replaced and `CORS_ORIGINS` patched to match the chosen `WEB_CUSTOMER_PORT` and `WEB_ADMIN_PORT`.
4. Be idempotent — re-running SHALL pick a fresh offset if the current `.env` ports have since been taken by another stack.

The script SHALL refuse to run on a host marked as production, to prevent clobbering prod config with dev defaults. Production markers SHALL be any of: a `.env.production` file at repo root, `AURA_PRODUCTION_HOST=1` in the environment, or a `/etc/aura-coffee/production` marker file. The production guard SHALL be overridable only via explicit `FORCE=1`.

**Previously:** The `.env.example` port baselines the script substituted were `5433 / 6379 / 8000 / 5173 / 5174 / 80`.

**Now:** The `NGINX_PORT` baseline is `8240`, matching the new `.env.example` default. All other probing, production-guard, and idempotency behavior is unchanged.

Relates to: PDD §7 (dev infrastructure). No INV-XXX impact.

#### Scenario: Script picks a free offset deterministically
- **GIVEN** a worktree whose path hashes to starting offset `+N`
- **AND** no other stack is bound on any of the six ports at offset `+N`
- **WHEN** `./scripts/setup-worktree-env.sh` is run
- **THEN** `.env` is written with all six ports at offset `+N` applied to the `.env.example` baselines (including `NGINX_PORT=8240+N`) and `CORS_ORIGINS` patched to match, and the same worktree path always produces the same starting offset

#### Scenario: Script skips collisions and picks the next free offset
- **GIVEN** another stack is already bound on at least one port at starting offset `+N`
- **WHEN** `./scripts/setup-worktree-env.sh` is run
- **THEN** the script detects the collision, bumps offset by +10, re-probes, and writes `.env` with the first fully-free offset it finds

#### Scenario: Production guard refuses to run
- **GIVEN** a `.env.production` file exists at repo root (or `AURA_PRODUCTION_HOST=1`, or `/etc/aura-coffee/production` exists)
- **WHEN** `./scripts/setup-worktree-env.sh` is run without `FORCE=1`
- **THEN** the script exits with status 1 and does not modify `.env`

## ADDED Requirements

### Requirement: Dev stack up-wrapper prints real host URLs
The repo SHALL provide `scripts/up.sh`, a wrapper around `docker compose up -d` that brings the full stack up and prints a banner listing the host-side URLs for the customer app, the admin app, the core API, and the nginx canonical entry point, derived from the current `.env`. The wrapper SHALL (1) require a `.env` file in the repo root and exit non-zero with an actionable message if missing; (2) run `docker compose up -d` and forward any extra arguments verbatim; (3) after compose returns, read `WEB_CUSTOMER_PORT`, `WEB_ADMIN_PORT`, `CORE_API_PORT`, and `NGINX_PORT` from `.env` without sourcing the file; (4) print a clearly demarcated banner listing the canonical entry point `http://localhost:${NGINX_PORT}/` followed by the direct URLs for customer, admin, and core-api; (5) include in the banner an explicit warning that the `localhost:5173` / `localhost:5174` URLs printed by Vite inside the web containers are container-internal and MUST be ignored. The wrapper exists because Vite dev servers inside `web-customer` and `web-admin` containers log their container-internal ports, which do not match host ports when worktrees bump them — following those logs produces "connection refused".

Relates to: PDD §7 (dev infrastructure, cross-cutting). No INV-XXX impact.

#### Scenario: Banner reflects current .env ports
- **GIVEN** a `.env` with `WEB_CUSTOMER_PORT=5333`, `WEB_ADMIN_PORT=5334`, `CORE_API_PORT=8160`, `NGINX_PORT=8240`
- **WHEN** `./scripts/up.sh` is run
- **THEN** the stack comes up and the banner contains `http://localhost:8240/`, `http://localhost:5333/`, `http://localhost:5334/`, and `http://localhost:8160/`

#### Scenario: Missing .env is an actionable error
- **GIVEN** a worktree with no `.env` file
- **WHEN** `./scripts/up.sh` is run
- **THEN** the script exits non-zero and its error message instructs the developer to run `./scripts/setup-worktree-env.sh`

#### Scenario: Extra arguments are forwarded to docker compose
- **WHEN** `./scripts/up.sh --build core-api` is run
- **THEN** the underlying `docker compose up -d` invocation receives `--build core-api` and the banner still prints on success

### Requirement: Nginx is the canonical local entry point
For local development, `http://localhost:${NGINX_PORT}/` SHALL be documented as the canonical entry point for browsing the site. `.env.example` and `AGENTS.md` SHALL state this explicitly and SHALL warn that the `localhost:5173` / `localhost:5174` URLs printed by Vite dev servers inside the `web-customer` and `web-admin` containers are container-internal and MUST be ignored. Direct access to Vite dev servers via `WEB_CUSTOMER_PORT` / `WEB_ADMIN_PORT` MAY remain available for debugging but SHALL NOT be presented as the recommended access path.

Relates to: PDD §7 (dev infrastructure). No INV-XXX impact. Does not alter production deployment topology.

#### Scenario: .env.example documents the canonical entry point
- **WHEN** a developer reads `.env.example`
- **THEN** the `# Host port bindings` section contains a comment identifying `http://localhost:${NGINX_PORT}/` as the canonical local entry point and warning that Vite log URLs (`localhost:5173` / `localhost:5174`) are container-internal

#### Scenario: AGENTS.md explains the Vite log footgun
- **WHEN** a developer or agent reads the dev-env section of `AGENTS.md`
- **THEN** it states that `scripts/up.sh` prints the real host URLs and that the `localhost:5173` / `localhost:5174` lines from `web-customer` / `web-admin` logs MUST NOT be followed
