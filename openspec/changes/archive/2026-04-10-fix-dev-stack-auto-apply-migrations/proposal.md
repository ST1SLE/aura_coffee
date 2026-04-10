## Why

Pulling a branch with a new Alembic revision silently leaves the dev database at the previous revision because `pgdata` is a named volume that survives across `docker compose down/up`, and neither `docker compose up` nor `scripts/up.sh` runs `alembic upgrade head`. The manual step documented in `docker-dev-env` ("Run migrations inside container") is invisible from the bring-up flow — nothing in the banner, the `.env.example`, or the compose file references it.

Concrete bite: after merging `admin-menu-bilingual-schema` into `menu_cart`, `alembic_version` stayed at `0003` while the code expected `0004_menu_tables`. Every admin menu CRUD request 500s with `psycopg2.errors.UndefinedTable: relation "categories" does not exist` (same for `modifiers`, `menu_items`, etc.). Reproduced end-to-end against the live dev stack. This blocks the entire Phase 2 manual test matrix (admin Blocks 1.1–1.5, customer Blocks 2.x, cart Blocks 3.x) because nothing downstream can run without the admin seeding the menu.

The same invisibility bites the admin-account prerequisite: `initial_admin` seed requires `ADMIN_LOGIN` / `ADMIN_PASSWORD`, neither of which is in `.env.example`, so every fresh worktree (and every new agent) hits "Part 2A: seed admin manually" as a blocker.

**MVP Phase**: cross-cutting dev infrastructure (PDD §7.1). This change unblocks Phase 2 — Menu & Cart manual testing directly, and prevents the same footgun in Phase 3+ as more migrations land.

## What Changes

- Add a dedicated one-shot `db-migrate` service to `docker-compose.yml` that runs `alembic upgrade head` once postgres is healthy, exits 0, and blocks `core-api` (and any other service that touches the DB) from starting until it has exited cleanly. Uses the existing `services/core-api/Dockerfile` `target: dev` image — no new Dockerfile, no new dependencies.
- Add a second one-shot `db-seed` service that runs after `db-migrate` completes and invokes `python -m database.seeds.initial_admin`. Split from `db-migrate` so devs can spin a clean-slate schema without the default admin row by disabling only `db-seed`, and so the "migrations are DDL, seeds are data" split stays conceptually honest.
- **BREAKING (dev only)**: Add `ADMIN_LOGIN=admin` and `ADMIN_PASSWORD=admin123` as committed defaults in `.env.example`. Same privacy posture as the existing committed `POSTGRES_PASSWORD=aura_secret` and `JWT_SECRET` placeholder. Documented explicitly as dev-only defaults.
- Patch `scripts/up.sh`'s `wait_for_healthy` to exclude the one-shot services (`db-migrate`, `db-seed`) from the "bad state" check, since those services are expected to be in state `exited` after a successful run and the current regex treats `exited` as failure.
- Update `scripts/up.sh`'s banner to print a `Migrations: applied` or `Migrations: failed (see docker compose logs db-migrate)` line derived from the `db-migrate` container's exit code, so bring-up either visibly succeeds or visibly tells the dev where to look.
- Update `database/AGENTS.md` to remove the "run this manually after a new deployment" block for `initial_admin`, and to document that `db-migrate` + `db-seed` are automatic on every `docker compose up`. The "migrations are DDL, seeds are standalone scripts" rule stays — the file-level constraint on migrations is unchanged. What changes is the orchestration.
- Update the `docker-dev-env` capability spec: remove the manual "Run migrations inside container" scenario and replace it with a scenario that asserts `db-migrate` runs on `docker compose up` and blocks `core-api` startup if it fails.
- No changes to any migration files (`database/migrations/versions/*.py`), no changes to any Python application code, no changes to the `database-setup` spec (its "migrations are DDL only" + "seeds are standalone scripts" rules remain intact — they describe file-level behavior, not orchestration).

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities

- `docker-dev-env`: the dev stack SHALL apply pending Alembic migrations and seed the initial admin account automatically on every `docker compose up`, via two one-shot services (`db-migrate`, `db-seed`) whose success blocks `core-api` startup. The spec's current "Run migrations inside container" scenario (which documents the manual exec) is superseded.

## Impact

- **Code**:
  - `docker-compose.yml` — add two services (`db-migrate`, `db-seed`), add `depends_on` on `core-api` to chain through `db-seed`.
  - `.env.example` — add `ADMIN_LOGIN=admin` and `ADMIN_PASSWORD=admin123` under a new `# Initial admin seed (dev-only defaults)` section, with an inline comment pointing at the `db-seed` service and warning that these MUST be overridden in any non-dev environment.
  - `scripts/up.sh` — patch `wait_for_healthy` to filter out one-shot services by name, and print a migration-status line in the banner.
  - `database/AGENTS.md` — swap "Run the seed manually" block for "`db-seed` runs this automatically on compose up; override `ADMIN_LOGIN`/`ADMIN_PASSWORD` in your `.env` for non-dev environments."
  - `openspec/specs/docker-dev-env/spec.md` — via the delta spec under this change.
- **APIs**: none.
- **DB**: none. No new migration, no schema change. `alembic_version` simply advances to whatever `head` says — which is the entire point.
- **Auth / RBAC**: none at runtime. Dev auth flow unchanged.
- **Dev workflow change**: `./scripts/up.sh` on a fresh worktree becomes a single command from clone to logged-in admin SPA. `docker compose up -d` (bare, without the wrapper) also works because the one-shots are compose-native. Subsequent pulls that introduce new migrations self-heal on the next `up` with no manual step.
- **Workers**: `payment-worker` and `sms-worker` do not depend on `db-migrate` because they don't touch DB tables owned by migrations (they read Redis / call external APIs). No change to their `depends_on`.
- **Dependencies**: none added. `db-migrate` and `db-seed` reuse the existing `services/core-api/Dockerfile` `dev` target image.
- **Production**: out of scope. This change edits the dev `docker-compose.yml` only. Production deploys run migrations as an explicit CI step (or will, when production exists) — that pipeline is not in this repo yet and is not touched here.
- **Inviolable rules**: INV-015 (secrets in env vars) is unchanged — `ADMIN_LOGIN`/`ADMIN_PASSWORD` are still env vars, just with committed dev defaults, exactly like `POSTGRES_PASSWORD` already is.

## Non-Goals

- **Not fixing the nginx `/admin` → `/admin/` 404.** That's a sibling concern in the same testing session, scoped to `frontend-routing`, and lives in a separate change (`fix-nginx-admin-trailing-slash`). This change MUST NOT touch `deploy/nginx/nginx.conf`.
- **Not changing migration file behavior.** The `database-setup` rule "migrations are DDL, no env reads" stays in force. `database/migrations/versions/*.py` is out of lane.
- **Not changing the `initial_admin` seed script.** The script is already idempotent via `ON CONFLICT (login) DO NOTHING`. No edits to `database/seeds/initial_admin.py`.
- **Not adding a production compose file, prod-migrate CI job, or any deploy-tier orchestration.** Scope is the local dev stack.
- **Not touching `pgdata` lifecycle.** The named volume stays persistent. The whole point is that `db-migrate` converges whatever state the volume currently holds to the code's expected head, not to wipe and recreate.
- **Not changing the test-DB auto-provisioning in `conftest.py::_ensure_test_database`.** That flow already does the right thing for the test DB and is documented in the `database-setup` spec. This change is about the dev DB, not the test DB.
- **Not adding ADMIN_LOGIN / ADMIN_PASSWORD to CI secrets.** CI runs pytest against the test DB, which does not invoke `db-seed`. No CI-side change.
- **Not auto-recovering from a failed migration.** If `db-migrate` fails, `core-api` does not start, and the banner says so. The fix is the dev fixing the migration, not the orchestration hiding the failure.
- **Not adding a `--no-migrate` or `--no-seed` flag to `scripts/up.sh`.** Devs who need to bypass can `docker compose up -d --scale db-seed=0` or run `docker compose up -d` against a subset. Adding flags is scope creep.

## File Lane (merge safety)

This change is allowed to modify ONLY:

```
docker-compose.yml
.env.example
scripts/up.sh
database/AGENTS.md
openspec/changes/fix-dev-stack-auto-apply-migrations/**
openspec/specs/docker-dev-env/spec.md                 (via archive at merge time; delta lives under changes/)
```

This change MUST NOT touch:

```
deploy/nginx/**                       (reserved for fix-nginx-admin-trailing-slash)
database/migrations/**                (migration files are out of lane)
database/seeds/**                     (seed script is out of lane)
services/**                           (no application code changes)
packages/**
web/**
openspec/specs/database-setup/**      (database-setup rules are unchanged)
openspec/specs/frontend-routing/**    (reserved for sibling change)
```

If during implementation the agent discovers a required change outside the lane (e.g. the seed script needs a small fix to be compose-friendly), STOP and escalate to the user. Do not broaden the diff silently.
