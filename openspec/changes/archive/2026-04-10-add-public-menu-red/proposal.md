## Why

The public menu router (`core_api.routers.menu_public`) currently ships as an empty stub (see spec `menu-router-stubs`). Without a read endpoint the customer SPA has nothing to render on the menu page, which blocks MVP Phase 2 (Menu & Cart) and every downstream flow (cart, checkout, payment). This change lights up the first customer-facing HTTP surface for the menu.

**MVP Phase**: Phase 2 — Menu & Cart (PDD §7.1).

## What Changes

- Add `GET /api/v1/menu` — single endpoint returning the active menu grouped by category.
- Response is always grouped by `Category` and ordered by `categories.sort_order`, then `menu_items.sort_order`, matching the PDD §5.4 index `(category_id, sort_order)`.
- Hide non-customer-facing rows:
  - `menu_items.archived = TRUE` are never returned (INV-006 / PDD §5.2).
  - `categories.is_visible = FALSE` are never returned.
  - `categories.type = 'modifier'` is never returned (modifiers are attached inline to items, not browsed as a top-level category).
- Support an `available=true` query filter that additionally hides `menu_items.available = FALSE` (stop list) and `size_options.available = FALSE`. When the filter is absent, the full active menu is returned including stop-listed rows so the frontend can render them as disabled.
- Bilingual response honoring `Accept-Language` (`ru` default, `en` opt-in): response exposes flat `name` / `description` fields selected from `name_ru`/`name_en` (and equivalents). The raw `name_ru`/`name_en` pair is still included so the SPA can switch language client-side without a refetch.
- Introduce a thin service layer `core_api.services.menu_public` that owns the DB query (eager-loads `size_options` and `modifiers` in one round trip) and the filtering rules. The router stays a thin HTTP adapter.
- Add focused tests in `services/core-api/tests/test_menu_public.py` covering: grouping/ordering, `archived` exclusion, `is_visible=false` exclusion, `available=true` filter, `Accept-Language` selection, empty-menu case.
- **Optional**: in-process TTL cache (e.g. 30 s) keyed by `(available_filter, language)`. Only added if it stays behind a single well-tested helper; otherwise deferred. Redis caching is explicitly out of scope for this change.

## Capabilities

### New Capabilities
- `menu-public-read`: Public HTTP read API over the active menu — grouping, ordering, stop-list visibility rules, bilingual projection via `Accept-Language`, and (optional) short-lived response cache. This is the customer-facing counterpart to the admin menu CRUD that will land separately.

### Modified Capabilities
<!-- None. `menu-router-stubs` intentionally described an *empty* router; adding endpoints to it is the expected next step, not a requirement-level change to that capability. `menu-schema` is consumed read-only. -->

## Impact

- **Code**:
  - `services/core-api/src/core_api/routers/menu_public.py` — add the `GET /` endpoint + response models, wired to the new service. Prefix and tag already set by `menu-router-stubs`.
  - `services/core-api/src/core_api/services/menu_public.py` — **new**: query + filter + language projection + (optional) cache.
  - `services/core-api/src/core_api/schemas/menu.py` — add public response schemas (`PublicMenuItem`, `PublicCategory`, `PublicMenuResponse`) that flatten bilingual fields. Existing admin schemas are untouched.
  - `services/core-api/tests/test_menu_public.py` — **new** test module.
- **APIs**: adds `GET /api/v1/menu` to the public surface. No breaking changes; no existing endpoint modified.
- **DB**: read-only. No migration. Relies on the PDD §5.4 index `menu_items(category_id, sort_order)` and the partial index on `(available, archived) WHERE archived = FALSE` — both already created by `menu-schema`.
- **Auth / RBAC**: endpoint is **unauthenticated** (public browsing). INV-002 is not violated because this is a pure read with no state mutation. No RBAC matrix changes.
- **Dependencies**: no new packages. Optional cache uses stdlib (`time` + a module-level dict) — no `cachetools`, no Redis.
- **Frontend**: unblocks `web-customer` menu page. The API client is auto-generated from OpenAPI, so the SPA picks this up on the next regeneration.
- **Workers**: none affected (`payment-worker`, `sms-worker` do not touch menu).

## Non-Goals

- **No menu mutations.** Create/update/delete, stop-list toggling, and archiving all live behind `/api/v1/admin/menu` and are owned by a separate admin-menu change.
- **No Redis / distributed caching.** At most an in-process TTL cache; cluster-wide invalidation is a later concern.
- **No search, pagination, or filtering beyond `available`.** The full menu for a single location fits comfortably in one response (PDD §3: single location, no multitenancy).
- **No price personalization / loyalty-aware pricing.** Loyalty lives in Phase 5; this endpoint returns catalog prices only.
- **No image upload / CDN work.** `image_url` is returned as stored; hosting of images is out of scope.
- **No `Content-Language` negotiation beyond a simple `ru`/`en` pick.** Quality values, wildcards, and regional variants (`en-GB`) are not parsed — unknown or missing header falls back to `ru`.
