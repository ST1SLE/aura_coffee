## ADDED Requirements

_References: PDD §7.1 (Phase 2: Menu & Cart), INV-002 (auth required on state mutations — enforced later by feature worktrees), INV-010 (role isolation — enforced later by feature worktrees)._

### Requirement: menu_admin router is populated and mounted

The system SHALL provide a router module `core_api.routers.menu_admin` exporting `router: APIRouter` with `prefix="/api/v1/admin/menu"` and `tags=["menu-admin"]`. This router SHALL be populated with the endpoints specified by the `menu-admin-crud` capability (CRUD for categories, items, modifiers, sizes, plus the two `.../availability` stop-list toggles). `core_api.main` SHALL call `app.include_router(menu_admin_router)` exactly once after the existing Phase 1 `include_router` calls.

#### Scenario: Router is importable and mounted
- **WHEN** importing `core_api.routers.menu_admin`
- **THEN** `router` SHALL be an `APIRouter` instance with `prefix == "/api/v1/admin/menu"` and `router.routes` SHALL be non-empty

#### Scenario: OpenAPI exposes menu-admin operations
- **WHEN** querying `/openapi.json` on a freshly started app
- **THEN** the response SHALL contain a `menu-admin` tag with operations under `/api/v1/admin/menu/...` matching the `menu-admin-crud` capability

#### Scenario: App still boots
- **WHEN** the FastAPI app is instantiated via `TestClient`
- **THEN** startup SHALL succeed with no exceptions and `GET /openapi.json` SHALL return HTTP 200

### Requirement: main.py registers all three routers exactly once

`core_api.main` SHALL import the three routers (`menu_admin`, `menu_public`, `cart`) and call `app.include_router(...)` for each exactly once. The file SHALL NOT contain duplicate includes, conditional includes, or feature-flag guards for these routers.

#### Scenario: Each router is registered exactly once
- **WHEN** grepping `services/core-api/src/core_api/main.py` for `include_router`
- **THEN** there SHALL be exactly one `include_router` call per router for `menu_admin_router`, `menu_public_router`, and `cart_router`

