## Why

Phase 5 (PDD §7.1) requires an admin promocode management UI. The current `web/admin/src/pages/PromosPage.tsx` is a flat i18n-title stub with no CRUD affordances. Admins cannot create, browse, filter, edit, activate, or deactivate promocodes through the admin panel — the only path is direct DB access, which breaks the operator workflow the PDD mandates (INV-010).

## What Changes

- **NEW** `web/admin/src/api/promocodes.ts` — zod-typed client for the `/api/v1/admin/promocodes` CRUD + activate/deactivate endpoints introduced by the `admin-promocodes-api` feature (phase5-plan group 1).
- **NEW** `web/admin/src/pages/Promos/` directory mirroring the `Menu/` pattern: `PromosPage.tsx` shell (state tabs + code search + create button + table), `PromosTable.tsx` (list with state chip, discount preview, valid_until, uses, row-level activate/deactivate), `PromoFormDialog.tsx` (create + edit form with lock-after-use UX and activate/deactivate buttons).
- **REMOVE** the flat `web/admin/src/pages/PromosPage.tsx` stub; wire App.tsx to `@/pages/Promos`.
- Scope `/promos` to `allowedRoles=['admin']` in `App.tsx` (currently shares the admin+barista layout).
- Add `pages.promos.*` i18n keys in both `ru` and `en` locales covering title, state tabs, state chips, table columns, form fields, actions, field-level errors, and the locked-after-use tooltip.
- Add vitest coverage: `PromosTable.test.tsx`, `PromoFormDialog.test.tsx`, `PromosPage.test.tsx`, `api/promocodes.test.ts`.

## Capabilities

### New Capabilities
- `admin-promocodes-ui`: Admin-only SPA page for promocode CRUD, state filtering, search, activate/deactivate — consumes the backend `admin-promocodes-api` capability. Server-computed `state` drives rendering; UI does not duplicate the INACTIVE/ACTIVE/EXPIRED/EXHAUSTED mapping (PDD §6.6).

### Modified Capabilities
<!-- none — the backend promocode lifecycle / admin API live under separate capabilities delivered in group 1. -->

## Non-Goals

- Physical DELETE of promocodes — archive-style only per PDD §6.6 (deactivate = soft archive).
- Client-side recomputation of `state` — server is the source of truth; the UI renders the `state` field from list/detail responses.
- Admin adjustment of customer loyalty balances — deferred to Phase 6 (users admin).
- Cron-driven transitions to EXPIRED / EXHAUSTED — deferred to Phase 6 (phase5-plan explicit).
- Bulk operations (bulk activate, bulk export) — not in PDD scope.
- Usage audit / per-user redemption log UI — out of scope; only the aggregate `current_uses` is surfaced.

## Impact

- **MVP Phase:** Phase 5 — Loyalty & Promocodes (PDD §7.1 item 1).
- **Affected code:**
  - `web/admin/src/pages/Promos/` (new directory)
  - `web/admin/src/pages/PromosPage.tsx` (deleted)
  - `web/admin/src/api/promocodes.ts`, `web/admin/src/api/promocodes.test.ts` (new)
  - `web/admin/src/App.tsx` (import + role tightening)
  - `web/admin/src/i18n/locales/ru.json`, `web/admin/src/i18n/locales/en.json`
- **APIs consumed:** `/api/v1/admin/promocodes` GET/POST, `/api/v1/admin/promocodes/{id}` GET/PATCH, `/api/v1/admin/promocodes/{id}/activate`, `/api/v1/admin/promocodes/{id}/deactivate` (admin-only per rbac_matrix; INV-010).
- **Dependencies:** requires `admin-promocodes-api` (phase5-plan group 1, merge_order 2) to be merged into `delivery` before integration. Sidebar gating already enforced by the Layout role filter from phase 3.5 `admin-role-wiring`.
- **Inviolable Rules touched:** INV-010 (admin-only surface), INV-011 (promocode quotas — UI shows server-provided `state` without duplicating enforcement).
- **No schema / DB changes.** No backend code changes in this capability.
