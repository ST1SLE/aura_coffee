# Shared Package

Internal Python package containing domain models, enums, constants, and validation rules shared across all backend services (core-api, payment-worker, sms-worker).

**PDD sections:** §3 (Domain Language), §6 (State Machines — enum definitions)

## Tech Stack

- Python 3.12+, Pydantic v2
- pytest for testing

## Scope

This module is responsible for:
- Pydantic models for domain entities (shared request/response schemas)
- Enum definitions for all state machines: OrderStatus, PaymentStatus, DeliveryStatus, OTPStatus, UserStatus, PromocodeStatus
- Domain constants: role names, loyalty calculation rules, SMS templates, rate-limit thresholds
- Pure validation functions (e.g., phone format, promo code format)
- Type definitions shared between services

## Constraints

- **Pure domain types only.** This package MUST NOT contain:
  - Business logic (order pricing, cancellation chains — that's core-api)
  - Database sessions or ORM models (that's each service's responsibility)
  - API-specific code (route handlers, middleware)
  - External API clients (YuKassa, SMS.ru, Yandex.Maps)
  - Configuration or environment variable reading
- **Changes here affect all backend services.** Any modification to shared types requires awareness that core-api, payment-worker, and sms-worker all depend on this package. Breaking changes must be coordinated.
- **State machine enums MUST match PDD §6 exactly.** Enum values are the source of truth for valid states and transitions. Adding/removing values requires PDD update first.

## Key Files

_(to be updated as code is added)_

## Testing

- **Framework:** pytest
- **Runner:** `pytest packages/shared/tests/ -v`
- **Test files:** `tests/test_<module>.py`
- **Scope:** pure unit tests only — no DB, no Redis, no network
- **Methodology:** GRACE — verification via standard pytest plus optional LDD log assertions (`grace_logs` fixture). Old RED/GREEN discipline retired in CP6 of GRACE migration; see root `AGENTS.md` and `MIGRATION_LOG.md`.

## This Module MUST NOT

- Import from core-api, payment-worker, or sms-worker (dependency flows one way: services → shared)
- Connect to databases or Redis
- Make HTTP requests
- Contain FastAPI or Celery dependencies
