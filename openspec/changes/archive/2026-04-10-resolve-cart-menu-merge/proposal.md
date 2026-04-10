## Why

Merging the `aura_coffee-cart` worktree into `menu_cart` left three textual merge conflicts (`rbac_matrix.py`, `tests/conftest.py`, `tests/test_router_stubs.py`) plus one hidden semantic conflict git auto-merged without flagging (`tests/test_main_includes_menu_routers.py`). The hidden conflict is a latent test failure: the test still asserts `/api/v1/admin/menu` and `/api/v1/menu` expose zero routes, but on `menu_cart` both routers are now implemented. The branch will not run green until all four are resolved, and the dead RED-phase scaffolding from the `menu-router-stubs` capability needs to be retired to reflect post-merge reality.

## What Changes

- Resolve `services/core-api/src/core_api/rbac_matrix.py` as a union of menu-admin routes (HEAD) and cart routes (`aura_coffee-cart`); both sets remain authoritative.
- Resolve `services/core-api/tests/conftest.py` as a union of the public-menu fixtures (HEAD: `PublicMenuSeed`, `_pg_ready`, `_pg_db_override`, `seed_public_menu`) and the cart fixtures (`aura_coffee-cart`: `cart_redis`, `db_session`); no fixture name collisions.
- Resolve `services/core-api/tests/test_router_stubs.py` — `stub_files` is no longer meaningful because `cart.py`, `menu_admin.py`, and `menu_public.py` are all implemented. Delete the file entirely: the `router exists + prefix/tags` assertions are redundant with full route tests, and `test_stubs_have_no_endpoint_decorators` becomes vacuous.
- Fix the hidden semantic conflict in `services/core-api/tests/test_main_includes_menu_routers.py`: drop the loop that asserts empty paths under `/api/v1/admin/menu` and `/api/v1/menu`. Keep the tag check and the `include_router count == 6` assertion — both are still valid post-merge.
- Retire the obsolete stub-state requirements in the `menu-router-stubs` capability (the "menu_public router is empty", "cart router is empty", and "endpoint-free constraint applies to menu_public and cart" requirements). They are contradicted by the `menu-public-read` and `cart-api` capabilities already archived on the two feature branches.
- No application code changes outside `rbac_matrix.py`. No behavior changes for customers or staff. No migration.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `menu-router-stubs`: remove the stub-state requirements that asserted `menu_public` and `cart` routers must be empty, and remove the endpoint-free constraint from those two files. The `menu_admin` router requirement (populated + mounted) remains. Rationale: the stub-phase requirements were intentionally transitional and are now superseded by `menu-public-read` and `cart-api`.

## Non-Goals

- No changes to `cart-api`, `menu-public-read`, `menu-admin-crud`, `pricing`, or `cart-schema` capabilities — the feature work on both branches stays intact.
- No refactor of the duplicated `db_client` fixture (one in conftest for menu admin tests, one module-local in `test_route_cart.py`). They coexist via pytest scoping and cleanup is out of scope.
- No consolidation of the duplicate Alembic-upgrade machinery (`_pg_ready` session-scoped vs. `db_session` function-scoped). Redundant but not broken.
- No archival of the `menu-router-stubs` capability as a whole. Only the stub-state requirements are retired; the populated `menu_admin` requirement stays.
- No new tests. This is a resolution change, not a feature change.

## Impact

- **Affected files (code):** `services/core-api/src/core_api/rbac_matrix.py`.
- **Affected files (tests):** `services/core-api/tests/conftest.py`, `services/core-api/tests/test_router_stubs.py` (deleted), `services/core-api/tests/test_main_includes_menu_routers.py`.
- **Affected specs:** `openspec/specs/menu-router-stubs/spec.md` (remove three requirements).
- **Affected phase:** Phase 2 — Menu & Cart (PDD §7.1). Clears the way for the merged branch to run green and unblocks downstream Phase 2 work.
- **Runtime impact:** None. Merge-only resolution; no public API, database, or service behavior changes.
- **Risk:** Low. All changes are test-state or RBAC-table-union. Verification is running the core-api test suite post-resolution.
