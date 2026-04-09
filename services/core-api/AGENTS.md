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
- **Runner:** `pytest services/core-api/tests/ -v`
- **Test files:** `tests/test_<module>.py` mirrors `src/core_api/<module>.py`
- **Redis:** use `fakeredis` — no real Redis in tests
- **DB:** test fixtures with test database (to be configured with CI)
- **Mocks:** mock external boundaries (Celery task dispatch, SMS API), NOT internal services
- **TDD:** full RED → GREEN → REFACTOR. Backend changes split into `-red` / `-green` changes.

## This Module MUST NOT

- Store or process audio/video files
- Call YuKassa API directly (delegate to payment-worker)
- Send SMS directly (delegate to sms-worker)
- Serve static frontend files in production (Nginx handles this)
