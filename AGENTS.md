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
cp .env.example .env                                           # TEST_DATABASE_URL is pre-set
docker compose up -d postgres redis
docker compose exec core-api pytest services/core-api/tests/ -v
```

The test database `aura_coffee_test` is auto-created on first run by the `_ensure_test_database` fixture in `services/core-api/tests/conftest.py`. Migrations are schema-only — they run without any application env vars (no `ADMIN_LOGIN`, no `ADMIN_PASSWORD`). Seed data lives in `database/seeds/`. See `services/core-api/AGENTS.md` for fixture details and `database/AGENTS.md` for the migration/seed contract.

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
