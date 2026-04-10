## Context

**Affected modules**: [core-api] (primary), [shared] (read-only — uses existing `MenuItemAvailability` enum). No changes to [payment-worker], [sms-worker], [web-customer], [web-admin], [database], [redis].

The menu domain schema (`categories`, `menu_items`, `size_options`, `modifiers`, `menu_item_modifiers`), SQLAlchemy models, and admin Pydantic schemas are already in place (see `openspec/specs/menu-schema/spec.md`). The router module `core_api.routers.menu_public` exists but is an empty stub with `prefix="/api/v1/menu"`, `tags=["menu-public"]` — enforced by `openspec/specs/menu-router-stubs/spec.md`.

The customer SPA (`web-customer`) is blocked on this endpoint: without it the menu page has no data source, and the cart / checkout / payment flows that follow in Phase 2 have nothing to reference. The API client is auto-generated from the FastAPI OpenAPI spec, so any response-shape decision locks in what TypeScript the frontend sees.

Constraints that shape the design:
- PDD §3: single location, single menu, no multitenancy — the entire active menu fits in one response.
- PDD §5.4 indexes already include `menu_items(category_id, sort_order)` and a partial index on `(available, archived) WHERE archived = FALSE`. The query MUST be shaped to use them.
- INV-006: stop list is `menu_items.available = FALSE`. Archived (`archived = TRUE`) is a separate, permanent state.
- INV-002 only applies to state mutations — a public read endpoint is explicitly allowed to be unauthenticated. Menu-browsing-without-login is a product requirement from PDD §7.1 Phase 2.
- RU + EN bilingual fields are columns on the tables (`name_ru`, `name_en`, `description_ru`, `description_en`).

## Goals / Non-Goals

**Goals:**

- The customer SPA MUST be able to render the full active menu (categories → items → sizes + modifiers) from a single `GET /api/v1/menu` call.
- The endpoint MUST complete in a single DB round trip for the hot path, using the PDD §5.4 indexes.
- The response MUST be stable and ordered so the SPA does not need to re-sort client-side.
- The endpoint MUST respect visibility rules: archived items always hidden; invisible categories always hidden; the `modifier` category never surfaced as a browsable category.
- The endpoint MUST offer a language selection mechanism that also exposes raw `ru`/`en` pairs, so the SPA can switch language without a refetch.
- Test coverage MUST exercise grouping, ordering, visibility rules, the `available` filter, language selection, and the empty-menu case.

**Non-Goals:**

- No menu mutations, no stop-list toggling, no archive — all live under `/api/v1/admin/menu` in a separate change.
- No Redis / distributed caching. At most an in-process TTL cache, and only if it stays behind one small helper with clear tests.
- No search, no pagination, no filtering beyond `available=true`.
- No loyalty-aware pricing. Catalog prices only.
- No `Accept-Language` quality-value / wildcard / regional-variant parsing — a simple prefix check is enough.
- No image hosting or CDN concerns — `image_url` is pass-through.

## Decisions

### D1. Endpoint shape: single `GET /api/v1/menu` returning a grouped tree

The endpoint SHALL return `PublicMenuResponse = { categories: list[PublicCategory] }`, where each `PublicCategory` embeds its ordered `items: list[PublicMenuItem]`, and each item embeds its `size_options` and `modifiers`. Categories are ordered by `categories.sort_order`, items by `menu_items.sort_order`.

**Why a single tree instead of two endpoints (`/categories` + `/menu-items?category_id=...`)**: the SPA renders the whole menu on one page anyway, and PDD §3 guarantees a single-location menu that comfortably fits in one response. Two endpoints would mean N+1 round-trips from the SPA and extra coordination in state management for zero benefit. Rejected.

**Why a grouped tree instead of a flat `list[PublicMenuItem]` with `category_id`**: grouping is a strict product requirement — the menu page is category-sectioned. Pushing grouping to the client duplicates the ordering contract on both sides and invites drift. Rejected.

### D2. Eager-load relationships with a single query

The service SHALL use `selectinload(MenuItem.size_options)` and `selectinload(MenuItem.modifiers)` (via the `menu_item_modifiers` secondary) plus `joinedload(MenuItem.category)` — or equivalent — so the entire response is materialized in O(1) statements regardless of menu size. No lazy loading, no per-item round trips.

**Why `selectinload` over `joinedload` for collections**: `joinedload` on multiple collections causes a Cartesian explosion; `selectinload` issues one additional query per collection which is stable and uses the `size_options(menu_item_id)` index. The category itself is a single-row lookup so `joinedload` is fine there. (Alternative considered: assemble the tree manually from three separate `select`s and stitch in Python — more code, same round-trip count, rejected.)

### D3. Filtering and visibility rules live in the service, not the router

`core_api.services.menu_public.get_public_menu(db, *, only_available: bool, language: Language) -> PublicMenuResponse` owns all three concerns: query, visibility rules, language projection. The router only parses request params / headers and calls the service. This matches the existing shape of other service modules (`services/auth.py`, `services/profile.py`).

Fixed visibility rules (always applied, not toggleable):
1. `menu_items.archived = FALSE`
2. `categories.is_visible = TRUE`
3. `categories.type != 'modifier'` — modifiers appear only inline on items, never as a browsable category.

Conditional rule (only when `available=true` query param is set):
4. `menu_items.available = TRUE`
5. `size_options.available = TRUE` (stop-listed sizes pruned from the per-item list)

**Why keep stop-listed items visible by default**: the SPA wants to render them as disabled "Out of stock" tiles rather than silently hide them (standard e-commerce UX). The `available=true` switch is for contexts where the caller explicitly wants a pruned list.

**Why drop category `type='modifier'` unconditionally**: PDD §5.2 describes modifiers as attachments to items, not standalone catalog entries. The `modifier` category exists only so admins can group modifiers in the admin panel. Leaking it to customers would confuse the UX. The admin endpoint will surface it separately.

### D4. Bilingual via `Accept-Language` + flat projected fields AND raw pairs

Request side: parse `Accept-Language` with a minimal rule — if the header starts with `en` (case-insensitive), language is `EN`; otherwise `RU` (default and fallback). No q-values, no wildcards, no BCP-47. A `lang` query param is **not** added; HTTP content negotiation is the standard answer and the API client generator handles it cleanly.

Response side: each `PublicCategory` and `PublicMenuItem` SHALL expose **both**:
- A flat `name: str` / `description: str | None`, picked according to the request language.
- The raw `name_ru`, `name_en`, `description_ru`, `description_en` fields.

**Why expose both**: the flat field is the ergonomic default for the SPA's current-language render; the raw pairs let the SPA switch language in-place on a user toggle without a second request. Response size is trivial (menu has ~tens of items). Alternative considered: only the flat field, with a refetch on language toggle — rejected because it introduces a loading spinner on a purely-client-side action.

**Projection helper**: a single `_pick(language, ru_value, en_value)` in the service, so the logic has exactly one home and is trivially testable.

### D5. Response schemas are *new*, not reused from admin

Add new Pydantic schemas in `core_api.schemas.menu`:
- `PublicCategory { id, type, name, name_ru, name_en, sort_order, items }`
- `PublicMenuItem { id, category_id, name, name_ru, name_en, description, description_ru, description_en, base_price, image_url, available, sort_order, size_options, modifiers }`
- `PublicMenuSizeOption { id, label, price, available }`
- `PublicMenuModifier { id, name, name_ru, name_en, price, available }`
- `PublicMenuResponse { categories: list[PublicCategory] }`

**Why not reuse `MenuItemResponse`**: the admin schema (a) exposes `archived` (never relevant to customers), (b) exposes the computed `availability` enum which conflates stop-list and archived (customers never see archived, so the three-state enum is noise), and (c) does not carry flat projected fields. Forking the schemas keeps each audience's contract clean and keeps the auto-generated TypeScript tight. The cost is a handful of extra classes — acceptable.

Prices are integers in kopecks (INV referenced in PDD §5.2). No conversion in the API layer; the SPA formats for display.

### D6. Caching: deferred, behind a feature toggle

The endpoint SHALL NOT add caching in the first implementation. The proposal marked caching as optional; shipping it in the same change means either (a) premature optimization without measurements, or (b) a second code path to test. Both are worse than a small, well-tested, cache-less service.

If measurements later show the query is a hot spot, the follow-up SHALL use an in-process TTL cache (stdlib only — `time.monotonic()` + a module-level `dict`) keyed by `(only_available, language)`, with a 30 s TTL and an explicit invalidation hook the admin mutation endpoints will call. Redis is rejected as overkill for a single-replica deployment. This is noted here so the decision is not re-litigated during `/opsx:apply`.

### D7. No auth middleware, no RBAC matrix entry

The endpoint is unauthenticated. The existing RBAC middleware already skips routes that are not listed in `rbac_matrix`, so simply *not* adding an entry is enough. A test SHALL assert that an anonymous client gets HTTP 200 from `GET /api/v1/menu`, which locks the decision in.

### D8. Testing uses the real test database, no mocks

Per the repo rule (`services/core-api/tests/conftest.py` hits `TEST_DATABASE_URL`, no sqlite fallback to `DATABASE_URL`), tests SHALL seed real rows via SQLAlchemy and assert against the HTTP response via `httpx`. No mocking of the service or the DB. Fixtures SHALL build: 2 visible categories (`drink`, `food`), 1 invisible category, 1 `modifier` category, mixed `available`/`archived` items, per-item sizes and modifiers.

## Risks / Trade-offs

- **[Risk] Response size on a very large menu** → Mitigation: PDD §3 guarantees a single location and Phase 2 scope is a real coffee shop (order of 50 items). If the menu ever grows past ~1 MB response, revisit with pagination or HTTP compression; the current single-shot tree is fine at target scale.
- **[Risk] `Accept-Language` parsing is too naive and misrepresents a user's preference** → Mitigation: fallback is always `ru`, and raw `name_ru`/`name_en` are in the payload, so any mis-detection is correctable on the client without data loss. Upgrading the parser later is a pure service-layer change; the API contract does not move.
- **[Risk] Leaking the `modifier` category to customers via some other path** → Mitigation: filter is in the service method, which is the only code path for this endpoint. A dedicated scenario in specs asserts the exclusion so regressions are caught in tests.
- **[Risk] Forking schemas causes drift between admin and public views** → Mitigation: they are *supposed* to differ — that is the point. Shared pieces (enums like `SizeLabel`, `CategoryType`) are reused; only the response envelopes are separate. A test checks both surfaces round-trip the same DB row so a schema-level drift shows up fast.
- **[Trade-off] Exposing both flat and raw bilingual fields inflates the payload** → Accepted: menu is small, and the alternative (refetch on language toggle) is worse UX.
- **[Trade-off] Deferring the cache means the first version has a slightly higher per-request cost** → Accepted: query is a few joins against indexed columns on a sub-100-row table on a single-replica deployment. Optimize only once measurements justify it.

## Migration Plan

This change is additive: new endpoint, new schemas, new service module, new tests. No DB migration, no data backfill, no config changes.

**Deploy**:
1. Merge, deploy core-api; `GET /api/v1/menu` goes live. Existing stub tests (`test_router_stubs.py`) must be updated or replaced because the empty-router assertion in `menu-router-stubs` now no longer holds for this module.
2. Frontend regenerates API client from the new OpenAPI spec and wires the menu page.

**Rollback**: revert the core-api deploy. No data is touched, so rollback is clean. The frontend will 404 on the new client call until it is reverted too — acceptable because the SPA menu page simply stays empty until both sides land.

**Note on `menu-router-stubs` scenarios**: the spec for that capability asserts `router.routes` is empty and no paths exist under `/api/v1/menu`. Those scenarios described a *temporary* state and will naturally be invalidated by this change. Resolution is handled in the tasks checklist (update or retire the affected scenarios in `openspec/specs/menu-router-stubs/spec.md` and `test_router_stubs.py`) as part of implementation, not as a separate spec delta — this change is purely additive at the requirement level.

## Open Questions

- Should `image_url` be rewritten to an absolute URL at the API layer (e.g. prefixing with a configured CDN base)? Current decision: pass through as stored, SPA resolves. Revisit if the admin upload flow stores relative paths.
- Should the `modifier`-type category exclusion be enforced by the service filter OR by a DB-level `CHECK` / view? Current decision: service filter. DB-level enforcement would be invasive and this is a presentation rule, not an integrity rule.
