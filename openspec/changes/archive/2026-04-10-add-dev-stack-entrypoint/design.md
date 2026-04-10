## Context

**Affected modules:** `[web-customer]`, `[web-admin]`, `[infra]` (docker-compose, nginx, `.env.example`, `scripts/`, `AGENTS.md`). No impact on `[core-api]`, `[payment-worker]`, `[sms-worker]`, `[shared]`, `[database]`, or `[redis]`. No runtime code paths are altered — this is pure dev tooling and documentation.

**Current state (as of this worktree):**

- `docker-compose.yml` parameterizes host ports via `${VAR:-default}` for the six worktree-bumpable variables (`POSTGRES_PORT`, `REDIS_PORT`, `CORE_API_PORT`, `WEB_CUSTOMER_PORT`, `WEB_ADMIN_PORT`, `NGINX_PORT`). Defaults are `5433 / 6379 / 8000 / 5173 / 5174 / 80`.
- `scripts/setup-worktree-env.sh` exists and generates a per-worktree `.env` at an offset derived from the worktree path hash.
- `web/customer/vite.config.ts` hardcodes `server.port = 5173` and `web/admin/vite.config.ts` hardcodes `server.port = 5174`. Vite's boot banner always prints `Local: http://localhost:5173/` (or `5174`) — these are the container-internal ports. When the host port has been bumped (e.g. `WEB_CUSTOMER_PORT=5333`), following Vite's banner produces "connection refused" on the host because nothing listens on `5173`.
- `deploy/nginx/nginx.conf` routes `/` → `web-customer:5173`, `/admin` → `web-admin:5174`, `/api/` → `core-api:8000`, all on the internal Docker network. Nginx is already wired as a potential single entry point.
- `NGINX_PORT=80` is privileged; binding it requires root. Docker on Linux usually runs as root so this works, but it is fragile, conflicts with any host-side web server, and makes "just use nginx as the entry point" feel heavier than it is.

**Observed incident (this session):** a developer with `WEB_CUSTOMER_PORT=5333` opened `http://localhost:5173/` because that is what the `web-customer` container logged, and saw "connection refused". The root cause is not a bug in compose or nginx — it is the absence of a louder, correct signal that overrides Vite's misleading banner.

**Stakeholders:** every developer bringing up the stack in any worktree, plus AI agents that read logs and try to follow the first URL they see.

## Goals / Non-Goals

**Goals:**
- Eliminate the "follow the Vite log → connection refused" footgun for any worktree, current or future.
- Make nginx the default, frictionless local entry point by binding it on a non-privileged port out of the box.
- Keep the change surface small: one new shell script, one default flip, one doc update. No new processes, no new tooling, no Makefile.
- Preserve the existing per-worktree port customization flow (`scripts/setup-worktree-env.sh`) with no behavioral change beyond the new `NGINX_PORT` baseline.

**Non-Goals:**
- Not fixing `web/admin/vite.config.ts`'s missing `/api` proxy. Serving admin through nginx sidesteps this but does not resolve the direct-Vite-admin failure mode.
- Not fixing the Vite base-path issue when admin is reverse-proxied under `/admin` (Vite serves assets from `/` by default). That is a separate nginx/Vite configuration change and will not be attempted here.
- Not rewriting Vite's stdout or suppressing its banner.
- Not introducing `just`, `make`, `taskfile`, or any other task runner.
- Not touching production nginx, TLS, or deployment topology.

## Decisions

### Decision 1: Change the `NGINX_PORT` default from `80` to `8240`

**Chosen:** `NGINX_PORT=8240` in `.env.example` and as the `${NGINX_PORT:-8240}` fallback in `docker-compose.yml`.

**Why:**
- `<1024` ports require root on Linux; even when docker-proxy can bind them, they frequently collide with host-side services (`systemd-resolved`, a system nginx, `httpd`, etc.) and produce opaque startup failures.
- `8240` is far from common developer ports (`3000`, `5173`, `8000`, `8080`) and sits near the existing `CORE_API_PORT=8000`, making the set of dev ports visually contiguous. It is not a registered IANA port in widespread use.
- Worktrees bumping in +10 increments stay comfortably in the `82xx` range before wrapping.

**Alternatives considered:**
- Keep `80`, require developers to `sudo`. Rejected: hostile UX, breaks the "`docker compose up` Just Works" promise.
- `8080`. Rejected: high collision rate with other dev servers (Tomcat, Jenkins, generic reverse proxies).
- `8000` or `8001`. Rejected: collides with `CORE_API_PORT=8000` baseline.
- `3000`. Rejected: reserved-in-spirit for Node/Next.js dev servers; high collision rate.

**Breaking surface:** Developers with an existing `.env` containing `NGINX_PORT=80` are unaffected — the change is only to the `.env.example` default and the compose fallback. `scripts/setup-worktree-env.sh` will generate new `.env` files at the new baseline going forward. Documented in proposal as "BREAKING (dev only)".

### Decision 2: Add `scripts/up.sh` as a thin wrapper over `docker compose up -d`

**Chosen:** A ~30-line bash script that:
1. Verifies `.env` exists (exits non-zero with a message pointing at `scripts/setup-worktree-env.sh` if not).
2. Runs `docker compose up -d "$@"` (forwarding any extra args like `--build` or specific service names).
3. On success, sources the four relevant port variables from `.env` using a controlled parse (grep + cut, NOT `source` — `.env` may contain values with `$`, `#`, or spaces and must not be executed as shell) and prints a boxed banner.
4. The banner lists the canonical nginx entry point first, then the direct Vite/core-api URLs, and ends with a one-line warning that `localhost:5173` / `localhost:5174` in container logs are container-internal and MUST be ignored.

**Why a shell script and not a Python helper or a compose `healthcheck` echo:**
- Bash is already the language of `scripts/setup-worktree-env.sh`. One script family, one mental model.
- No Python dependency outside containers, no `uv run` friction.
- Compose does not have a first-class post-up hook. Attempting to print the banner from inside a container is worse because the container doesn't know the host port mapping.

**Alternatives considered:**
- **Compose post-hook container.** A throwaway `alpine` service that prints URLs. Rejected: compose ordering makes this fragile, and the container can't reliably read the host-side `.env` values without duplicating them into its own environment.
- **Makefile target.** Rejected: adds a new tool to onboarding; the rest of the repo has no Makefile.
- **Fold into `setup-worktree-env.sh`.** Rejected: that script runs *once per worktree creation*, `up.sh` runs *every time you bring the stack up*. Different cadences, different concerns.

**Parsing `.env` safely:** use `grep -E '^(WEB_CUSTOMER_PORT|WEB_ADMIN_PORT|CORE_API_PORT|NGINX_PORT)=' .env | cut -d= -f2-`. Do NOT `source .env`. This prevents any shell injection from `.env` content and avoids exporting unrelated variables (`JWT_SECRET_KEY`, etc.) into the script's environment.

### Decision 3: Document nginx as the canonical local entry point in `.env.example` and `AGENTS.md`

**Chosen:** Add a short section to the `# Host port bindings` block in `.env.example` pointing at `http://localhost:${NGINX_PORT}/` and calling out the Vite log footgun. Add a matching subsection to the dev-env part of `AGENTS.md` so AI agents reading the repo encounter the same guidance.

**Why:** Both humans and agents currently have no in-repo signal that the `5173`/`5174` banner lines are wrong. The banner from `scripts/up.sh` is the loudest signal, but it only fires at stack-up time — the static docs cover the case where someone looks at logs mid-session or onboards without running the wrapper first.

**Alternatives considered:**
- Patch Vite to print the host port. Rejected: Vite has no visibility into docker port mapping.
- Wrap Vite's command in the compose file with `sh -c "npm run dev ... 2>&1 | sed ..."`. Rejected: brittle, fights upstream, produces confusing logs.

## Risks / Trade-offs

- **[Risk] `scripts/up.sh` drifts from `docker compose up` as the authoritative invocation.** Developers may skip it and hit the same footgun. → **Mitigation:** Keep the script trivial so there's no reason to bypass it; reference it from `AGENTS.md` and `.env.example`; the banner doubles as positive reinforcement.
- **[Risk] Port `8240` collides on some developer's machine.** → **Mitigation:** `scripts/setup-worktree-env.sh` already probes for collisions and bumps the offset. The default is only relevant for single-worktree, fresh-`.env` cases; the probing path handles the rest.
- **[Risk] A developer with an existing `.env` containing `NGINX_PORT=80` continues using a privileged port indefinitely.** → **Mitigation:** Accept this. Their setup still works; the change is strictly additive for them. A migration note in `AGENTS.md` is enough.
- **[Risk] Banner parsing of `.env` breaks if a value contains `=`.** → **Mitigation:** `cut -d= -f2-` (not `-f2`) preserves everything after the first `=`. Port variables are integers so this is academic, but the pattern is correct in general.
- **[Trade-off] Admin access via nginx is still broken** (missing Vite base-path config, missing admin `/api` proxy). → **Mitigation:** Acknowledged as a non-goal; this change does not pretend to fix it. A follow-up change proposal will address `web-admin` reverse-proxy correctness. For now, admin remains usable via `http://localhost:${WEB_ADMIN_PORT}/` once its `/api` proxy is added (also a follow-up) or via direct core-api calls from the browser.

## Migration Plan

1. Merge the change. New `.env.example` has `NGINX_PORT=8240`.
2. Existing worktrees with an existing `.env` keep working unchanged — the compose fallback only matters when the variable is absent.
3. New worktrees running `scripts/setup-worktree-env.sh` pick up the new baseline automatically.
4. Developers who want to migrate an existing `.env` edit one line: `NGINX_PORT=80` → `NGINX_PORT=8240` (plus their offset, if any). No data migration, no rebuild required.
5. Rollback: revert the commit. `scripts/up.sh` becomes a no-op file to delete; the `NGINX_PORT` default flips back to `80`. No persistent state is touched.

## Open Questions

- Should `scripts/up.sh` also check the stack's health (e.g. `docker compose ps --format json` and verify all services are `running`) before printing the banner? Leaning yes — a banner printed while core-api is still restarting is misleading. Default to "yes, with a short timeout (~30s)"; the spec's scenarios can be adjusted in implementation if this proves flaky.
- Should `AGENTS.md` get a dedicated "Developer entry points" subsection, or a paragraph in the existing dev-env section? Deferring to tasks.md / implementation time — either is fine.
