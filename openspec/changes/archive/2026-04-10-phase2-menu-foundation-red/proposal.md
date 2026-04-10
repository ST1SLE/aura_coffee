> **TDD phase: RED.** This is the first of a two-change pair (`phase2-menu-foundation-red` → `phase2-menu-foundation-green`). This change lands PREREQ setup and failing tests only. Implementation lands in the GREEN change. Both changes share identical proposal, design, and specs — only `tasks.md` differs.

## Why

Phase 2 (Menu & Cart, PDD §7.1) needs admin CRUD, public menu, stop list, and cart features implemented in parallel worktrees. Today all three future routers (menu admin, menu public, cart) would contend for the same files — `database/migrations/`, `services/core-api/src/core_api/main.py`, SQLAlchemy models, shared enums — producing unavoidable merge conflicts.

This change lays a foundation that splits contention-prone artifacts into stable, shared files and registers **empty router stubs** in `main.py` ahead of time. Parallel worktrees then only fill in their own router files; `main.py`, migrations, models, and schemas stay untouched during feature work.

## What Changes

- Add Alembic migration `0004_menu_tables.py` creating: `categories`, `menu_items`, `size_options`, `modifiers`, `menu_item_modifiers` (M:N junction). All fields per PDD §5.2 Menu table group, strictly aligned.
- Add SQLAlchemy models in `services/core-api/src/core_api/models/menu.py` mapping the new tables. (Note: creates a new `models/` package — current project keeps ORM declarations under `services/`; design.md proposes the package location.)
- Add Pydantic v2 schemas:
  - `services/core-api/src/core_api/schemas/menu.py` — `Category*`, `MenuItem*`, `SizeOption*`, `Modifier*` with `Create` / `Update` / `Response` variants and bilingual fields.
  - `services/core-api/src/core_api/schemas/cart.py` — `CartItemCreate`, `CartItemResponse`, `CartResponse` (Redis-backed, per PDD §5.3).
- Extend `packages/shared/src/shared/enums.py` with menu-related enums: `CategoryType` (`DRINK`/`FOOD`/`MERCH`/`MODIFIER`), `SizeLabel` (`S`/`M`/`L`), `MenuItemAvailability` (`AVAILABLE`/`STOP_LIST`/`ARCHIVED`).
- Create **empty** `APIRouter` stub files with zero endpoints:
  - `services/core-api/src/core_api/routers/menu_admin.py`
  - `services/core-api/src/core_api/routers/menu_public.py`
  - `services/core-api/src/core_api/routers/cart.py`
- Register all three stub routers in `services/core-api/src/core_api/main.py` via `include_router(...)` so downstream worktrees never modify `main.py`.
- Seed data is **out of scope** (covered by the feature changes that follow).

## Capabilities

### New Capabilities
- `menu-schema`: database schema, ORM models, and Pydantic DTOs for categories, menu items, size options, modifiers, and the many-to-many junction per PDD §5.2. Bilingual (RU/EN) fields, prices as integer kopecks, stop-list/archived flags.
- `cart-schema`: Pydantic DTOs for cart items and cart responses used by the Phase 2 cart router (storage itself is Redis per PDD §5.3 — no DB tables).
- `menu-router-stubs`: empty `APIRouter` files for `menu_admin`, `menu_public`, `cart`, registered in `main.py`. Establishes the contention-free merge surface for parallel Phase 2 feature worktrees.

### Modified Capabilities
_None._ No existing spec's requirements change. `fastapi-app` gains three new mounted routers with zero endpoints, which is additive and does not alter existing behavior.

## Impact

- **Code:**
  - New: `database/migrations/versions/0004_menu_tables.py`, `services/core-api/src/core_api/models/__init__.py`, `services/core-api/src/core_api/models/menu.py`, `services/core-api/src/core_api/schemas/menu.py`, `services/core-api/src/core_api/schemas/cart.py`, three new files in `routers/`.
  - Modified: `packages/shared/src/shared/enums.py` (additive), `services/core-api/src/core_api/main.py` (+3 `include_router` calls and imports).
- **Database:** adds 5 new tables. No data migration. Fully reversible via Alembic `downgrade()`.
- **APIs:** no new HTTP endpoints in this change — routers are intentionally empty. OpenAPI schema gains three tags with no operations.
- **Dependencies:** none added; uses existing SQLAlchemy 2.0, Alembic, Pydantic v2, FastAPI.
- **Follow-up changes unblocked:** three parallel worktrees — `phase2-menu-admin`, `phase2-menu-public`, `phase2-cart` — each touching only its own router file plus services. Merge conflicts reduced to router internals only.
- **PDD alignment:** strict — PDD §5.2 Menu group, §3 Menu/Cart domain language, INV-006 (stop list), INV-014 (immutable snapshots — guides cart schema design). No extensions; modifier grouping (min/max selection) is deferred to a later change if/when the admin worktree needs it.
- **MVP Phase:** Phase 2 (Menu & Cart) foundation, per PDD §7.1. Blocks all Phase 2 feature work until merged.

## Non-Goals

- **No endpoints.** No HTTP handlers, no business logic, no service-layer code in `routers/` or `services/`. Router files contain only `router = APIRouter(...)`.
- **No seeds.** No seed data for categories/items/modifiers in this change. Seeds live with the feature worktrees that need them or with an operational seed script.
- **No cart Redis wiring.** No Redis client, no `cart:{session_id}` keys, no TTL logic. `schemas/cart.py` defines DTOs only.
- **No stop-list toggle logic.** Fields exist; mutation endpoints are Phase 2 feature work.
- **No frontend changes.** No TypeScript types, no API client regeneration — there are no endpoints to generate from.
- **No tests for behavior.** Only schema-level tests (migration up/down, model import smoke, Pydantic validation round-trips). Behavioral tests belong to the feature worktrees.
- **No changes to existing auth, RBAC, or user tables.** RBAC matrix entries for new endpoints are added by the feature changes that introduce those endpoints.
