## Affected modules

`[web-admin]`. No other module is touched. The backend (`[core-api]`), customer SPA (`[web-customer]`), shared package (`[shared]`), database, and workers are all untouched.

_References: PDD §3 (Domain Language — Category, Menu Item, Size Option, Modifier), PDD §5.2 (Menu table group), PDD §7.1 Phase 2 (Menu & Cart), archived change `2026-04-10-add-public-menu-green` (defines the public menu schemas the customer consumes), INV-002 (state mutations require auth — unchanged here)._

## Problem framing

The admin SPA and the backend were built from divergent interpretations of the menu data model. The backend is authoritative per PDD §5.2 (bilingual fields, typed categories, ordered lists, stop-list via `available`). The admin SPA ships a pre-bilingual draft that 422s on every create/update. Two additional consumers already agree with the backend:

1. The backend Pydantic schemas themselves (`services/core-api/src/core_api/schemas/menu.py`).
2. The customer SPA types (`web/customer/src/api/menuTypes.ts`).

So the design question is **not** "which side is right" — it's "how do we realign the admin SPA with minimal blast radius and maximal merge safety against the two sibling changes running in parallel worktrees".

## Constraints

- MUST keep all CRUD function names and URL paths (`listCategories`, `createItem`, `PATCH /items/:id/availability`, etc.) identical, because the RBAC matrix and existing tests depend on them.
- MUST NOT touch `App.tsx`, `main.tsx`, or `vite.config.ts` — these belong to `fix-admin-spa-basepath`.
- MUST NOT touch anything under `web/customer/**` — handled by `fix-customer-menu-aggregated-endpoint`.
- MUST update the test suite in the same change so the branch stays green at every task boundary.
- SHOULD minimize new i18n keys — reuse existing `pages.menu.*` namespace.
- SHOULD NOT introduce a code-generation step (e.g. openapi-typescript). The existing codebase hand-writes types; keep convention until a separate change introduces codegen holistically.

## Decisions

### D1. Redeclare `CategoryType` and `SizeLabel` locally in `web/admin/src/api/menu.ts`

**Options considered:**
- **A. Import from `packages/shared/src`.** Would be DRY but requires a TS path alias for the shared package and risks build-config changes that overlap with `fix-admin-spa-basepath` (which already touches `vite.config.ts`).
- **B. Redeclare as a TS string-literal union local to `menu.ts`.** Free from build-config coupling, fits within the file lane, trivially testable.

**Decision:** **B**. Consolidating shared enums across admin / customer / backend is a worthwhile follow-up but out of scope here. A one-line `export type CategoryType = 'drink' | 'food' | 'merch' | 'modifier'` is enough and cannot conflict with the other two worktrees.

### D2. Category edit UX: flat form, not modal

**Options considered:**
- **A. Upgrade `CategoryList` inline editor to a flat form with `name_ru`, `name_en`, `type` on one row.**
- **B. Introduce a separate `CategoryFormDialog` modal like `MenuItemFormDialog`.**

**Decision:** **A**. The current CategoryList is a left-rail selector, not a full CRUD table; a modal would distort the page layout. The inline form MAY wrap to a second row on narrow viewports. `sort_order` defaults to `categories.length` at creation time so the new category lands at the end; `is_visible` defaults to `true`. Both fields become editable in a follow-up change if UX demands it — out of scope here.

### D3. Translation of category display name

The admin UI itself is bilingual via `react-i18next`. Category names are data, not UI strings. The decision: read `i18n.language` (`'ru' | 'en'`) at the render site and pick `cat.name_ru` or `cat.name_en` with `name_ru` as the fallback when the active language is missing a translation. Same rule applies to items and modifiers. A tiny helper `pickLang(ru, en, lang)` SHALL live in `pages/Menu/utils.ts` so all three tables call the same function.

### D4. 422 error surfacing

The existing `MenuItemFormDialog` already handles 422 by parsing `err.body.detail[*].loc` into a field list. That logic stays — only the set of field names it can report changes (`name_ru`, `name_en`, `base_price`, … instead of `name`, `price_kopecks`). The same pattern SHALL be copied into `CategoryList` and `ModifiersPanel` so all three surfaces give the user useful field-level feedback instead of a generic "Could not save".

### D5. Contract test instead of live backend test

Ideally the admin SPA would have a Pact-style contract test against a stubbed FastAPI instance. That's outside the scope of this fix. **Decision:** add one lightweight test per resource that constructs a `CategoryCreate` / `MenuItemCreate` / `ModifierCreate` / `SizeOptionCreate` value using only the fields the type allows, and asserts via `JSON.stringify` that the exact bilingual keys are present and no monolingual keys slip through. Combined with the stricter types, this catches regressions without standing up a backend.

### D6. Do not introduce codegen (openapi-typescript)

The argument for codegen is strong — it would permanently prevent this class of drift. The argument against is that it's a cross-cutting change affecting the customer SPA too, and the user wants minimum merge conflict across three parallel worktrees. **Decision:** defer. Propose a `frontend-schema-codegen` change later, once all three Phase 2 fixes have landed.

### D7. File lane as the merge-safety primitive

**Decision:** the proposal's File Lane section is normative, not advisory. Every task in `tasks.md` carries a single target file and that file MUST appear in the lane list. If during implementation an agent discovers that a touch outside the lane is required (e.g. updating `index.tsx` because a prop cascaded), the agent SHALL stop and escalate to the user rather than silently broadening the diff.

## Migration strategy

No DB migration. No runtime migration. The change is type- and form-level only. The backend already accepts the new payloads; the admin SPA simply starts sending them correctly.

Rollout: a single git merge. No feature flag — the current admin is 100% broken, so there is no regression to gate against.

## Test plan

At every task boundary the suite is green:

1. **RED — API client types.** A test constructs a monolingual `{ name: 'x' }` literal and asserts it does NOT satisfy `CategoryCreate`. Expected red = TypeScript error (`@ts-expect-error`). This test is what physically enforces the schema alignment going forward.
2. **RED — API client payloads.** A test mocks `fetch`, calls `createCategory({ type, name_ru, name_en, sort_order: 0, is_visible: true })`, and asserts the POST body is exactly the bilingual payload.
3. **GREEN — type + client rewrite.** Types updated; test 1 compiles clean; test 2 passes.
4. **RED — form field presence.** A component test renders `CategoryList` and asserts two inputs with accessible labels "Название (RU)" / "Name (EN)" exist.
5. **GREEN — form field rewrite.** Inputs added; test 4 passes.
6. Same RED/GREEN loop for `MenuItemFormDialog` (name_ru/en, description_ru/en, sort_order, image_url), `ModifiersPanel` (name_ru/en, sort_order), `SizeOptionsEditor` (label select, no volume_ml).
7. **VERIFY.** Full admin vitest suite green. Manual smoke via the dev stack: create a category, an item, a modifier, a size; all four round-trip without 422.

## Risks and mitigations

- **Risk:** i18n keys drift between RU and EN locale files. **Mitigation:** add a test that asserts `Object.keys(ru.common) === Object.keys(en.common)` (sorted comparison). One task at the end of the tasks list adds this check.
- **Risk:** The `utils.ts` helper `pickLang` might be imported into `index.tsx` through cascading prop drilling. **Mitigation:** `index.tsx` is explicitly excluded from the lane. If cascading demands it, stop and escalate — this likely means the decomposition is wrong.
- **Risk:** `SizeOptionsEditor` currently allows free-text labels. If the DB already has legacy non-SML rows, switching to a `<select>` would prevent editing them. **Mitigation:** the backend schema uses `SizeLabel` enum, so any non-SML rows would already be rejected by Pydantic on the way in — there cannot be legacy rows.
- **Risk:** Large diff in `MenuItemFormDialog` may conflict with a future UX polish change. **Mitigation:** none needed right now; no sibling change touches that file.
- **Risk:** Admin and customer SPAs diverge again later. **Mitigation:** propose a codegen follow-up (out of scope; D6).
