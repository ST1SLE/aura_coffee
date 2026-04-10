## Context

The dev stack's current migration model is "manual, invisible, and silently stale." `pgdata` is a named volume that persists across `docker compose down && docker compose up`. `alembic_version` in that volume is whatever was last applied. Code in `database/migrations/versions/` marches forward as branches merge. Nothing in the bring-up flow (`./scripts/up.sh` or `docker compose up -d`) bridges the gap. The `docker-dev-env` spec currently documents the manual step ("Run migrations inside container") but the only place that surfaces it is a scenario inside a spec file nobody reads during onboarding.

Concrete incident motivating this change: the `menu_cart` branch's `0004_menu_tables.py` was never applied against any developer's `pgdata`. Every admin menu CRUD call returned `500 UndefinedTable`, blocking the entire Phase 2 manual test matrix. Confirmed against the live stack: `SELECT version_num FROM alembic_version` → `0003`; `POST /api/v1/admin/menu/categories` → `500`; log shows `relation "categories" does not exist`.

The parallel "seed admin manually" footgun has the same shape: `ADMIN_LOGIN` / `ADMIN_PASSWORD` aren't in `.env.example`, so the seed step is invisible and error-prone.

The test DB (`aura_coffee_test`) already auto-migrates via `conftest.py::_ensure_test_database` — precedent exists for "migrations run automatically in a specific orchestration context, while the file-level rules stay strict." This change extends that precedent from the test-DB context to the dev-DB context.

## Goals / Non-Goals

**Goals:**
- `./scripts/up.sh` (and bare `docker compose up -d`) on a fresh worktree is a single command from clone to logged-in admin SPA.
- Pulling a branch with new migrations self-heals on the next bring-up with zero manual steps.
- Migration failures are loud: `core-api` refuses to start, banner says where to look, wrapper exits non-zero.
- Preserve the file-level discipline from `database-setup`: migrations remain DDL-only, seeds remain standalone Python scripts. The change is orchestration, not file semantics.
- Keep production semantics untouched: prod migrations remain an explicit CI/CD step (elsewhere).

**Non-Goals:**
- No changes to any migration file or seed script. If they're buggy, that's a separate change.
- No nginx changes (sibling change).
- No changes to worker services' `depends_on` — they don't touch migration-owned tables.
- No `--no-migrate` / `--no-seed` flags on `scripts/up.sh`.
- No production compose file, no CI migration job.
- No automatic downgrade / rollback on failure.

## Decisions

### D1. One-shot compose service vs core-api entrypoint

**Chosen**: Dedicated one-shot services (`db-migrate`, `db-seed`).

**Alternatives considered:**
- **(a) `core-api` entrypoint runs `alembic upgrade head && exec uvicorn ...`**. Simplest diff, zero new services. Rejected because: (1) mingles migration logs with uvicorn logs, making `docker compose logs core-api` noisy; (2) if a migration fails, core-api crashes in a loop instead of exiting once with a clean failure signal; (3) conflates concerns — `docker compose restart core-api` re-runs migrations as a side effect; (4) no clean place to show a "migrations applied" banner.
- **(b) `scripts/up.sh` runs `docker compose exec core-api alembic upgrade head` after bring-up**. Rejected because bare `docker compose up -d` (bypassing the wrapper) would still be broken. The `docker-dev-env` spec has a "Copy and run" scenario that asserts `docker compose up` alone works — option (b) breaks it.
- **(c) Banner warning only, keep it manual**. Rejected as the root-cause cause of the current incident. A warning doesn't close the loop; the next agent will forget.

**Rationale for one-shot services:**
- Compose-native. No scripts, no entrypoint magic.
- Explicit in `docker compose ps`: `db-migrate Exited (0)` is visible.
- `depends_on: service_completed_successfully` gives us a clean dependency chain. If migration fails, `core-api` doesn't start; no crash loop, no partial state.
- Isolated logs: `docker compose logs db-migrate` is exactly the migration output. Separate from uvicorn.
- Works identically whether the dev runs `./scripts/up.sh` or `docker compose up -d`.
- Reuses the existing `services/core-api/Dockerfile` `dev` target image. No new Dockerfile, no new dependencies, no new build step.

### D2. Split `db-migrate` and `db-seed` into two services

**Chosen**: Split.

**Alternatives considered:**
- **(a) Single `db-bootstrap` service that runs migrate-then-seed**. 20 lines less YAML.
- **(b) Split into `db-migrate` + `db-seed`, chained via `service_completed_successfully`**.

**Rationale for split:**
- Matches the existing file-level split: migrations are DDL (under `database/migrations/`), seeds are standalone Python (under `database/seeds/`). Keeping the runtime split parallel to the file split reduces cognitive friction.
- Lets a developer spin a clean-slate schema without the default admin by `docker compose up -d db-migrate postgres redis core-api` (i.e. excluding `db-seed` from the up set). Not a common workflow, but cheap to preserve.
- Failure modes are more granular: a failed migration vs a failed seed (which has a different root-cause surface: bcrypt, env vars, etc.) are visible as distinct services in `ps` and distinct log streams.
- Future seeds (promocodes, shop settings, test data) can be added as additional one-shot services chained off `db-migrate` without touching the migration container.

**Trade-off**: more YAML (~20 lines) and one extra ~1–2s for the seed container to start its own Python interpreter. Acceptable.

### D3. Commit `admin` / `admin123` defaults to `.env.example`

**Chosen**: Yes, commit dev defaults to `.env.example`.

**Alternatives considered:**
- **(a) Commit to `.env.example`**. Devs get auto-seeding with no per-worktree edits.
- **(b) Hard-code inside `docker-compose.yml`'s `db-seed` service block (`environment: ADMIN_LOGIN=admin`...)**. Keeps `.env.example` cleaner but still commits the credential to git.
- **(c) Leave seed disabled unless dev sets the env vars themselves**. Rejected — reintroduces the exact footgun this change exists to remove.

**Rationale for (a):**
- `.env` is already the canonical place for every dev secret. Putting the admin credential there matches the mental model. `POSTGRES_PASSWORD=aura_secret` and the `JWT_SECRET` placeholder already live there; `ADMIN_LOGIN`/`ADMIN_PASSWORD` are no more sensitive.
- Devs inspecting `.env` see the full set of dev defaults in one place, instead of having to dig into `docker-compose.yml` to find out what credentials the seed uses.
- `./scripts/setup-worktree-env.sh` already has a production guard (refuses to run on hosts with `.env.production` or `AURA_PRODUCTION_HOST=1`), so the risk of `.env` leaking dev creds into a prod-ish env is already mitigated by the bootstrap script's own safeguards.
- The `.env.example` section gets an explicit comment calling out that these are dev-only and MUST be overridden elsewhere. Defense in depth.

**Trade-off accepted**: `admin` / `admin123` is now a public string in git. A copy-paste mistake could leak it into staging if someone grabs `.env.example` without reading the comment. But this is already true for every other committed default, and the production guard is the primary barrier.

### D4. Patch `wait_for_healthy` in `scripts/up.sh` instead of replacing it

**Chosen**: Minimal patch — add `db-migrate|db-seed` to a name-based skip list in the existing regex.

**Alternatives considered:**
- **(a) Rewrite the helper to check exit codes per service**. More robust but larger diff.
- **(b) Change the regex to only flag `dead` (not `exited`)**. Would also let a genuinely-crashed service slip through.
- **(c) Add a name-based skip list for one-shots.**

**Rationale for (c):**
- Smallest diff to a critical script.
- Explicit: reviewers can see exactly which services are one-shots.
- Future-proof: adding another one-shot (`db-backup`, `db-snapshot`, etc.) requires updating the skip list, which is the right forcing function.

### D5. Banner prints migration status

**Chosen**: After `wait_for_healthy`, inspect `db-migrate`'s exit code and print `Migrations: applied ✓` or `⚠ Migrations FAILED — see: docker compose logs db-migrate`.

**Rationale**: The failure case is the one that matters. Without a banner line, a failed migration silently leads to a broken stack with no signal until the dev clicks around and hits 500s (exactly today's bug). An explicit status line forces the signal to be visible during the 2–3 seconds the dev is looking at the terminal right after bring-up.

## Risks / Trade-offs

- **[Risk] `db-migrate` or `db-seed` breaks compose bring-up on a worktree that has pending migrations with bugs** → Mitigation: that's the intended failure mode. Banner says exactly where to look, and `docker compose logs db-migrate` shows the traceback. Devs fix the migration, re-run `./scripts/up.sh`. No worse than today, and more visible.
- **[Risk] Cold start latency increases by ~5–10s for the first `db-migrate` image pull and ~2–3s per subsequent run** → Mitigation: accepted. One-time cost on cold start, minimal cost on every subsequent up. Far less than the 10+ minutes of debugging a 500 error caused by a missing migration.
- **[Risk] Devs committing `admin`/`admin123` defaults to `.env.example` could leak if the file is copied into a staging environment without review** → Mitigation: (1) inline comment in `.env.example` calls it out explicitly; (2) `setup-worktree-env.sh` already has a production guard; (3) every non-dev environment must override via its own `.env`, same rule as every other dev default (e.g. `POSTGRES_PASSWORD`).
- **[Risk] `depends_on: service_completed_successfully` is a modern compose feature (Compose v2.1+) — older compose installs might not honor it** → Mitigation: Compose v2 is the baseline for this project (`docker compose up` syntax, healthchecks already in use). If a dev is on v1 they already have bigger compatibility issues. No action.
- **[Risk] Running `docker compose restart core-api` will not re-run `db-migrate`** → Mitigation: that's correct behavior. `restart` is for recovering a running service, not for schema convergence. Devs who want to re-migrate run `docker compose up -d db-migrate` or bounce the full stack.
- **[Risk] The `db-seed` service will run its Python module every `up`, even when the schema hasn't changed** → Mitigation: the seed is idempotent (`ON CONFLICT (login) DO NOTHING`). The runtime cost is one bcrypt hash + one INSERT attempt ≈ 200ms. Negligible.
- **[Risk] If a dev manually inserts a different admin row and then runs `up`, `db-seed` will attempt to insert the `.env`-provided row too** → Mitigation: the conflict clause protects the existing row. If the dev wants a non-`admin` admin, they override in `.env` (Scenario "Admin credentials are overridable per environment" covers this).
- **[Trade-off] Migration speed on first bring-up of a fresh worktree is now gated by `db-migrate`'s completion** → `core-api` boots later, which the `depends_on` chain serializes. But this was already the expected order of operations; today it's just implicit and unenforced.

## Migration Plan

1. Add the two one-shot services to `docker-compose.yml`, add `depends_on` to `core-api`.
2. Add the dev-only admin defaults to `.env.example`.
3. Patch `scripts/up.sh`'s `wait_for_healthy` and banner.
4. Update `database/AGENTS.md` to drop the "run the seed manually" block.
5. **Local verification (no code changes, pure orchestration)**:
   - `docker compose down` (keeps pgdata).
   - `docker compose up -d`.
   - Confirm `docker compose ps` shows `db-migrate Exited (0)` and `db-seed Exited (0)`.
   - Confirm `SELECT version_num FROM alembic_version;` returns `0004`.
   - Confirm `POST /api/v1/admin/menu/categories` with a valid payload returns 201 instead of 500.
   - Confirm `./scripts/up.sh` prints `Migrations: applied ✓` in the banner.
6. **Failure-mode verification**: temporarily introduce a syntax error in a migration, re-run `./scripts/up.sh`, confirm the banner shows the failure line and the wrapper exits non-zero. Revert the intentional break.
7. **Rollback strategy**: revert the commits touching `docker-compose.yml`, `.env.example`, `scripts/up.sh`, and `database/AGENTS.md`. No data changes, no schema changes, no application code changes — rollback is a pure revert. Devs go back to running `alembic upgrade head` manually.

## Open Questions

- None blocking. All decisions resolved during explore phase.
