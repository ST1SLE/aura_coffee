## ADDED Requirements

### Requirement: Root AGENTS.md exists with project overview
The repo SHALL contain a root `AGENTS.md` that provides project summary, tech stack, module map (directory → purpose → openspec tag), and cross-cutting Inviolable Rules (INV-002, INV-004, INV-013, INV-014, INV-015, INV-016). It SHALL reference PDD by section number, not duplicate content.

#### Scenario: Root AGENTS.md provides global context
- **WHEN** an agent starts working anywhere in the repo
- **THEN** it SHALL pick up root `AGENTS.md` with project overview and global constraints

#### Scenario: Root AGENTS.md does not duplicate PDD
- **WHEN** a developer reads root `AGENTS.md`
- **THEN** it SHALL contain PDD section references (e.g., "see §6.1") instead of restating PDD content

### Requirement: Core API AGENTS.md defines API server scope
`services/core-api/AGENTS.md` SHALL define scope as: FastAPI HTTP server, business logic, CRUD, sessions, authorization, all state mutations. It SHALL reference PDD §4.1, §6 (all state machines), §7 (all workflows). It SHALL declare that core-api MUST NOT call external APIs synchronously (except Yandex.Maps Suggest, per §4.1).

#### Scenario: Agent working in core-api knows its boundaries
- **WHEN** an agent works within `services/core-api/`
- **THEN** it SHALL have access to core-api AGENTS.md defining its scope, owned PDD sections, and forbidden actions

### Requirement: Payment Worker AGENTS.md defines payment scope
`services/payment-worker/AGENTS.md` SHALL define scope as: Celery worker for YuKassa API interaction. It SHALL reference PDD §4.2, §6.2 (Payment Lifecycle), §7.9 (Webhook Processing), §8.1 (YuKassa compliance). It SHALL enforce idempotency and webhook IP verification.

#### Scenario: Agent working in payment-worker knows YuKassa constraints
- **WHEN** an agent works within `services/payment-worker/`
- **THEN** it SHALL have access to payment-worker AGENTS.md with YuKassa-specific rules and lifecycle references

### Requirement: SMS Worker AGENTS.md defines notification scope
`services/sms-worker/AGENTS.md` SHALL define scope as: Celery worker for SMS.ru/SMSC. It SHALL reference PDD §4.3, §6.4 (OTP Lifecycle), §7.8 (SMS Delivery Chain), §8.2 (SMS.ru compliance). It SHALL enforce retry policy (3 attempts, exponential backoff).

#### Scenario: Agent working in sms-worker knows SMS constraints
- **WHEN** an agent works within `services/sms-worker/`
- **THEN** it SHALL have access to sms-worker AGENTS.md with SMS-specific rules and retry policy

### Requirement: Customer Frontend AGENTS.md defines client scope
`web/customer/AGENTS.md` SHALL define scope as: React SPA for customers. It SHALL reference PDD §4.4. It SHALL enforce: responsive mobile-first (320px min), bilingual RU/EN, all validation duplicated on server, prices always from server (never local calculation).

#### Scenario: Agent working in customer frontend knows UX constraints
- **WHEN** an agent works within `web/customer/`
- **THEN** it SHALL have access to customer AGENTS.md with responsive, i18n, and validation rules

### Requirement: Admin Panel AGENTS.md defines admin scope
`web/admin/AGENTS.md` SHALL define scope as: React SPA for staff (admin, barista, courier). It SHALL reference PDD §4.5 and INV-010 (role isolation). It SHALL enforce: role-filtered UI, server-side authorization for all actions, order feed polling/WebSocket for real-time updates.

#### Scenario: Agent working in admin panel knows role isolation rules
- **WHEN** an agent works within `web/admin/`
- **THEN** it SHALL have access to admin AGENTS.md with role isolation constraints from INV-010

### Requirement: Shared Package AGENTS.md defines library scope
`packages/shared/AGENTS.md` SHALL define scope as: domain models (Pydantic), enums, constants, validation rules. It SHALL enforce: no business logic, no DB sessions, no API-specific code, no external API calls. Changes to shared package affect all backend services.

#### Scenario: Agent working in shared package knows its restricted scope
- **WHEN** an agent works within `packages/shared/`
- **THEN** it SHALL have access to shared AGENTS.md restricting scope to pure domain types and validation

### Requirement: Database AGENTS.md defines migration scope
`database/AGENTS.md` SHALL define scope as: Alembic migrations and seed data. It SHALL reference PDD §5 (Data Storage Strategy), INV-013 (PII isolation), INV-014 (immutable order items). It SHALL enforce: migrations MUST be idempotent and reversible (§5.5), destructive migrations via two-phase process, prices in kopecks (integer), timestamps in UTC.

#### Scenario: Agent working in database knows migration rules
- **WHEN** an agent works within `database/`
- **THEN** it SHALL have access to database AGENTS.md with migration safety rules from §5.5

### Requirement: AGENTS.md hierarchy composes correctly
An agent working in a module directory SHALL receive both the root AGENTS.md (global constraints) and the module-specific AGENTS.md (local scope). The module AGENTS.md SHALL NOT contradict root AGENTS.md.

#### Scenario: Agent receives composed context
- **WHEN** an agent works within `services/payment-worker/`
- **THEN** it SHALL receive root AGENTS.md (INV rules, project overview) AND `services/payment-worker/AGENTS.md` (YuKassa scope) simultaneously
