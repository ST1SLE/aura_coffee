## 1. Directory scaffolding — backend services

- [x] 1.1 [core-api] Create `services/core-api/src/.gitkeep`
- [x] 1.2 [core-api] Create `services/core-api/tests/.gitkeep`
- [x] 1.3 [payment-worker] Create `services/payment-worker/src/.gitkeep`
- [x] 1.4 [payment-worker] Create `services/payment-worker/tests/.gitkeep`
- [x] 1.5 [sms-worker] Create `services/sms-worker/src/.gitkeep`
- [x] 1.6 [sms-worker] Create `services/sms-worker/tests/.gitkeep`

## 2. Directory scaffolding — frontend apps

- [x] 2.1 [web-customer] Create `web/customer/src/.gitkeep`
- [x] 2.2 [web-admin] Create `web/admin/src/.gitkeep`

## 3. Directory scaffolding — shared, database, infra

- [x] 3.1 [shared] Create `packages/shared/src/.gitkeep`
- [x] 3.2 [shared] Create `packages/shared/tests/.gitkeep`
- [x] 3.3 [database] Create `database/migrations/.gitkeep`
- [x] 3.4 [database] Create `database/seeds/.gitkeep`
- [x] 3.5 Create `deploy/.gitkeep`
- [x] 3.6 Create `scripts/.gitkeep`

## 4. Root AGENTS.md

- [x] 4.1 Create root `AGENTS.md` with project summary, tech stack, module map, cross-cutting INV rules (INV-002, INV-004, INV-013, INV-014, INV-015, INV-016), and PDD reference

## 5. Backend service AGENTS.md files

- [x] 5.1 [core-api] Create `services/core-api/AGENTS.md` — scope: FastAPI server, PDD §4.1, §6, §7; constraint: no sync external API calls except Yandex.Maps Suggest
- [x] 5.2 [payment-worker] Create `services/payment-worker/AGENTS.md` — scope: Celery worker for YuKassa, PDD §4.2, §6.2, §7.9, §8.1; constraints: idempotency, webhook IP verification
- [x] 5.3 [sms-worker] Create `services/sms-worker/AGENTS.md` — scope: Celery worker for SMS.ru, PDD §4.3, §6.4, §7.8, §8.2; constraint: 3-retry exponential backoff

## 6. Frontend AGENTS.md files

- [x] 6.1 [web-customer] Create `web/customer/AGENTS.md` — scope: React SPA for customers, PDD §4.4; constraints: mobile-first 320px, bilingual, server-side validation, prices from server
- [x] 6.2 [web-admin] Create `web/admin/AGENTS.md` — scope: React SPA for staff, PDD §4.5, INV-010; constraints: role-filtered UI, server-side auth, real-time order feed

## 7. Shared and database AGENTS.md files

- [x] 7.1 [shared] Create `packages/shared/AGENTS.md` — scope: Pydantic models, enums, constants, validation; constraints: no business logic, no DB sessions, no API code
- [x] 7.2 [database] Create `database/AGENTS.md` — scope: Alembic migrations, seeds, PDD §5, INV-013, INV-014; constraints: idempotent/reversible migrations, two-phase destructive changes, prices in kopecks, UTC timestamps
