## Why

The current RBAC enforcement relies on per-endpoint `Depends(require_role(...))` calls scattered across routers. As the API grows (menu, orders, delivery, loyalty, admin panel — phases 2–6), every new endpoint must manually declare its role guard. This is error-prone: a missed `Depends` silently leaves an endpoint unprotected. A declarative route protection matrix centralizes all access rules in one place and enforces them via middleware, giving a single source of truth auditable at a glance. Ref: INV-002, INV-010.

**MVP phases:** Applies across all phases (1–6). The middleware itself ships in Phase 1 (Auth) as infrastructure; the route matrix grows with each subsequent phase.

## What Changes

- **New middleware**: A FastAPI middleware that intercepts every request, matches the path + method against a declarative route→role mapping, and rejects unauthorized access before the endpoint handler runs.
- **Route protection matrix**: A single Python config (dict/dataclass) mapping route patterns to allowed roles. Supports exact paths and path prefixes with wildcards.
- **Default-deny policy**: Any route not listed in the matrix and not explicitly marked public is denied (403). This prevents accidental exposure of new endpoints.
- **Deprecation of per-endpoint role guards**: Existing `Depends(require_role(...))` calls in routers become redundant and are removed. The `require_role` dependency stays available for edge cases but is no longer the primary enforcement mechanism.
- **Public routes whitelist**: Explicitly listed routes (health check, auth endpoints, public menu) bypass role checks.

## Non-Goals

- **Granular permission system**: No sub-role permissions (e.g., `can_edit_menu`). The matrix maps routes to roles directly. Granular permissions can be layered on later if needed.
- **Dynamic/DB-stored rules**: The route matrix is static Python config, not stored in the database. No runtime rule editing via admin panel.
- **Rate limiting or throttling**: The middleware only checks role authorization, not request frequency. Rate limiting stays in OTP/Redis layer.

## Capabilities

### New Capabilities
- `rbac-middleware`: Declarative route protection matrix with FastAPI middleware enforcement, default-deny policy, and public route whitelist.

### Modified Capabilities
- `rbac`: Existing `require_role` dependency is demoted from primary enforcement to optional secondary guard. Spec-level behavior changes: endpoints no longer rely on dependency injection for role checks — middleware handles it upstream.

## Impact

- **Code**: `services/core-api/src/core_api/main.py` — middleware registration. New module for matrix config + middleware logic. Existing routers lose `require_role` dependencies.
- **APIs**: No HTTP contract changes. Same 401/403 responses, same role semantics. Clients unaffected.
- **Testing**: New middleware tests. Existing role-check tests need migration from dependency-level to integration-level (request through middleware).
- **Dependencies**: No new external packages. Pure FastAPI/Starlette middleware.
