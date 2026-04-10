## Context

**Affected modules:** [core-api], [shared], [database].

Phase 1 (Auth & User Profile) is merged: auth routers, staff auth, user profile, RBAC middleware, and Alembic migrations `0001`–`0003` exist in `services/core-api/src/core_api/` and `database/migrations/versions/`. Phase 2 (Menu & Cart, PDD §7.1) is the next batch and is intended to be implemented in three parallel worktrees:

1. `phase2-menu-admin` — admin CRUD for categories, items, sizes, modifiers, stop list.
2. `phase2-menu-public` — public menu endpoint(s) with stop-list filtering.
3. `phase2-cart` — Redis-backed cart add/update/remove with server-side price recomputation.

Each worktree needs to land a router, supporting services, and tests without stepping on the others. The three obvious collision points are:

- `services/core-api/src/core_api/main.py` — every worktree would add its own `include_router(...)` call.
- `database/migrations/versions/` — Alembic chains by `down_revision`; two worktrees both branching from `0003` cannot both merge cleanly.
- SQLAlchemy model module(s) and Pydantic schema files covering overlapping entities (a menu item is referenced by admin CRUD, public menu, and cart).
- `packages/shared/src/shared/enums.py` — all three need `CategoryType`, `SizeLabel`, availability states.

This change removes these collision points up front by landing **one** migration, **one** model module, **one** schemas module per concern (menu + cart), enum additions, and **empty** router stubs already wired into `main.py`. After this change merges, feature worktrees only create new files under `services/core-api/src/core_api/services/` and edit their own router file.

Current state (verified):

- `database/migrations/versions/` contains `0001_initial.py`, `0002_auth_tables.py`, `0003_staff_accounts.py`. Head is `0003`.
- `services/core-api/src/core_api/` has `routers/{auth,profile,staff_auth}.py`, `schemas/{auth,profile,staff_auth}.py`, `services/{auth,otp,profile,staff_auth,user}.py`. ORM models live in `packages/shared/src/shared/models/` (not in `core_api/`) — all existing Phase 1 models (`User`, `UserProfile`, `LoyaltyAccount`, `StaffAccount`) are there, `Base` is declared in `shared.models.__init__`, and `database/migrations/env.py` imports `from shared.models import Base`.
- `services/core-api/src/core_api/main.py` currently calls `app.include_router(...)` for `auth_router`, `profile_router`, `staff_auth_router`.
- `packages/shared/src/shared/enums.py` defines `UserStatus`, `OTPStatus`, `StaffRole` only.

Authoritative source: `docs/PRODUCT_DESIGN_DOCUMENT.md`, §3 (Domain Language), §5.2 (Menu table group), §5.3 (Redis keys), §7.1 (Phase 2 scope), INV-006 (stop list), INV-014 (immutable order items), INV-015 (secrets).

## Goals / Non-Goals

**Goals:**

- G1. Land all Phase 2 shared schema/enum/model/router surface in a single merge so feature worktrees can fan out without conflict.
- G2. Match PDD §5.2 Menu schema exactly — same tables, same columns, same relationships (integer kopecks, bilingual fields, stop-list flag, archived flag, sort_order, M:N junction). No extensions.
- G3. Keep `main.py` edits isolated to this change: three `include_router(...)` additions and their imports.
- G4. Provide forward-and-backward Alembic migration with a verified `downgrade()`.
- G5. Keep the change reviewable: no endpoints, no services, no seeds, no frontend.

**Non-Goals:**

- NG1. Endpoints, handlers, or RBAC matrix entries for menu/cart. Feature worktrees own those.
- NG2. Redis client wiring, cart key layout, TTLs, session resolution. Only Pydantic DTOs land here.
- NG3. Image upload pipeline, S3/MinIO, or `image_url` population logic. Column exists; management is Phase 2 admin work or later.
- NG4. Frontend types, OpenAPI regeneration (nothing new to generate), web-customer/web-admin changes.
- NG5. Order / Order Item schemas. Those live in Phase 3 (PDD §7.1). Cart DTOs do NOT double as order DTOs — INV-014 requires order items to be independent immutable snapshots built server-side at checkout.

## Decisions

### D1. Place menu ORM model in `packages/shared/src/shared/models/menu.py`

All existing Phase 1 ORM models (`User`, `UserProfile`, `LoyaltyAccount`, `StaffAccount`) live in `packages/shared/src/shared/models/`. `Base` is declared in `shared.models.__init__`. Alembic's `env.py` imports `from shared.models import Base` — it only detects tables registered under this `Base`. Putting menu models anywhere outside `shared.models` would require modifying Alembic's env.py to add a foreign import, coupling the migration layer to a specific service.

**Decision:** menu models go in `packages/shared/src/shared/models/menu.py`, imported in `shared/models/__init__.py`. `core_api` services import via `from shared.models.menu import Category, MenuItem, ...` — consistent with `from shared.models.user import User` etc.

**D1 resolves design Q3:** `Base` is in `shared.models`, not `core_api.database`. No new `Base` is needed; menu models inherit from the existing `shared.models.Base`.

### D2. Single migration `0004_menu_tables.py` with all five tables

One Alembic revision creating `categories`, `menu_items`, `size_options`, `modifiers`, and `menu_item_modifiers` in dependency order — strictly the tables listed in PDD §5.2.

**Rationale:** Atomic foundation. Partial application leaves the ORM models unusable. Alembic transactions ensure all-or-nothing on PostgreSQL.

**Schema details** (all columns NOT NULL unless stated; PKs are `id BIGSERIAL` unless stated; `created_at`/`updated_at` as `TIMESTAMPTZ DEFAULT now()`):

- `categories`: `id`, `type` (ENUM `category_type`: `drink|food|merch|modifier`), `name_ru VARCHAR(120)`, `name_en VARCHAR(120)`, `sort_order INT DEFAULT 0`, `is_visible BOOLEAN DEFAULT TRUE`, `created_at`, `updated_at`.
- `menu_items`: `id`, `category_id` (FK → `categories.id` ON DELETE RESTRICT), `name_ru VARCHAR(200)`, `name_en VARCHAR(200)`, `description_ru TEXT NULL`, `description_en TEXT NULL`, `base_price INT CHECK (base_price >= 0)`, `image_url VARCHAR(500) NULL`, `available BOOLEAN DEFAULT TRUE`, `archived BOOLEAN DEFAULT FALSE`, `sort_order INT DEFAULT 0`, `created_at`, `updated_at`.
- `size_options`: `id`, `menu_item_id` (FK → `menu_items.id` ON DELETE CASCADE), `label` (ENUM `size_label`: `S|M|L`), `price INT CHECK (price >= 0)`, `available BOOLEAN DEFAULT TRUE`, UNIQUE (`menu_item_id`, `label`).
- `modifiers`: `id`, `name_ru VARCHAR(120)`, `name_en VARCHAR(120)`, `price INT CHECK (price >= 0)`, `available BOOLEAN DEFAULT TRUE`, `sort_order INT DEFAULT 0`.
- `menu_item_modifiers`: composite PK (`menu_item_id`, `modifier_id`), both FK with ON DELETE CASCADE.

Indexes per PDD §5.4:

- `ix_menu_items_category_sort` on `menu_items(category_id, sort_order)`.
- Partial index `ix_menu_items_active` on `menu_items(available, archived) WHERE archived = FALSE`.
- `ix_size_options_menu_item` on `size_options(menu_item_id)`.

`downgrade()` drops in reverse order: `menu_item_modifiers` → `modifiers` → `size_options` → `menu_items` → `categories` → drop enums `category_type`, `size_label`.

### D3. Pydantic schemas: split menu and cart, full `Create`/`Update`/`Response` triplet

`schemas/menu.py` exposes for each entity: `<Entity>Base`, `<Entity>Create`, `<Entity>Update` (all fields optional), `<Entity>Response`. `<Entity>Response` is `ConfigDict(from_attributes=True)` so it converts directly from SQLAlchemy models.

Bilingual fields use plain `name_ru: str`, `name_en: str` — no nested `LocalizedString` wrapper, matching the PDD schema and the auth schemas already in the repo.

Prices are `int` (kopecks) with `Field(ge=0)`. `SizeLabel` and `CategoryType` come from `shared.enums`.

`schemas/cart.py` exposes:

- `CartItemCreate` — `menu_item_id: int`, `size_option_id: int | None`, `modifier_ids: list[int]`, `quantity: int = Field(ge=1, le=99)`.
- `CartItemResponse` — the above plus server-computed `unit_price`, `line_total`, `menu_item_snapshot` (bilingual name + availability flag), `size_snapshot`, `modifiers_snapshot` (list of `{id, name_ru, name_en, price}`).
- `CartResponse` — `items: list[CartItemResponse]`, `subtotal: int`, `currency: Literal["RUB"]`, `expires_at: datetime`.

Snapshots exist in the cart DTO because the cart worktree will compute prices server-side per INV-006 (stop list must be re-validated on every cart fetch). They are NOT persisted and do NOT replace order-item snapshots required by INV-014 — order items are built server-side at checkout in Phase 3.

**Alternatives considered:**

- Generate schemas with `pydantic-sqlalchemy` or `SQLModel`. Rejected: Phase 1 hand-writes schemas; consistency wins over tool adoption in a foundation change.
- One big `schemas/menu_and_cart.py`. Rejected: cart is Redis-backed, menu is Postgres-backed; splitting them keeps the feature worktrees' diff surfaces disjoint.

### D4. Router stubs contain only `APIRouter(prefix=..., tags=[...])`

Each stub file:

```python
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/admin/menu", tags=["menu-admin"])
```

Prefixes (locked now so they cannot drift between worktrees):

- `menu_admin.py` → `/api/v1/admin/menu`, tag `menu-admin`.
- `menu_public.py` → `/api/v1/menu`, tag `menu-public`.
- `cart.py` → `/api/v1/cart`, tag `cart`.

`main.py` imports each as `menu_admin_router`, `menu_public_router`, `cart_router` and calls `app.include_router(...)` for each below the existing Phase 1 calls. No other change to `main.py`.

**Rationale:** Empty routers are legal in FastAPI and produce zero OpenAPI operations — the generated TS client is unaffected. Locking prefixes here means the three worktrees agree without needing a sync round.

### D5. Enum additions live in `packages/shared/src/shared/enums.py`

Add `CategoryType(str, enum.Enum)` and `SizeLabel(str, enum.Enum)` alongside the existing `UserStatus`, `OTPStatus`, `StaffRole`. Values match PDD §3 / §5.2 exactly (`drink`, `food`, `merch`, `modifier`; `S`, `M`, `L`).

Also add `MenuItemAvailability(str, enum.Enum)` with values `available`, `stop_list`, `archived` — a **derived** enum exposed only in the response schema for frontend display. ORM stays on the two booleans `available` + `archived` to match PDD §5.2 one-to-one.

**Rationale:** `shared/` is imported by every backend service and is the single source of truth for enum string values that end up in DB columns, HTTP payloads, and test fixtures. Alembic references `shared.enums.CategoryType` and `shared.enums.SizeLabel` by `.value` when creating PG enums, so any drift is caught at migration time.

### D6. Tests limited to smoke + round-trip, no API layer

- `services/core-api/tests/test_migrations_menu.py`: runs `alembic upgrade head` then `alembic downgrade -1` on the test DB; asserts tables exist, then gone.
- `services/core-api/tests/test_models_menu.py`: imports `core_api.models.menu`, instantiates each model with the minimum required fields, flushes to the test session, asserts relationships (`menu_item.size_options`, `menu_item.modifiers`, `category.menu_items`).
- `services/core-api/tests/test_schemas_menu.py`: constructs each `Create` / `Update` / `Response` Pydantic model with valid and invalid payloads; confirms `Response.model_validate(orm_instance)` round-trips.
- `services/core-api/tests/test_schemas_cart.py`: same for cart DTOs.
- `services/core-api/tests/test_main_includes_menu_routers.py`: starts the app with `TestClient`, calls `/openapi.json`, asserts the three tags are registered and their path lists are empty.

No HTTP endpoint tests — there are no endpoints. No Redis tests — there is no Redis code.

## Risks / Trade-offs

- **R1. Empty routers land OpenAPI tags with zero operations.** Some OpenAPI-to-client generators emit dead imports for empty tags. → Mitigation: verified that the project's generator (FastAPI-native `/openapi.json` consumer) ignores operation-less tags; if a future generator chokes, gate `include_router` calls behind a feature flag — but this is not needed today.
- **R2. Menu models go into `shared/models/` — touching a shared package.** → Mitigation: additive only (new file + import line in `__init__.py`); Phase 1 models are untouched. If a future worker needs menu data it can import from the same place at zero cost.
- **R3. Three parallel worktrees will each add entries to the RBAC matrix (`rbac_matrix.py`).** That file is not touched here, so it remains a collision point. → Mitigation: worktrees MUST each add their RBAC rows in a dedicated, non-overlapping section and rebase-merge; acceptable because RBAC rows are line-additive and `git` merges them cleanly when they target different endpoint paths.
- **R4. Integer kopecks overflow risk on BIGINT boundaries is far off but real for sum aggregates.** → Mitigation: per PDD, `base_price` and size `price` columns are `INTEGER` (≤ 21 474 836.47 ₽, fine for an item); only aggregate totals (cart, order) SHOULD be `BIGINT` — aggregates are outside this change.
- **R5. `size_label` as a PG enum locks the set to `S/M/L`. A future "XL" requires an `ALTER TYPE ADD VALUE`.** → Mitigation: acceptable per PDD §3; `ALTER TYPE ADD VALUE` is non-blocking on PG 16.
- **R6. Modifier grouping / min-max selection is absent.** A future admin UI that needs "Milk: pick 1" style rules will require a new migration adding `modifier_groups` and `modifiers.group_id`. → Mitigation: accepted. Deferred by design to keep this change strictly PDD-aligned; the future change is a clean additive migration with NULLABLE FK.

## Migration Plan

1. **Forward:** `alembic upgrade head` from `0003_staff_accounts` to `0004_menu_tables`. Creates enums, tables, indexes. No data backfill. Safe on empty or populated prod DB (no conflict with existing tables).
2. **Rollback:** `alembic downgrade -1` drops everything `0004` created. Fully reversible. Phase 2 feature work has not started yet, so there is no data to preserve.
3. **Deploy order:** (a) merge this change, (b) run migration in CI + staging, (c) verify app boot and `/openapi.json` shows three new tags with zero operations, (d) cut feature worktrees from the updated `dev` branch.
4. **Backwards compatibility:** no existing table, endpoint, or enum is modified. Phase 1 is untouched.

## Open Questions

- **Q1.** Should `menu_items.image_url` be `VARCHAR(500)` or `TEXT`? PDD §5.2 does not specify a length. Default chosen: `VARCHAR(500)` for index-friendliness. Reviewer may override.
- **Q2.** Should the new `models/` package also re-export Phase 1 ORM models to unify imports? Current plan: no (scope discipline). Reviewer may ask to bundle.
- **Q3. (Resolved)** `Base` is declared in `packages/shared/src/shared/models/__init__.py`. All models (including new menu models) inherit from it. `core_api/database.py` has no `Base`. Menu models go in `shared/models/menu.py` per D1.
