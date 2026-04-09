## Context

**Affected modules:** [core-api]

Currently, role-based access control is enforced per-endpoint via `Depends(require_role(...))` in FastAPI routers (`deps/rbac.py`). Each router author must remember to add the dependency. As the API surface grows across MVP phases 2–6 (menu, orders, delivery, loyalty, admin), the risk of unprotected endpoints increases. There is no single place to audit which roles can access which routes.

The existing `get_current_user` dependency (`deps/auth.py`) extracts `user_id` and `role` from JWT. The `require_role` factory checks role membership. Both work correctly but are opt-in at the endpoint level.

Roles are fixed: `customer`, `admin`, `barista`, `courier` (INV-010).

## Goals / Non-Goals

**Goals:**
- Single declarative data structure mapping route patterns → allowed roles
- FastAPI middleware that enforces the matrix before endpoint dispatch
- Default-deny: unlisted routes that are not public SHALL return 403
- Public routes whitelist for unauthenticated endpoints (health, auth, public menu)
- Maintain current HTTP contract (401 for missing/invalid token, 403 for wrong role)

**Non-Goals:**
- Granular sub-role permissions (e.g., `can_edit_menu`)
- Database-stored or dynamically editable rules
- Rate limiting, IP filtering, or any non-RBAC concern
- Frontend route guards (web-admin already filters by role client-side)

## Decisions

### D1: Starlette middleware vs. FastAPI dependency

**Decision:** Starlette `BaseHTTPMiddleware` subclass.

**Rationale:** Middleware intercepts requests before routing, giving a single enforcement point. Dependencies require cooperation from every router. Middleware guarantees coverage — even if a developer forgets to annotate an endpoint, the default-deny policy catches it.

**Alternatives considered:**
- *FastAPI router-level dependency*: Still requires every router to opt in. Misses the "single source of truth" goal.
- *Custom APIRoute class*: More complex, harder to test, same opt-in problem at router level.

### D2: Route matrix format

**Decision:** Python dict in a dedicated module `core_api/rbac_matrix.py`. Keys are `(method, path_pattern)` tuples; values are sets of allowed roles. A separate `PUBLIC_ROUTES` set lists patterns that skip auth entirely.

**Rationale:** Python dict is type-checkable, IDE-navigable, and testable. No YAML/JSON parsing needed. The matrix is small enough (dozens of entries) that a single dict is readable.

**Alternatives considered:**
- *YAML config file*: Extra parsing dependency, no type safety, harder to test.
- *Decorator-based registration*: Distributed across routers — defeats single-source-of-truth goal.

### D3: Path matching strategy

**Decision:** Prefix-based matching with FastAPI path parameter syntax. Patterns use `{param}` placeholders (e.g., `/api/v1/menu/{item_id}`). Matching SHALL be longest-prefix-first to avoid ambiguity.

**Rationale:** Aligns with FastAPI's own route syntax. Developers can copy route paths directly into the matrix. Longest-prefix-first prevents broad patterns from shadowing specific ones.

### D4: Token extraction in middleware

**Decision:** The middleware SHALL reuse `AuthService.decode_access_token()` for JWT decoding. It SHALL NOT duplicate token validation logic. For public routes, token extraction is skipped entirely.

**Rationale:** Single source of truth for token validation. Avoids divergence between middleware and dependency auth logic.

### D5: Coexistence with `require_role`

**Decision:** `require_role` dependency SHALL remain available but is no longer required. Existing usages in routers SHALL be removed during this change. The dependency MAY be used for edge cases where endpoint-level logic needs the current user dict (it still provides that via `get_current_user`).

**Rationale:** Removing the dependency import from routers simplifies them. Keeping the module avoids breaking anything that imports it for the user dict, not just for role checking.

## Risks / Trade-offs

**[Performance overhead]** → Middleware runs on every request including public routes. Mitigation: Public route check is a set lookup (O(1)). JWT decode only happens for protected routes. Negligible for this traffic scale.

**[OpenAPI spec accuracy]** → `require_role` dependencies currently generate 401/403 responses in OpenAPI docs. Middleware-based enforcement is invisible to OpenAPI. Mitigation: Add explicit `responses={401: ..., 403: ...}` to protected endpoints, or document globally. Acceptable trade-off for centralized enforcement.

**[Route sync drift]** → Matrix could fall out of sync with actual routes. Mitigation: Add a test that compares registered FastAPI routes against the matrix — any route missing from both the matrix and public list fails the test.

**[Middleware ordering]** → RBAC middleware MUST run after CORS middleware (CORS preflight must succeed without auth). Mitigation: Register RBAC middleware before CORS in `main.py` (Starlette middleware stack is LIFO — last added runs first for request, last for response; CORS added after RBAC means CORS intercepts first).

## Open Questions

- Should the matrix include future phase routes now (commented out) or only routes that exist? Recommend: only existing routes, add as new routers land.
