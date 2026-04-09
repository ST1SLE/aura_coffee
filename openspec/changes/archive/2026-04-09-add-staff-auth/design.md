## Affected Modules

`[core-api]` `[shared]` `[database]` `[redis]`

## Context

Customer auth (SMS OTP) is fully implemented: JWT access tokens (HS256, 15 min TTL), Redis-backed refresh tokens (7 day TTL, rotation on use), `get_current_user` dependency. However, role is hardcoded to `"customer"` and there is no RBAC enforcement. Staff cannot log in — no `staff_accounts` table, no login/password flow, no role-based guards.

Per PDD §7.1 Phase 1 (steps 4–5), staff auth and RBAC middleware MUST be completed before any Phase 2 work. INV-002 requires server-side auth on all mutations; INV-010 requires strict role isolation (barista MUST NOT access menu management, users, promocodes, settings; courier MUST NOT access anything except delivery orders and status changes).

## Goals / Non-Goals

**Goals:**
- Staff login/password authentication with JWT issuance containing staff role
- Reusable `require_role()` dependency for role-based endpoint protection
- `staff_accounts` table with bcrypt-hashed passwords and role enum
- Staff session management via Redis (same refresh token pattern as customers)

**Non-Goals:**
- Admin panel UI (separate change)
- Staff CRUD endpoints (separate change; initial admin seeded via migration)
- Password reset/recovery
- Customer auth modifications

## Decisions

### D1: Separate `staff_accounts` table (not extending `users`)

Staff authenticate via login/password, customers via SMS OTP. These are fundamentally different auth flows with different schemas (login+password_hash vs phone_hash). PDD §5.1 defines them as separate tables.

**Alternative considered**: Single `users` table with optional fields. Rejected because it violates PDD schema design, mixes PII models, and complicates 152-FZ compliance (INV-013).

### D2: bcrypt for password hashing

Use `bcrypt` via the `bcrypt` package (not `passlib`). bcrypt is the industry standard, has built-in salt, and `passlib` is unmaintained.

**Alternative considered**: `argon2-cffi`. Better in theory but adds a C dependency and bcrypt is sufficient for a staff-only system with ~5 accounts.

### D3: Same JWT structure, namespaced by role type

Staff JWTs SHALL use the same HS256 signing key and structure (`sub`, `role`, `iat`, `exp`) as customer tokens. The `role` field differentiates: `"customer"` vs `"admin"` / `"barista"` / `"courier"`. The existing `get_current_user` dependency continues to decode any valid JWT — RBAC enforcement is layered on top via `require_role()`.

**Alternative considered**: Separate signing keys for staff vs customer. Rejected as unnecessary complexity — role-based guards are sufficient, and a single key simplifies rotation.

### D4: `require_role()` as composable FastAPI dependency

`require_role(*allowed_roles)` SHALL return a FastAPI `Depends` that:
1. Calls `get_current_user` to extract the authenticated user
2. Checks `user.role` against `allowed_roles`
3. Returns 403 if role is not in the allowed set

This composable approach lets endpoints declare `Depends(require_role("admin"))` or `Depends(require_role("admin", "barista"))`.

**Alternative considered**: Middleware-based approach checking route metadata. Rejected because FastAPI dependency injection is more explicit, testable, and idiomatic.

### D5: Staff refresh tokens namespaced in Redis

Staff refresh tokens SHALL use key pattern `staff_refresh:{token}` (vs `refresh:{token}` for customers). Same TTL (7 days), same rotation-on-use logic. This prevents token collision and allows independent invalidation.

### D6: Initial admin seeded via migration

The Alembic migration SHALL insert one admin account with login from `ADMIN_LOGIN` env var and password from `ADMIN_PASSWORD` env var (bcrypt-hashed at migration time). This bootstraps the system without requiring a staff CRUD endpoint. Per INV-015, credentials MUST come from environment variables.

## Migration Strategy

**Forward migration**:
1. Create PostgreSQL enum type `staff_role` with values `admin`, `barista`, `courier`
2. Create `staff_accounts` table
3. Seed initial admin account from env vars

**Rollback**:
1. Drop `staff_accounts` table
2. Drop `staff_role` enum type

No data backfill needed — this is a new table with no existing data.

## Risks / Trade-offs

- **[Risk] Single JWT signing key for staff and customers** → If key is compromised, both systems are affected. Mitigation: key rotation via env var (`JWT_SECRET`), short access token TTL (15 min). Acceptable for MVP.
- **[Risk] Initial admin password in env var** → Must be changed after first deploy. Mitigation: document in deployment guide; admin CRUD (future change) will allow password changes.
- **[Risk] No brute-force protection on staff login** → Rate limiting is not yet implemented. Mitigation: staff login endpoint is internal-facing; add rate limiting in a separate change when Redis rate-limiting is implemented.

## Open Questions

None — all decisions are straightforward applications of existing patterns and PDD requirements.
