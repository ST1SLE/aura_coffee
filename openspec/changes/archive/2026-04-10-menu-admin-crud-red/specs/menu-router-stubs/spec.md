## MODIFIED Requirements

_References: PDD §7.1 (Phase 6 replaces the Phase 2 stub for `menu_admin`), INV-002, INV-006, INV-010._

### Requirement: menu_admin router is populated and mounted

The system SHALL provide a router module `core_api.routers.menu_admin` exporting `router: APIRouter` with `prefix="/api/v1/admin/menu"` and `tags=["menu-admin"]`. This router SHALL be populated with the endpoints specified by the `menu-admin-crud` capability (CRUD for categories, items, modifiers, sizes, plus the two `.../availability` stop-list toggles). `core_api.main` SHALL call `app.include_router(menu_admin_router)` exactly once after the existing Phase 1 `include_router` calls.

**Previously:** the router was required to contain **zero** endpoint functions and OpenAPI was required to contain no `paths` under `/api/v1/admin/menu`.
**Now:** the router contains the endpoint set specified by `menu-admin-crud`, and OpenAPI SHALL expose those paths.

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

`core_api.main` SHALL import the three routers (`menu_admin`, `menu_public`, `cart`) and call `app.include_router(...)` for each exactly once. The file SHALL NOT contain duplicate includes, conditional includes, or feature-flag guards for these routers. The `menu_public` and `cart` routers remain empty stubs until their own feature changes land.

**Previously:** all three routers were empty stubs when mounted.
**Now:** `menu_admin` carries endpoints; `menu_public` and `cart` remain empty stubs. The "exactly one `include_router` call per router" requirement is unchanged.

#### Scenario: Each router is registered exactly once
- **WHEN** grepping `services/core-api/src/core_api/main.py` for `include_router`
- **THEN** there SHALL be exactly one `include_router` call per router for `menu_admin_router`, `menu_public_router`, and `cart_router`

### Requirement: Endpoint-free constraint applies only to menu_public and cart

The stub files `core_api.routers.menu_public` and `core_api.routers.cart` SHALL NOT contain any of: `@router.get`, `@router.post`, `@router.put`, `@router.patch`, `@router.delete`, calls to dependency injection, calls into `core_api.services.*`, or edits to `core_api.rbac_matrix`. The `menu_admin` router is no longer covered by this constraint — its contents are governed by the `menu-admin-crud` capability.

**Previously:** the "no endpoint code" constraint applied to all three stubs including `menu_admin`.
**Now:** the constraint applies only to `menu_public` and `cart`.

#### Scenario: Static check finds no endpoint decorators in remaining stubs
- **WHEN** scanning `core_api/routers/menu_public.py` and `core_api/routers/cart.py` for the substring `@router.`
- **THEN** no matches SHALL be found

#### Scenario: menu_admin is allowed endpoint decorators
- **WHEN** scanning `core_api/routers/menu_admin.py` for `@router.`
- **THEN** matches MAY be present (the `menu-admin-crud` capability defines their exact shape)
