## Why

Vite dev servers inside the `web-customer` and `web-admin` containers log `Local: http://localhost:5173/` (and `5174`), but those ports are the *container-internal* ports — the host-side ports are whatever `WEB_CUSTOMER_PORT` / `WEB_ADMIN_PORT` are set to in `.env`, which per the worktree-safety guardrail (`.env.example`) are bumped per worktree. Following the log leads to "connection refused" because nothing is listening on `localhost:5173` on the host. On top of that, the default `NGINX_PORT=80` is a privileged port, so the documented "one entry point via nginx" story is fragile on developer machines.

## What Changes

- Add `scripts/up.sh`: a thin wrapper around `docker compose up -d` that reads `.env` after the stack is healthy and prints a banner with the *actual* host URLs (customer, admin, core-api, nginx entry point). This becomes the documented way to bring the stack up locally.
- **BREAKING (dev only)**: Change the `NGINX_PORT` default in `.env.example` from `80` to `8240` so nginx binds to a non-privileged port by default. `docker-compose.yml` default fallback updated to match.
- Establish nginx on `http://localhost:${NGINX_PORT}` as the canonical local entry point for browsing the site. Direct Vite ports (`WEB_CUSTOMER_PORT`, `WEB_ADMIN_PORT`) remain exposed for debugging but are no longer the recommended access path.
- Update `.env.example` comments and `AGENTS.md` dev-env section to state explicitly: "Ignore the `localhost:5173` / `localhost:5174` lines in web-customer / web-admin container logs — those are container-internal. Use the URLs printed by `scripts/up.sh`, or open `http://localhost:${NGINX_PORT}`."

## Capabilities

### New Capabilities
<!-- None — this change extends existing dev-env capability. -->

### Modified Capabilities
- `docker-dev-env`: Add a requirement that a `scripts/up.sh` wrapper exists and prints the host-side URLs derived from `.env` after the stack is up. Update the "Environment configuration" requirement to document `NGINX_PORT=8240` as the new default and nginx as the canonical local entry point.

## Impact

- **Affected files**: `scripts/up.sh` (new), `.env.example` (default + comments), `.env` (developer-local, not committed), `docker-compose.yml` (`NGINX_PORT` default fallback `:-80` → `:-8240`), `AGENTS.md` (dev-env note on Vite log ports).
- **Affected workflows**: Local developer onboarding and per-worktree stack bring-up. No production impact — `scripts/up.sh` is a dev convenience wrapper and `NGINX_PORT` is overridable per environment.
- **No impact** on `core-api`, workers, database schema, Celery, or any business logic. No runtime behavior of shipped services changes.
- **MVP phase**: Cross-cutting dev infrastructure — supports all Phases 1–6 (section 7.1). Not tied to a specific feature phase; unblocks developer velocity across all phases.
- **Inviolable rules**: No INV-XXX impact. Secrets handling (INV-015) unchanged — `.env` remains the sole secret source and is not read by the wrapper beyond port variables.

## Non-Goals

- **Not** changing production nginx configuration, TLS, or deployment topology. This is strictly the local dev `docker compose` path.
- **Not** fixing the `web/admin/vite.config.ts` missing `/api` proxy or the nginx `/admin` base-path routing issue. Those are known separate problems; this change routes users through nginx where the customer app works, and leaves admin-via-nginx for a follow-up change.
- **Not** introducing a process manager, Makefile, or task runner (`just`, `taskfile`, etc.). A single shell script is sufficient.
- **Not** auto-generating or rewriting `.env` from `.env.example`. Developers still copy and edit it themselves per the existing worktree guardrail.
- **Not** suppressing or rewriting Vite's own log output. The fix is to give developers a louder, correct signal via `scripts/up.sh` and documentation, not to fight Vite.
