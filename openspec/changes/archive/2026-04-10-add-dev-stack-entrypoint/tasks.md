<!--
Note on module tags: this change is pure dev infrastructure (scripts, compose
defaults, .env.example, AGENTS.md). None of the enumerated service tags
([core-api], [web-customer], etc.) apply. Tasks use [infra] as an out-of-band
tag to keep the rule's intent (per-module scoping) while reflecting reality.

Note on TDD prefixes: no backend or frontend code changes. All work is shell
scripts and static config/docs. PREREQ (config/script files with no unit
test) and VERIFY (manual end-to-end confirmation) are used throughout.
-->

## 1. NGINX_PORT default flip

- [x] 1.1 [infra] PREREQ: Update `.env.example` — change `NGINX_PORT=80` to `NGINX_PORT=8240`. Add an inline comment in the `# Host port bindings` section identifying `http://localhost:${NGINX_PORT}/` as the canonical local entry point and warning that Vite log URLs (`localhost:5173` / `localhost:5174`) are container-internal.
- [x] 1.2 [infra] PREREQ: Update `docker-compose.yml` — change the `nginx` service port mapping fallback from `${NGINX_PORT:-80}:80` to `${NGINX_PORT:-8240}:80`. No other compose changes.
- [x] 1.3 [infra] VERIFY: With a fresh `.env` copied from `.env.example` (no customizations), run `docker compose up -d nginx` and confirm nginx binds on host port `8240`. Run `curl -I http://localhost:8240/` and confirm a response comes back (2xx/3xx/4xx — the point is the TCP connection succeeds, not what the app returns).

## 2. scripts/up.sh wrapper

- [x] 2.1 [infra] PREREQ: Create `scripts/up.sh` with `set -euo pipefail`, executable bit set. The script MUST:
  - Verify a `.env` file exists in the repo root (resolved via `$(git rev-parse --show-toplevel)` or `dirname` of the script, not `$PWD`). If missing, print an actionable error pointing at `scripts/setup-worktree-env.sh` and exit non-zero.
  - Run `docker compose up -d "$@"` so extra args are forwarded.
  - Parse `WEB_CUSTOMER_PORT`, `WEB_ADMIN_PORT`, `CORE_API_PORT`, `NGINX_PORT` from `.env` via `grep -E '^VAR=' | cut -d= -f2-`. MUST NOT `source` or `export` the file (avoids executing `.env` content as shell).
  - After compose succeeds, wait for the stack to become healthy with a bounded timeout (~30s, polling `docker compose ps --format json`). If timeout is exceeded, still print the banner but prefix it with a "services may still be starting" note.
  - Print a boxed banner listing, in this order: canonical entry point (`http://localhost:${NGINX_PORT}/`), direct customer (`http://localhost:${WEB_CUSTOMER_PORT}/`), direct admin (`http://localhost:${WEB_ADMIN_PORT}/`), direct core API (`http://localhost:${CORE_API_PORT}/`).
  - End the banner with an explicit warning line: the `localhost:5173` / `localhost:5174` URLs printed by Vite inside `web-customer` / `web-admin` containers are container-internal and MUST be ignored.
- [x] 2.2 [infra] VERIFY: In a worktree with non-default ports (e.g. `WEB_CUSTOMER_PORT=5333`, `WEB_ADMIN_PORT=5334`, `CORE_API_PORT=8160`, `NGINX_PORT=8240`), run `./scripts/up.sh` and confirm the banner contains the four URLs above with those exact host ports. Open `http://localhost:5333/` in a browser and confirm the customer app loads (not "connection refused").
- [x] 2.3 [infra] VERIFY: In a worktree with no `.env` file, run `./scripts/up.sh` and confirm it exits non-zero without invoking `docker compose`, and the error message instructs the developer to run `scripts/setup-worktree-env.sh`.
- [x] 2.4 [infra] VERIFY: Run `./scripts/up.sh --build core-api` and confirm the underlying `docker compose up -d` receives `--build core-api` (core-api image is rebuilt) and the banner still prints on success.
- [x] 2.5 [infra] VERIFY: Create a throwaway `.env` entry containing a value with `=` inside it (e.g. `SOME_VAR=a=b`), re-run `./scripts/up.sh`, and confirm the banner still prints correctly. This confirms the `cut -d= -f2-` parse is robust.

## 3. Documentation

- [x] 3.1 [infra] PREREQ: Update `AGENTS.md` dev-env section to document the Vite log footgun: state that `scripts/up.sh` prints the real host URLs and that the `localhost:5173` / `localhost:5174` lines from `web-customer` / `web-admin` container logs MUST NOT be followed. State that `http://localhost:${NGINX_PORT}/` is the canonical local entry point.
- [x] 3.2 [infra] VERIFY: Read the updated `AGENTS.md` and `.env.example` end-to-end and confirm both documents consistently identify the canonical entry point and warn about the Vite log URLs. Any contradiction between the two files is a failure.

## 4. Spec + change archival readiness

- [x] 4.1 [infra] VERIFY: Run `openspec validate add-dev-stack-entrypoint` (or project equivalent) and confirm the proposal, design, specs delta, and tasks parse cleanly. Fix any validation errors surfaced.
- [x] 4.2 [infra] VERIFY: Confirm no changes were made to `core-api`, `payment-worker`, `sms-worker`, `shared`, `database/`, or any Python/TypeScript source file. The diff SHOULD touch only `scripts/up.sh` (new), `.env.example`, `docker-compose.yml`, `AGENTS.md`, and files under `openspec/changes/add-dev-stack-entrypoint/`.
