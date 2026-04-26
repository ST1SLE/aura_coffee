# Core API

FastAPI HTTP server — the central application server handling all client and admin requests. Owns all business logic, CRUD operations, session management, and authorization.

**PDD sections:** §4.1 (boundaries), §6 (all state machines), §7 (all workflows)

## Tech Stack

- Python 3.12+, FastAPI, Pydantic v2
- SQLAlchemy 2.0 (sync) for DB access
- Redis for cart, sessions, rate-limiting
- PyJWT for authentication
- pytest + httpx for testing

## Scope

This module is responsible for:
- All HTTP API endpoints (customer + admin)
- Business logic: order pricing (§7.2), address validation (§7.3), delivery fee (§7.4), time slot validation (§7.5), cancellation (§7.6), repeat order (§7.7)
- State machine transitions for all entities (§6.1–§6.6)
- Authentication: SMS OTP for customers, login/password for staff
- Authorization: role-based access control (customer, admin, barista, courier)
- Rate-limiting for SMS OTP requests (INV-012)
- Cart management via Redis
- Enqueuing tasks for payment-worker and sms-worker via Celery

## Constraints

- **No synchronous external API calls** in request handlers, EXCEPT Yandex.Maps Suggest API (≤ 500ms acceptable latency). Payments and SMS are delegated to workers via Celery queue.
- **Latency SLA:** All endpoints ≤ 1000ms (p95). Critical path (order creation, webhook processing) ≤ 500ms (p95). Tasks enqueued to Celery MUST be picked up within 5s.
- **INV-002:** Every state-mutating endpoint MUST check authentication and role server-side.
- **INV-004:** Financial mutations (points + promo + payment) MUST be in a single DB transaction.
- **INV-006:** Stop-list validation MUST be server-side. Client-side checks are UX only.
- **INV-010:** Role isolation — barista cannot manage menu/users/promos; courier sees only delivery orders.

## Key Files

_(to be updated as code is added)_

## Testing

- **Framework:** pytest + httpx
- **Canonical runner:** `docker compose exec core-api pytest services/core-api/tests/ -v`
- **Test files:** `tests/test_<module>.py` mirrors `src/core_api/<module>.py`
- **Redis:** use `fakeredis` — no real Redis in tests
- **Mocks:** mock external boundaries (Celery task dispatch, SMS API), NOT internal services
- **Methodology:** GRACE — verification via standard pytest plus optional LDD log assertions (`grace_logs` fixture in this module's `tests/conftest.py`). Required log markers per `docs/verification-plan.xml` V-M-CORE-API. Old RED/GREEN discipline retired; see root `AGENTS.md` and `MIGRATION_LOG.md`.

### Database fixtures

Two fixture tiers. Pick the lightest one that works.

1. **Default — sqlite in-memory.** Most tests (services, schemas, RBAC, auth logic) run against `sqlite://` via the `DATABASE_URL=sqlite://` default set in `conftest.py`. Fast, zero setup, no Postgres required.
2. **Postgres — `migrated_db_session`.** Tests that exercise models, ORM relationships, or migrations depend on this module-scoped fixture. It:
   - Reads `TEST_DATABASE_URL` (from `.env`, which you copied from `.env.example`).
   - Auto-creates `aura_coffee_test` via `_ensure_test_database` if it does not exist yet (maintenance connection to the `postgres` admin DB).
   - Runs `alembic upgrade head` against the test DB.
   - Yields a SQLAlchemy `Session` and rolls it back on teardown.
   - Skips entirely if `TEST_DATABASE_URL` is unset — conftest falls back to `sqlite://`, **never** to `DATABASE_URL`, so there is no path to corrupt the dev DB.

### Worktree testing workflow

A brand-new worktree is expected to run tests with zero troubleshooting:

```bash
cp .env.example .env                        # has TEST_DATABASE_URL pre-set
docker compose up -d postgres redis         # or the full stack
docker compose exec core-api pytest services/core-api/tests/ -v
```

On the first run the fixture creates `aura_coffee_test` and migrates it (~2s one-off). Subsequent runs reuse the DB. To reset:

```bash
docker compose exec postgres dropdb -U aura aura_coffee_test
```

## This Module MUST NOT

- Store or process audio/video files
- Call YuKassa API directly (delegate to payment-worker)
- Send SMS directly (delegate to sms-worker)
- Serve static frontend files in production (Nginx handles this)
