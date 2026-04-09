## Why

Customer auth (SMS OTP) is complete, but staff cannot log in or be authorized — there is no `staff_accounts` table, no login/password endpoint, and no RBAC middleware. Per PDD §7.1, staff auth is Phase 1 step 4–5 and blocks all subsequent phases (menu management, orders, admin panel). Without it, INV-002 (server-side auth on all mutations) and INV-010 (role isolation) cannot be enforced.

## What Changes

- Add `staff_accounts` table with login/password credentials and role enum (`admin`, `barista`, `courier`)
- Add `POST /api/v1/staff/auth/login` and `POST /api/v1/staff/auth/logout` endpoints (password-based, JWT issuance with staff role)
- Add `POST /api/v1/staff/auth/refresh` endpoint for staff token refresh
- Add `StaffRole` enum to `packages/shared/`
- Add `require_role(*roles)` FastAPI dependency for RBAC enforcement on protected endpoints
- Add staff session management via Redis (refresh tokens, same pattern as customer auth)
- **BREAKING**: All future staff-facing endpoints will require role-based authorization

## Non-Goals

- Customer-facing auth changes — customer SMS OTP flow is complete and unchanged
- Admin panel UI (login screen, dashboard) — belongs to a separate `web-admin` change
- Staff CRUD (creating/editing/deactivating staff accounts) — separate admin-panel capability; initial staff seeded via migration
- Password reset/recovery flow — out of scope for MVP; staff passwords managed by admin
- Multi-factor authentication for staff — not required at MVP stage

## MVP Phase

Phase 1: Auth (PDD §7.1) — steps 4 and 5. This is the final Phase 1 deliverable before Phase 2 (Menu & Cart) can begin.

## Capabilities

### New Capabilities

- `staff-auth`: Staff login/password authentication — endpoints, JWT issuance with role, session management
- `rbac`: Role-based access control middleware — `require_role()` dependency, role enforcement on protected endpoints per INV-010

### Modified Capabilities

- `user-models`: Add `staff_accounts` table and `StaffRole` enum to the data model

## Impact

- **core-api**: New auth router (`routers/staff_auth.py`), new RBAC dependency (`deps/rbac.py`), password hashing dependency (e.g., `bcrypt`)
- **shared**: New `StaffRole` enum
- **database**: New migration for `staff_accounts` table + seed data for initial admin account
- **redis**: Staff refresh token storage (same key pattern as customers, namespaced)
- **Dependencies**: `bcrypt` or `passlib[bcrypt]` added to core-api requirements
