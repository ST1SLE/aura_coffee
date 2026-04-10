## REMOVED Requirements

_References: PDD §7.1 (Phase 2: Menu & Cart). These requirements described a transitional stub state for the `menu_public` and `cart` routers that no longer exists — both routers are now populated by the `menu-public-read` and `cart-api` capabilities respectively._

### Requirement: Empty menu_public router stub exists and is mounted

**Previously:** The system SHALL provide a router module `core_api.routers.menu_public` exporting `router: APIRouter` with `prefix="/api/v1/menu"` and `tags=["menu-public"]`, containing **zero** endpoint functions. `core_api.main` SHALL mount it via `include_router`.

**Now:** Removed. The `menu-public-read` capability defines the populated `menu_public` router contract. The "is mounted" invariant is retained by the sibling requirement *"main.py registers all three routers exactly once"*, which remains in this capability.

**Reason:** Superseded by `menu-public-read`, which specifies the `GET /api/v1/menu` endpoint and its response shape. The "zero endpoints" constraint is directly contradicted by the superseding capability.

**Migration:** No runtime migration. Consumers of the `menu-public-read` capability SHALL rely on its spec for the router's contents; this capability no longer constrains the shape of `menu_public`.

### Requirement: Empty cart router stub exists and is mounted

**Previously:** The system SHALL provide a router module `core_api.routers.cart` exporting `router: APIRouter` with `prefix="/api/v1/cart"` and `tags=["cart"]`, containing **zero** endpoint functions. `core_api.main` SHALL mount it via `include_router`.

**Now:** Removed. The `cart-api` capability defines the populated `cart` router contract (five operations: `GET /api/v1/cart`, `DELETE /api/v1/cart`, `POST /api/v1/cart/items`, `PATCH /api/v1/cart/items/{line_id}`, `DELETE /api/v1/cart/items/{line_id}`). The "is mounted" invariant is retained by the sibling *"main.py registers all three routers exactly once"* requirement.

**Reason:** Superseded by `cart-api`. The "zero endpoints" constraint is directly contradicted by the superseding capability.

**Migration:** No runtime migration. Consumers SHALL rely on `cart-api` for the router's contents.

### Requirement: Endpoint-free constraint applies only to menu_public and cart

**Previously:** The stub files `core_api.routers.menu_public` and `core_api.routers.cart` SHALL NOT contain any of: `@router.get`, `@router.post`, `@router.put`, `@router.patch`, `@router.delete`, calls to dependency injection, calls into `core_api.services.*`, or edits to `core_api.rbac_matrix`. The `menu_admin` router is no longer covered by this constraint — its contents are governed by the `menu-admin-crud` capability.

**Now:** Removed. With `menu_public` populated by `menu-public-read` and `cart` populated by `cart-api`, the prohibition on endpoint decorators, DI calls, and `rbac_matrix` edits no longer applies to any router. Each router's allowed content is fully governed by its owning capability (`menu-admin-crud`, `menu-public-read`, `cart-api`).

**Reason:** The constraint existed to keep RED-phase stubs honest during the transition from scaffold to implementation. Both stubs have been implemented; the constraint has no remaining target.

**Migration:** No runtime migration. The test `tests/test_router_stubs.py::test_stubs_have_no_endpoint_decorators` that enforced this requirement SHALL be removed as part of the resolve-cart-menu-merge change.
