## 1. Shared Enums

- [x] 1.1 [shared] Add `StaffRole` enum (ADMIN, BARISTA, COURIER) to `packages/shared/src/shared/enums.py`

## 2. Database Schema

- [x] 2.1 [shared] Add `StaffAccount` SQLAlchemy model to shared models (id, login, password_hash, role, display_name, is_active, created_at, updated_at)
- [x] 2.2 [database] Create Alembic migration: `staff_role` enum type + `staff_accounts` table + unique index on `login`
- [x] 2.3 [database] Add admin seed logic to migration: read `ADMIN_LOGIN` / `ADMIN_PASSWORD` env vars, bcrypt-hash password, insert initial admin row

## 3. Dependencies

- [x] 3.1 [core-api] Add `bcrypt` to core-api requirements/dependencies

## 4. Staff Auth Service

- [x] 4.1 [core-api] Create `services/staff_auth.py`: password verification (bcrypt), JWT issuance with staff role, refresh token create/rotate/delete in Redis (key pattern `staff_refresh:{token}`)

## 5. Staff Auth Pydantic Schemas

- [x] 5.1 [core-api] Create Pydantic request/response schemas for staff auth: `StaffLoginRequest`, `StaffTokenResponse`, `StaffRefreshRequest`, `StaffLogoutRequest`

## 6. Staff Auth Router

- [x] 6.1 [core-api] Create `routers/staff_auth.py` with `POST /api/v1/staff/auth/login` endpoint
- [x] 6.2 [core-api] Add `POST /api/v1/staff/auth/refresh` endpoint to staff auth router
- [x] 6.3 [core-api] Add `POST /api/v1/staff/auth/logout` endpoint to staff auth router (requires valid JWT)
- [x] 6.4 [core-api] Register staff auth router in FastAPI app

## 7. RBAC Middleware

- [x] 7.1 [core-api] Create `deps/rbac.py` with `require_role(*allowed_roles)` dependency that calls `get_current_user` and checks role against allowed set, returning 403 on mismatch

## 8. Tests

- [x] 8.1 [core-api] Write tests for staff login: valid credentials, wrong password, non-existent login, inactive account
- [x] 8.2 [core-api] Write tests for staff token refresh: valid refresh, expired token, replayed token
- [x] 8.3 [core-api] Write tests for staff logout: successful logout, unauthenticated request
- [x] 8.4 [core-api] Write tests for `require_role`: authorized role, unauthorized role, no auth header, customer role denied on staff endpoint
