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

## General Rules

- Prices are stored as integers in kopecks (1₽ = 100). Display conversion is frontend responsibility.
- All timestamps are UTC (`TIMESTAMPTZ`). Timezone conversion is frontend responsibility.
- Bilingual: all user-facing text has RU + EN variants. DB fields: `name_ru`, `name_en`.
- Domain language is strict — use terms from PDD §3. Inconsistent naming is a bug.
