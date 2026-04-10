# Aura Coffee

Web platform for a local coffee shop — online ordering with pickup and own-courier delivery. Production system for a real coffee shop. Single location, single menu, no multitenancy.

**Authoritative design doc:** `docs/PRODUCT_DESIGN_DOCUMENT.md`

## Tech Stack

- **Backend:** Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.0 (sync) + Alembic, Celery + Redis, PyJWT
- **Frontend:** React 19 + TypeScript, Vite, Tailwind CSS, shadcn/ui, react-i18next, React Router
- **API client:** Auto-generated from FastAPI OpenAPI spec
- **Data:** PostgreSQL 16, Redis 7
- **Infra:** Docker + Docker Compose, Nginx
- **Testing:** pytest + httpx (backend), Vitest (frontend)

## Module Map

| Directory | Module Tag | Purpose |
|-----------|-----------|---------|
| `services/core-api/` | `[core-api]` | FastAPI HTTP server — business logic, CRUD, auth, all state mutations |
| `services/payment-worker/` | `[payment-worker]` | Celery worker — YuKassa payments, webhooks, refunds |
| `services/sms-worker/` | `[sms-worker]` | Celery worker — SMS.ru OTP codes, order notifications |
| `web/customer/` | `[web-customer]` | React SPA — customer-facing: menu, cart, checkout, profile |
| `web/admin/` | `[web-admin]` | React SPA — staff panel: admin, barista, courier views |
| `packages/shared/` | `[shared]` | Shared Python package — domain models, enums, constants, validation |
| `database/` | `[database]` | Alembic migrations, seeds, schema |

## Cross-Cutting Constraints

These Inviolable Rules apply to ALL modules. See PDD §2 for full definitions.

- **INV-002 — Auth for mutations:** All state-mutating operations MUST require server-side authentication and role-based authorization. Client-side auth checks are NOT sufficient.
- **INV-004 — Atomic financials:** Points redemption, promo application, and payment creation MUST be wrapped in a single DB transaction. Partial state (points deducted, payment failed) is FORBIDDEN.
- **INV-013 — PII isolation:** Personal data (phone, name, addresses) MUST be stored separately from order data. Tables reference users by opaque UUID. Account deletion MUST anonymize PII while preserving order history.
- **INV-014 — Immutable order items:** UPDATE and DELETE on `order_items` are FORBIDDEN. Order items are snapshots of prices/names at time of order.
- **INV-015 — Secrets out of code:** All API keys, secrets, and connection strings MUST be in environment variables. Never in source code, git history, or config files.
- **INV-016 — Explicit state transitions only:** State machines in PDD §6 are exhaustive. Any transition NOT listed is FORBIDDEN. Do not invent, add, or imply transitions.

## State Machines

All state machines are defined in PDD §6. Reference them by section:

- §6.1 — Order Lifecycle (CREATED → PAID → PREPARING → READY → IN_DELIVERY → COMPLETED / CANCELLED)
- §6.2 — Payment Lifecycle (PENDING → AWAITING_CONFIRMATION → SUCCEEDED → REFUND_PENDING → REFUNDED)
- §6.3 — Delivery Assignment (AWAITING_COURIER → COURIER_ASSIGNED → PICKED_UP → DELIVERED)
- §6.4 — SMS OTP (CREATED → SENT → VERIFIED / EXPIRED / FAILED)
- §6.5 — User Account (PENDING_VERIFICATION → ACTIVE → BLOCKED → DELETED)
- §6.6 — Promocode (DRAFT → ACTIVE → PAUSED → EXPIRED / EXHAUSTED)

## Development Methodology: TDD

This project follows Test-Driven Development for all backend code.

### Worktree Testing Workflow

Every worktree — new or existing — runs tests the same way, with zero manual setup beyond copying `.env.example`:

```bash
./scripts/setup-worktree-env.sh                                # writes .env with a collision-free port offset
./scripts/up.sh                                                # brings the full stack up and prints the real host URLs
docker compose exec core-api pytest services/core-api/tests/ -v
```

`setup-worktree-env.sh` derives a deterministic starting offset from `sha1(worktree_path)`, probes the 6 candidate host ports against `127.0.0.1`, and bumps by +10 on collision until a free set is found (max 20 attempts). Idempotent — re-run it any time another stack comes up and collides. The plain `cp .env.example .env` still works for a single-worktree setup.

`up.sh` is a thin wrapper over `docker compose up -d` that reads `.env` after the stack is up and prints a banner with the actual host-side URLs: the canonical nginx entry point, plus direct customer / admin / core-api URLs. Extra args are forwarded verbatim (e.g. `./scripts/up.sh --build core-api`).

### Canonical local entry point: always nginx

For browsing the site, use `http://localhost:${NGINX_PORT}/` — that is the canonical local entry point. The `.env.example` default is `NGINX_PORT=8240` (non-privileged), so `docker compose up` binds nginx without needing root.

**IGNORE the Vite log URLs.** The `web-customer` and `web-admin` containers print lines like:

```
Local:   http://localhost:5173/
```

Those ports are the **container-internal** ports — they are NOT your host ports when you have bumped host ports per worktree (`WEB_CUSTOMER_PORT`, `WEB_ADMIN_PORT`). Following those URLs on the host produces "connection refused". Use the URLs printed by `./scripts/up.sh`, or open `http://localhost:${NGINX_PORT}/`.

The test database `aura_coffee_test` is auto-created on first run by the `_ensure_test_database` fixture in `services/core-api/tests/conftest.py`. Migrations are schema-only — they run without any application env vars (no `ADMIN_LOGIN`, no `ADMIN_PASSWORD`). Seed data lives in `database/seeds/`. See `services/core-api/AGENTS.md` for fixture details and `database/AGENTS.md` for the migration/seed contract.

### Running multiple worktrees at once

Each worktree that brings up the docker stack binds host ports. Two worktrees cannot share the same host ports. All host bindings are templated in `docker-compose.yml` as `${VAR:-default}` so each worktree can override them in its own `.env` (which is git-ignored).

The ports to override are listed at the bottom of `.env.example` under `# Host port bindings`:

```
POSTGRES_PORT, REDIS_PORT, CORE_API_PORT, WEB_CUSTOMER_PORT, WEB_ADMIN_PORT, NGINX_PORT
```

Convention: pick an offset per worktree and add it to every port. E.g. your second worktree uses offset `+10` → `5443 / 6389 / 8010 / 5183 / 5184 / 90`. Your third uses `+20`. Consistency keeps the math easy when you need to curl a specific service.

Caveat: `CORS_ORIGINS` in `.env` hardcodes `5173,5174`. If you change `WEB_CUSTOMER_PORT` or `WEB_ADMIN_PORT` in a worktree, also update `CORS_ORIGINS` to match — otherwise browser requests to the admin/customer SPAs will be rejected.

### The Two-Change Model

Every backend feature is split into two sequential OpenSpec changes:

| Change | Phase | Contains | End State |
|--------|-------|----------|-----------|
| `<name>-red` | RED | PREREQ + RED tasks | All tests exist and FAIL |
| `<name>-green` | GREEN | GREEN + REFACTOR + MIGRATE + VERIFY | All tests PASS |

Both changes land on the same feature branch, applied sequentially.
The branch is only considered complete when the GREEN change passes.

### Task Type Prefixes

| Prefix | Meaning | TDD Phase |
|--------|---------|-----------|
| `RED` | Write failing test | Red |
| `GREEN` | Write minimal code to pass test | Green |
| `REFACTOR` | Clean up, no behavior change | Refactor |
| `PREREQ` | Dependencies, config (no test) | Setup |
| `MIGRATE` | Alembic migration | Green |
| `VERIFY` | Run and confirm (migration, full suite) | Green |
| `IMPL` | Frontend component (test follows) | Frontend |
| `TEST` | Frontend test after implementation | Frontend |

### REFACTOR Granularity

- Group has ≥3 RED tests OR >50% RED density → one REFACTOR at end of group
- Otherwise → REFACTOR after each GREEN

### Frontend Exception

Frontend modules (`[web-customer]`, `[web-admin]`) use lighter TDD:
- **Logic** (hooks, utils, API clients, state management): RED → GREEN → REFACTOR
- **UI** (components, pages): IMPL → TEST → REFACTOR
- **Pure presentation**: tests optional
- Frontend changes are NOT split into two changes.

## General Rules

- Prices are stored as integers in kopecks (1₽ = 100). Display conversion is frontend responsibility.
- All timestamps are UTC (`TIMESTAMPTZ`). Timezone conversion is frontend responsibility.
- Bilingual: all user-facing text has RU + EN variants. DB fields: `name_ru`, `name_en`.
- Domain language is strict — use terms from PDD §3. Inconsistent naming is a bug.
