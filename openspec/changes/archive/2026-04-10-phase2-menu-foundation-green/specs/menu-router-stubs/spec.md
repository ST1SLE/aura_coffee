## ADDED Requirements

_References: PDD §7.1 (Phase 2: Menu & Cart), INV-002 (auth required on state mutations — enforced later by feature worktrees), INV-010 (role isolation — enforced later by feature worktrees)._

### Requirement: Empty menu_admin router stub exists and is mounted

The system SHALL provide a router module `core_api.routers.menu_admin` exporting `router: APIRouter` with `prefix="/api/v1/admin/menu"` and `tags=["menu-admin"]`, containing **zero** endpoint functions. `core_api.main` SHALL call `app.include_router(menu_admin_router)` after the existing Phase 1 `include_router` calls.

#### Scenario: Router is importable and empty
- **WHEN** importing `core_api.routers.menu_admin`
- **THEN** `router` SHALL be an `APIRouter` instance with `prefix == "/api/v1/admin/menu"` and `router.routes` SHALL be empty

#### Scenario: OpenAPI includes the tag with no operations
- **WHEN** querying `/openapi.json` on a freshly started app
- **THEN** the response SHALL contain a `menu-admin` tag and no `paths` entries beginning with `/api/v1/admin/menu`

### Requirement: Empty menu_public router stub exists and is mounted

The system SHALL provide a router module `core_api.routers.menu_public` exporting `router: APIRouter` with `prefix="/api/v1/menu"` and `tags=["menu-public"]`, containing **zero** endpoint functions. `core_api.main` SHALL mount it via `include_router`.

#### Scenario: Router is importable and empty
- **WHEN** importing `core_api.routers.menu_public`
- **THEN** `router` SHALL be an `APIRouter` instance with `prefix == "/api/v1/menu"` and `router.routes` SHALL be empty

#### Scenario: OpenAPI has no paths under the public menu prefix
- **WHEN** querying `/openapi.json`
- **THEN** no `paths` key SHALL begin with `/api/v1/menu`

### Requirement: Empty cart router stub exists and is mounted

The system SHALL provide a router module `core_api.routers.cart` exporting `router: APIRouter` with `prefix="/api/v1/cart"` and `tags=["cart"]`, containing **zero** endpoint functions. `core_api.main` SHALL mount it via `include_router`.

#### Scenario: Router is importable and empty
- **WHEN** importing `core_api.routers.cart`
- **THEN** `router` SHALL be an `APIRouter` instance with `prefix == "/api/v1/cart"` and `router.routes` SHALL be empty

#### Scenario: Zero operations for cart tag
- **WHEN** querying `/openapi.json`
- **THEN** the `cart` tag SHALL be present with no path operations attached to it

### Requirement: main.py registers all three stubs exactly once

`core_api.main` SHALL import the three new routers and call `app.include_router(...)` for each exactly once. The file SHALL NOT contain duplicate includes, conditional includes, or feature-flag guards for these routers.

#### Scenario: Each router is registered exactly once
- **WHEN** grepping `services/core-api/src/core_api/main.py` for `include_router`
- **THEN** there SHALL be exactly six `include_router` calls total: the three existing Phase 1 calls plus `menu_admin_router`, `menu_public_router`, `cart_router`

#### Scenario: App boots without error
- **WHEN** the FastAPI app is instantiated via `TestClient`
- **THEN** startup SHALL succeed with no exceptions and `GET /openapi.json` SHALL return HTTP 200

### Requirement: No endpoint, service, or RBAC code lands in this change

The stub files SHALL NOT contain any of: `@router.get`, `@router.post`, `@router.put`, `@router.patch`, `@router.delete`, calls to dependency injection, calls into `core_api.services.*`, RBAC decorator usage, or edits to `core_api.rbac_matrix`. These belong to the feature worktrees that follow.

#### Scenario: Static check finds no endpoint decorators in stubs
- **WHEN** scanning the three new router files for the substring `@router.`
- **THEN** no matches SHALL be found
