## 1. Baseline reproduction

- [ ] 1.1 PREREQ [dev-env] With the current `menu_cart` branch checked out and the dev stack up, run `docker compose exec -T postgres psql -U aura -d aura_coffee -c "SELECT version_num FROM alembic_version"` and confirm it returns `0003` (the broken baseline). Record the value in the task log.
- [ ] 1.2 PREREQ [dev-env] Run `docker compose exec -T -e ADMIN_LOGIN=admin -e ADMIN_PASSWORD=admin123 core-api python -m database.seeds.initial_admin` once to make the admin account exist for reproduction. Then call `POST /api/v1/admin/menu/categories` with a valid body (use the JWT from `POST /api/v1/staff/auth/login`) and confirm the request returns HTTP 500. Grep `docker compose logs core-api --tail 80` for `UndefinedTable` and record the exact error line. This is the baseline the fix must eliminate.

## 2. Compose one-shot services

- [ ] 2.1 IMPL [docker-compose] In `docker-compose.yml`, add a `db-migrate` service before the `core-api` block. The service SHALL use `build.context: .`, `build.dockerfile: services/core-api/Dockerfile`, `build.target: dev`, `env_file: .env`, volume mounts for `./packages/shared/src`, `./services/core-api/src`, and `./database`, `depends_on: postgres: condition: service_healthy`, `command: ["sh", "-c", "cd /app/database && alembic upgrade head"]`, and `restart: "no"`.
- [ ] 2.2 IMPL [docker-compose] In `docker-compose.yml`, add a `db-seed` service after `db-migrate`. Same image, same mounts, same `env_file`. `command: ["python", "-m", "database.seeds.initial_admin"]`. `depends_on: db-migrate: condition: service_completed_successfully`. `restart: "no"`.
- [ ] 2.3 IMPL [docker-compose] Extend the existing `core-api` service's `depends_on` to add `db-seed: condition: service_completed_successfully` alongside the existing `postgres` and `redis` entries. Do NOT remove the existing postgres/redis dependencies.
- [ ] 2.4 VERIFY [docker-compose] Run `docker compose config` and confirm the rendered output lists both new services and the `core-api` dependency chain resolves without warnings. Run `docker compose up -d db-migrate` in isolation and confirm it exits 0 (from `docker compose ps`). Run `docker compose up -d db-seed` and confirm it also exits 0.

## 3. Environment defaults

- [ ] 3.1 IMPL [env] In `.env.example`, add a new section `# Initial admin seed (dev-only defaults — override in any non-dev environment)` with `ADMIN_LOGIN=admin` and `ADMIN_PASSWORD=admin123`. Place the section after the host-port bindings, before the external-API keys section. Include a one-line inline comment pointing at the `db-seed` compose service as the consumer.
- [ ] 3.2 IMPL [env] In `.env` (the developer's local, git-ignored file), add the same two lines if they aren't already set, so the local reproduction can run the new flow. This is a local-only change, not committed.
- [ ] 3.3 VERIFY [env] Run `docker compose exec -T db-seed env | grep ADMIN` (after a full `docker compose up -d`) and confirm both env vars are present in the container's environment, proving `env_file` propagation works.

## 4. scripts/up.sh patch

- [ ] 4.1 IMPL [scripts] In `scripts/up.sh`'s `wait_for_healthy` helper, modify the `bad=` line so it excludes services whose name matches `db-migrate` or `db-seed`. Simplest form: pipe `docker compose ps --format json` through a `grep -v` filter by name before the state regex. Keep the 30-second deadline unchanged.
- [ ] 4.2 IMPL [scripts] After `wait_for_healthy` returns and before the banner block, query `docker compose ps --format json` for the `db-migrate` service, parse its `ExitCode`, and set a shell variable `MIGRATE_STATUS="applied ✓"` if exit code is 0, `MIGRATE_STATUS="FAILED — see: docker compose logs db-migrate"` otherwise.
- [ ] 4.3 IMPL [scripts] Modify the banner heredoc to include a `Migrations: ${MIGRATE_STATUS}` line immediately below the `Aura Coffee — dev stack is up` header, before the URL block. If `MIGRATE_STATUS` indicates failure, wrap the URL block in a `⚠ Stack incomplete — see above` note and have `scripts/up.sh` exit non-zero after printing.
- [ ] 4.4 VERIFY [scripts] Run `./scripts/up.sh` against a healthy stack and confirm the banner shows `Migrations: applied ✓`. The wrapper SHALL exit 0.
- [ ] 4.5 VERIFY [scripts] Introduce a temporary syntax error in a copy of `database/migrations/versions/0004_menu_tables.py` (e.g. add `raise Exception("test")` at the top of `upgrade()`). Run `./scripts/up.sh`, confirm the banner shows `⚠ Migrations FAILED` and the script exits non-zero. REVERT the intentional break immediately after verifying.

## 5. Documentation

- [ ] 5.1 IMPL [docs] In `database/AGENTS.md`, replace the "Running the initial admin seed" section's manual block (the `docker compose exec -e ADMIN_LOGIN=... core-api python -m database.seeds.initial_admin` command) with a paragraph explaining that `db-seed` runs this automatically on `docker compose up`, and that `ADMIN_LOGIN` / `ADMIN_PASSWORD` come from `.env` (with dev defaults in `.env.example`). Preserve the existing "Schema-only migrations" and "This Module MUST NOT" sections unchanged.
- [ ] 5.2 VERIFY [docs] Re-read `database/AGENTS.md` end-to-end and confirm the removed section is the only thing that changed. Spot-check the "Schema-only migrations" constraints are intact — they describe file-level rules, which this change does not touch.

## 6. End-to-end verification

- [ ] 6.1 VERIFY [stack] Stop the stack with `docker compose down` (keep the `pgdata` volume). Manually `docker compose exec -T postgres psql -U aura -d aura_coffee -c "UPDATE alembic_version SET version_num = '0003'"` to simulate a pre-migration worktree state. Then run `./scripts/up.sh`. After bring-up, query `alembic_version` and confirm it has advanced to `0004`.
- [ ] 6.2 VERIFY [stack] Get an admin JWT via `POST /api/v1/staff/auth/login` with `admin` / `admin123`. `POST /api/v1/admin/menu/categories` with `{"type":"drink","name_ru":"Кофе","name_en":"Coffee","sort_order":1,"is_visible":true}` and confirm HTTP 201 (not 500). Record the response body.
- [ ] 6.3 VERIFY [stack] `POST /api/v1/admin/menu/modifiers` with `{"name_ru":"Сироп","name_en":"Syrup","price":50,"available":true,"sort_order":0}` and confirm HTTP 201. Record the response.
- [ ] 6.4 VERIFY [stack] Confirm the seed idempotency by running `docker compose up -d db-seed` a second time. Expect exit code 0 and a log line indicating the `ON CONFLICT` clause was hit (or similar — at minimum no duplicate row and no error). `SELECT count(*) FROM staff_accounts WHERE login='admin'` SHALL return 1.
- [ ] 6.5 VERIFY [stack] Confirm fresh-worktree path: `docker compose down -v` (WARNING: wipes `pgdata`; only do this step on the local dev machine and only after capturing any data you care about). Then `./scripts/up.sh`. After bring-up, confirm that (a) `db-migrate` runs and exits 0, (b) `db-seed` runs and exits 0, (c) login as `admin`/`admin123` works, (d) admin menu CRUD works. Record each step.
