# Aura Coffee

Production web platform for a single-location coffee shop — online ordering with pickup and own-courier delivery.

## Stack

Python 3.12 / FastAPI / Celery / SQLAlchemy / PostgreSQL 16 / Redis backend; React 19 / TypeScript / Vite / Tailwind frontend; nginx + docker compose for the local and production stack.

## Quickstart

```bash
cp .env.example .env
./scripts/setup-worktree-env.sh    # picks collision-free host ports
./scripts/up.sh                    # brings the full stack up
# Open http://localhost:${NGINX_PORT}/ — default 8240
```

## Architecture

| Path | Role |
|------|------|
| `services/core-api/` | FastAPI HTTP server (business logic, all state mutations) |
| `services/payment-worker/` | Celery worker for YuKassa payments |
| `services/sms-worker/` | Celery worker for SMS.ru OTP and notifications |
| `web/customer/` | React SPA for customers |
| `web/admin/` | React SPA for staff (admin / barista / courier) |
| `packages/shared/` | Shared Python package: domain enums + GRACE LDD logger |
| `database/` | Alembic migrations and seed scripts |

The authoritative product design doc is `docs/PRODUCT_DESIGN_DOCUMENT.md`.

## Methodology

This project uses [GRACE](https://github.com/osovv/grace-marketplace) (Graph-RAG Anchored Code Engineering). See `AGENTS.md` for the project-wide module map and `docs/*.xml` for the GRACE substrate (knowledge graph, development plan, verification plan, etc.). Migration history is in `MIGRATION_LOG.md`.

## License

See `LICENSE`.
