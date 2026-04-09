## 1. Route Protection Matrix

- [x] 1.1 [core-api] Create `services/core-api/src/core_api/rbac_matrix.py` with `ROUTE_MATRIX` dict mapping `(method, path_pattern)` → `set[str]` of allowed roles, and `PUBLIC_ROUTES` set for unauthenticated endpoints
- [x] 1.2 [core-api] Populate `ROUTE_MATRIX` with entries for all existing protected routes: `/api/v1/profile` (customer), `/api/v1/staff/auth/*` (public)
- [x] 1.3 [core-api] Populate `PUBLIC_ROUTES` with existing public endpoints: `GET /health`, `POST /api/v1/auth/send-code`, `POST /api/v1/auth/verify-code`, `POST /api/v1/auth/refresh`, `POST /api/v1/auth/logout`, `POST /api/v1/staff/auth/login`, `POST /api/v1/staff/auth/refresh`, `POST /api/v1/staff/auth/logout`

## 2. Middleware Implementation

- [x] 2.1 [core-api] Create `services/core-api/src/core_api/middleware/__init__.py` package
- [x] 2.2 [core-api] Create `services/core-api/src/core_api/middleware/rbac.py` with `RBACMiddleware(BaseHTTPMiddleware)` — implements path matching, JWT extraction via `AuthService.decode_access_token()`, role check against matrix, OPTIONS passthrough, and default-deny
- [x] 2.3 [core-api] Implement longest-prefix path matching helper in `middleware/rbac.py` that converts `{param}` patterns to regex and matches most specific route first

## 3. Middleware Registration

- [x] 3.1 [core-api] Register `RBACMiddleware` in `services/core-api/src/core_api/main.py` — add before CORSMiddleware so CORS runs first on requests (Starlette LIFO order)

## 4. Router Cleanup

- [x] 4.1 [core-api] Remove `Depends(require_role(...))` and inline role checks from `services/core-api/src/core_api/routers/profile.py`

## 5. Tests

- [x] 5.1 [core-api] Create `services/core-api/tests/test_rbac_middleware.py` — test valid role access, invalid role (403), missing token (401), expired token (401), OPTIONS bypass, default-deny for unlisted routes
- [x] 5.2 [core-api] Create `services/core-api/tests/test_rbac_matrix.py` — test path matching logic: exact match, parameterized paths, longest-prefix precedence
- [x] 5.3 [core-api] Create `services/core-api/tests/test_route_coverage.py` — test that all registered FastAPI routes are present in either `ROUTE_MATRIX` or `PUBLIC_ROUTES`
