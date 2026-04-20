## Context

Affected modules: **[web-admin]**.

Phase 5 (PDD §7.1 item 1) ships admin promocode management end-to-end. The backend half (`admin-promocodes-api`, phase5-plan group 1 merge_order 2) exposes `/api/v1/admin/promocodes` with a server-computed `state` field (INACTIVE / ACTIVE / EXPIRED / EXHAUSTED, PDD §6.6) and distinct `activate` / `deactivate` POST actions. The admin SPA today only contains a translation-title stub at `web/admin/src/pages/PromosPage.tsx`, so operators have no CRUD path.

The SPA already has a mature mini-framework for admin CRUD in `web/admin/src/pages/Menu/` (page shell + table + form-dialog triad, zod-typed API in `api/menu.ts`, vitest coverage). This design reuses that pattern to keep mental overhead low. The Layout role filter (from phase 3.5 `admin-role-wiring`) already hides the "Promos" sidebar link from barista and courier, so the only remaining admin-only enforcement needed in this change is the `ProtectedRoute allowedRoles`.

## Goals / Non-Goals

**Goals:**

- Provide a role-restricted (admin-only) promocode CRUD surface mirroring the Menu pattern.
- Keep the UI a thin projection of the backend: no duplicated state-computation, no duplicated lock-after-use rules — the server 422s on violations and the UI renders read-only affordances consistent with those rules.
- Localize every user-visible string in `ru` + `en` (PDD bilingual constraint).
- Cover the non-obvious UX rules with vitest tests: lock-after-use disable matrix, rubles↔kopecks conversion, state-driven action visibility, search debounce, state-filter tab reload.

**Non-Goals:**

- DELETE endpoint / destructive archive (PDD §6.6 forbids).
- Client recomputation of `state` (server is source of truth; INV-011).
- Admin loyalty point adjustments (Phase 6, out of scope).
- Cron-driven EXPIRED / EXHAUSTED automation (deferred, phase5-plan).
- Bulk operations, CSV export, per-user usage log UI.
- Any schema / DB / backend changes — this capability is frontend-only.

## Decisions

### D1. Directory layout: split `Promos/` mirrors `Menu/`

The shell (`PromosPage.tsx`), the table (`PromosTable.tsx`), and the form dialog (`PromoFormDialog.tsx`) SHALL live in `web/admin/src/pages/Promos/`, mirroring the `Menu/` pattern. Rationale: engineers already navigate `Menu/` fluently; a sibling directory keeps tree structure predictable and review diffs localized. Alternative considered: keep a single flat `PromosPage.tsx` — rejected because the dialog + table together exceed 400 lines and obscure each concern.

The old flat `web/admin/src/pages/PromosPage.tsx` MUST be deleted and the App.tsx import redirected to `@/pages/Promos` (index file).

### D2. zod at the API boundary, not auto-generated OpenAPI types

`web/admin/src/api/promocodes.ts` SHALL define zod schemas that mirror `services/core-api/src/core_api/schemas/promocode.py`. Rationale: the rest of `web/admin/src/api/` (`menu.ts`, `courier.ts`) uses hand-written zod; introducing OpenAPI codegen here would be an out-of-scope architectural drift. Runtime zod parsing catches shape regressions on the client side before they reach React Query consumers. Alternative considered: raw `fetch` + TS types only — rejected because silent shape drift has been a recurring bug class in this SPA.

### D3. Server-computed `state` is authoritative in the UI

`PromocodeResponse.state` (literal union `inactive | active | expired | exhausted`) SHALL drive both the table chip color and the action-button visibility / disabled matrix. The UI MUST NOT derive `state` from `is_active + valid_until + current_uses + max_uses` on its own. Rationale: PDD §6.6 explicitly designates the server as sole owner of that mapping; duplicating it in the client creates drift risk (INV-011). Alternative considered: derive on the client to avoid a round-trip on optimistic flips — rejected; activate/deactivate responses return the refreshed `PromocodeResponse` with new `state`, so React Query cache invalidation gives the right state without recomputation.

### D4. Activate / Deactivate are separate requests, not part of PATCH

Activation and deactivation SHALL be dedicated POST endpoints (`.../activate`, `.../deactivate`) invoked from the edit dialog footer or the table action buttons. The PATCH payload MUST NOT include `is_active`. Rationale: the backend enforces different preconditions (activate requires `valid_until`, forbids EXPIRED / EXHAUSTED; deactivate forbids EXPIRED) and returns distinct error codes. Treating `is_active` as a patchable field would either bypass those server guards or require the UI to replicate them. Alternative considered: send `is_active=true/false` inside PATCH — rejected per PDD §6.6 transition guards and backend API contract.

### D5. Lock-after-use fields: render-disable + tooltip, server still 422s

When `current_uses > 0`, the `code`, `discount_type`, and `discount_value` inputs SHALL render as disabled with a tooltip sourced from `pages.promos.locked_hint`. The form MUST still accept a 422 response for those fields (e.g. in a race where the first use lands while the dialog is open) and show the field-level error. Rationale: UX-layer prevention is the happy path; the server guard is the correctness guarantee. Never bypass the server in edit rules.

### D6. Rubles ↔ kopecks at the dialog save/load boundary

`discount_value` (when `discount_type === 'fixed_amount'`) and `min_order_amount` are rubles in the UI, kopecks on the wire. The dialog MUST multiply by 100 on submit and divide by 100 on load, rounding to two decimals for display. `discount_value` when `discount_type === 'percent'` is an integer percentage (0 < n ≤ 100) and MUST NOT be converted. Rationale: PDD stores money as integer kopecks globally; admins think in rubles. Alternative considered: push conversion into the zod schema's `transform` — rejected because a zod `transform` collapses parse+transform into one step, making it harder to render raw values in the input while displaying formatted values elsewhere.

### D7. Search debounce at 300ms in the page shell, not inside the input

The code-search input SHALL debounce via a single `useEffect` + `setTimeout` in `PromosPage.tsx` (300 ms). The table receives the debounced value as a prop and the query key is `["promos", state, codeDebounced, page]`. Rationale: a shared React Query cache keyed off the debounced value gives a single in-flight request per final keystroke without an extra library.

### D8. State-filter tabs map 1:1 to `?state=` server param

Five tabs SHALL render: `all`, `active`, `inactive`, `expired`, `exhausted`. `all` omits the `state` query param. Rationale: the backend already accepts `state=all` per phase5-plan; no derived UI-only filtering. Clicking a tab resets pagination to page 1 (React Query key change).

### D9. Route-level admin guard even though sidebar hides the link

`App.tsx` SHALL wrap `/promos` in `<ProtectedRoute allowedRoles={['admin']}>`. Rationale: the sidebar filter is display-only; a barista could type `/admin/promos` into the URL bar. Defense-in-depth per INV-010 (the backend would 403 anyway, but a blank-page route is the right UX).

### D10. Table action-button state machine

| server `state` | row actions visible                             |
|----------------|--------------------------------------------------|
| `active`       | Edit, Deactivate                                 |
| `inactive`     | Edit, Activate                                   |
| `expired`      | Edit (valid_until / max_uses only), no activate  |
| `exhausted`    | Edit, no activate                                |

Disabled while the mutation is in flight. Inside the edit dialog footer the same rules apply: Activate button SHALL render only when `!is_active && state !== 'expired' && state !== 'exhausted'`, Deactivate SHALL render only when `is_active === true`.

### D11. i18n keys flat under `pages.promos.*`

All new strings SHALL live under `pages.promos.*` in `ru.json` and `en.json`, partitioned into sub-objects (`state`, `state_chip`, `columns`, `form`, `actions`, `errors`). Rationale: matches the `pages.menu.*`, `pages.orders.*` convention; lint-free for `react-i18next` nested lookups.

### D12. Vitest coverage, not Playwright

Per-component vitest suites (`PromosTable.test.tsx`, `PromoFormDialog.test.tsx`, `PromosPage.test.tsx`, `api/promocodes.test.ts`). Rationale: matches the rest of `web/admin/`; Playwright coverage for the admin SPA has not been set up and is not in scope for phase 5.

## Atomicity Analysis (INV-004)

This capability is frontend-only and performs **no state mutations beyond the HTTP boundary** — all atomicity concerns (promocode create, patch, activate/deactivate, and the downstream `current_uses` increment inside checkout) live in core-api transactions, owned by the `admin-promocodes-api` and `promocode-race-fix` capabilities. The SPA MUST therefore:

- Not cache-patch optimistically in a way that could show a successful state flip before the server's atomic commit (INV-004 requires single-transaction atomicity; the UI SHALL await the `activate` / `deactivate` response before swapping `state`).
- Not display `current_uses` drift client-side — re-fetch after any mutation that could change it.

## State Machine Touch Points (PDD §6.6)

The Promocode lifecycle (INACTIVE → ACTIVE → {EXPIRED | EXHAUSTED | INACTIVE}) is enforced server-side; the UI observes it via:

- **INACTIVE → ACTIVE**: `POST /activate` button (requires `valid_until`, forbids expired/exhausted).
- **ACTIVE → INACTIVE**: `POST /deactivate` button (forbids expired).
- **ACTIVE → EXPIRED**: computed by server on read, never a UI action.
- **ACTIVE → EXHAUSTED**: computed by server on read, never a UI action.

No unlisted transitions are exposed in the UI (INV-016).

## Risks / Trade-offs

- **[Risk]** Backend `admin-promocodes-api` not merged before this UI lands → dialog and table receive 404s in dev. **Mitigation:** the phase5-plan explicit merge order guarantees backend is merged into `delivery` before this UI branch rebases; CI runs `pytest` + `npm test`, the latter uses mocked fetch so does not depend on backend presence. The integration-smoke must be verified manually after rebase.
- **[Risk]** Server-provided `state` is computed at list time; a promocode that crosses `valid_until` during the session stays "active" in the cached list until refetch → operator acts on stale data. **Mitigation:** React Query `staleTime: 30s`, and any mutation invalidates the list query. Acceptable for admin tooling.
- **[Risk]** The 300 ms debounce + React Query refetch on every state-tab click produces extra requests when the admin is rapidly toggling filters → small burst of GETs. **Mitigation:** the endpoint is paginated and indexed; phase 5 traffic is internal admin only, so the extra requests are harmless.
- **[Risk]** Forgetting to uppercase `code` client-side before display → admin types `weekend10`, server stores `WEEKEND10`, table re-render now shows uppercase, admin thinks a duplicate was created. **Mitigation:** show the server-canonical (uppercase) form after save by re-reading from the server response.
- **[Trade-off]** Not using OpenAPI codegen → slight duplication between Python pydantic schema and TS zod schema. Accepted: consistent with the rest of `web/admin/src/api/`; introducing codegen is a separate architectural concern.
- **[Trade-off]** No optimistic UI for activate/deactivate → a perceptible delay (one round-trip) on toggle. Accepted: correctness > latency for admin-rare actions.

## Migration Plan

No DB migration. Deployment steps:

1. Merge this UI change onto `delivery` after `admin-promocodes-api` is already on `delivery` (phase5-plan enforces merge order 2 < 4).
2. `npm run build` in `web/admin/` verifies bundle.
3. Smoke test in dev compose: create → activate → list-filter → deactivate → reactivate → edit-with-uses=0 → simulate a usage via checkout → verify lock-after-use.

Rollback: revert the single commit; `delivery` loses the new route and `PromosPage.tsx` stub path no longer exists. If rollback is needed, restore the flat stub file alongside the revert.

## Open Questions

- None blocking. The PDD and phase5-plan resolve the primary questions (state rules, lock-after-use, archive-style). Minor UX polish (exact shadcn chip colors, table density) SHOULD follow the visual language of `Menu/` without a separate decision.
