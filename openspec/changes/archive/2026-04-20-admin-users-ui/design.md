## Context

Affected modules: **[web-admin]**.

Phase 6 (PDD §7.1 item 2) ships admin user management end-to-end. The backend half (`admin-users-api`, phase6-plan group 1 merge_order 2) exposes `/api/v1/admin/users/*` with five endpoints: paginated list, detail (with loyalty balance + last 20 transactions + `active_orders_count`), block (cascades §7.6 order cancellations), unblock, and loyalty adjust (single DB transaction, INV-004). The admin SPA today only has a translation-title stub at `web/admin/src/pages/UsersPage.tsx`, so operators have no list / detail / block / adjust path.

The SPA already has a mature mini-framework for admin CRUD in `web/admin/src/pages/Promos/` (page shell + table + dialog triad, plain-TS API in `api/promocodes.ts`, vitest coverage, `useState` form pattern with `parseFieldErrors` for 422 field mapping). This design reuses that pattern verbatim. The `Layout` role filter (phase 5.5 `admin-layout-rbac-wiring`) already hides the "Users" sidebar link from barista and courier, so the only remaining admin-only enforcement needed is the route-level `ProtectedRoute` gate.

## Goals / Non-Goals

**Goals:**

- Provide a role-restricted (admin-only) user list / detail / block / unblock / loyalty-adjust surface mirroring the `Promos/` pattern.
- Keep the UI a thin projection of the backend: no duplicated §6.5 state-machine enforcement, no client-side computation of `active_orders_count`, no client-side `loyalty_balance` derivation. The server MUST remain the source of truth; the UI surfaces its 409 / 422 responses as inline errors or snackbars.
- Localize every user-visible string in `ru` + `en` (PDD bilingual constraint).
- Never render `phone` or `phone_hash` anywhere (INV-013).
- Cover the non-obvious UX rules with vitest tests: status-conditional action buttons, block-confirm checkbox gate, loyalty-adjust validation (`delta != 0`, `reason` length), `insufficient_balance` inline mapping, search debounce, transactions DESC ordering.

**Non-Goals:**

- Self-delete / DELETE user from admin UI (§6.5 customer path, out of Phase 6).
- Rendering `phone` / `phone_hash` (INV-013).
- Embedded order-history list inside detail modal (Phase 7).
- Bulk operations, CSV export, per-user full audit log.
- Client recomputation of `active_orders_count` or `loyalty_balance` (server authoritative).
- Optimistic UI for block / unblock / adjust — correctness > latency for admin-rare mutations.
- Adjusting loyalty for `PENDING` / `DELETED` users (button hidden; backend 409s anyway).
- Any backend, schema, or DB changes — this capability is frontend-only.

## Decisions

### D1. Directory layout: `Users/` mirrors `Promos/`

The shell (`UsersPage.tsx`), the table (`UsersTable.tsx`), the status badge (`UserStatusBadge.tsx`), the detail dialog (`UserDetailDialog.tsx`), the block-confirm dialog (`BlockConfirmDialog.tsx`), and the loyalty-adjust form (`LoyaltyAdjustForm.tsx`) SHALL live in `web/admin/src/pages/Users/`. Rationale: engineers already navigate `Promos/` fluently; a sibling directory keeps tree structure predictable and review diffs localized. Alternative considered: flat `UsersPage.tsx` — rejected because five sub-components with independent test suites would collapse into a single >800-line file and obscure each concern.

The old flat `web/admin/src/pages/UsersPage.tsx` MUST be deleted and the `App.tsx` import redirected to `@/pages/Users` (index file).

### D2. Plain TS types at the API boundary, not zod

`web/admin/src/api/admin-users.ts` SHALL define plain TypeScript interfaces mirroring the Pydantic schemas from `services/core-api/src/core_api/schemas/admin_users.py` (as outlined in phase6-plan lines 299-305). Rationale: the rest of `web/admin/src/api/` (`menu.ts`, `promocodes.ts`, `courier.ts`) uses hand-written TS interfaces, not zod, despite the proposal wording. Introducing zod here would be architectural drift out of scope for this change. Alternative considered: zod or OpenAPI codegen — rejected on consistency grounds.

### D3. Server-owned status + active_orders_count are authoritative

`UserDetailResponse.status` (literal union `active | blocked | pending_verification | deleted`) and `active_orders_count: int` SHALL drive both badge color and action-button visibility. The UI MUST NOT derive either of them on its own. Rationale: §6.5 + §7.6 are explicitly owned by the backend (INV-016: unlisted transitions forbidden); duplicating rules in the client creates drift risk. On a 409 `invalid_user_state` from block/unblock/adjust, the UI SHALL refetch the detail and surface a toast — never retry or rewrite state client-side.

### D4. Inner `ProtectedRoute` guard even though sidebar hides the link

`App.tsx` SHALL wrap `/users` in `<ProtectedRoute allowedRoles={['admin']}>`. Rationale: the sidebar filter is display-only; a barista could type `/admin/users` into the URL bar. Defense-in-depth per INV-010. Mirrors the `/promos` pattern exactly (App.tsx:30-37).

### D5. Separate `UserStatusBadge`, not reuse of `OrderStatus` badge

A dedicated `UserStatusBadge.tsx` SHALL render `UserStatus` with its own palette:

| status                 | color tone                           |
|------------------------|--------------------------------------|
| `active`               | green / success                      |
| `blocked`              | red / destructive                    |
| `pending_verification` | amber / warning                      |
| `deleted`              | gray / muted (tombstone)             |

Rationale: `OrderStatus` and `UserStatus` are different enums with different semantics. Cross-pollinating a single generic `StatusBadge` would couple orders and users via color drift. Alternative considered: a generic `StatusBadge<T>` — rejected because the audience (operator) reads colors for instant recognition and colliding palettes would confuse.

### D6. Action-button visibility matrix (driven by server status)

| server `status`        | "Заблокировать" | "Разблокировать" | "Скорректировать" |
|------------------------|:----------------:|:-----------------:|:------------------:|
| `active`               | ✅               | —                 | ✅                 |
| `blocked`              | —                | ✅                | ✅                 |
| `pending_verification` | —                | —                 | — (hidden)         |
| `deleted`              | —                | —                 | — (hidden)         |

`PENDING` / `DELETED` rows do not even expose a detail dialog action area beyond read-only info. Rationale: §6.5 forbids `PENDING → BLOCKED` and `DELETED → *`; backend returns 409. Hiding the buttons removes a foot-gun. The detail dialog SHALL still render the row (read-only) for debugging.

### D7. Block-confirm dialog is always shown, even when `active_orders_count == 0`

`BlockConfirmDialog.tsx` SHALL render for every block attempt regardless of `active_orders_count`. The warning text SHALL interpolate N (zero is an acceptable value; the text becomes "Будут отменены 0 активных заказов…"). The confirm button SHALL remain disabled until the explicit checkbox "Я понимаю, что все активные заказы будут отменены" is checked. Rationale: UX contract — the act of blocking is destructive for user trust even when no orders are affected. Alternative considered: skip confirmation at N=0 — rejected because the block itself is a non-trivial lifecycle action.

After the POST resolves, the dialog SHALL display the result: "Заблокирован. Отменено {cancelled_orders_count} заказов." (from `BlockUserResponse.cancelled_orders_count`). A "Close" button dismisses the dialog and triggers a detail refetch.

### D8. Loyalty-adjust form: react-hook-form pattern, but via plain useState

Despite the proposal mentioning "react-hook-form as in Promos", `PromoFormDialog.tsx` in fact uses plain `useState` + a field-errors `Record<string, string>` keyed by backend `loc` (see `parseFieldErrors` in `api/promocodes.ts`). `LoyaltyAdjustForm.tsx` SHALL follow this pattern verbatim. Rationale: `react-hook-form` is not a dependency of `web/admin/` (no entry in `package.json`), and adding it for one form is out of scope. The useState pattern handles three fields (delta, reason) trivially.

Client-side validation:
- `delta`: MUST parse to integer; MUST be `!= 0`.
- `reason`: MUST have `length >= 1` after trim; MUST have `length <= 500`.
- Violations SHALL set a field error and suppress the POST.

Server-side error mapping:
- 422 with `detail[*].loc == [..., 'delta']` → inline error under `delta`.
- 422 with `{code: 'insufficient_balance'}` (or `detail` containing that keyword) → inline error under `delta` with `pages.users.adjust.error_insufficient`. The backend returns `422 "insufficient_balance"` per phase6-plan line 275; the UI parses it and maps to delta-field error.
- On success: call `onSuccess()` (parent refetches detail), clear the form, show snackbar "Баланс изменён" via the existing `notifier` component.

### D9. Search debounce at 300ms in the page shell

The `display_name` search input SHALL debounce via a single `useEffect` + `setTimeout` (300 ms) in `UsersPage.tsx`. The table receives the debounced value as a prop; the query key is `["admin-users", status, searchDebounced, page]`. Rationale: matches `Promos/` behavior — shared fetch cache keyed off the debounced value, one in-flight request per final keystroke.

### D10. Status-filter tabs map 1:1 to `?status=` server param

Four tabs SHALL render: `all`, `active`, `blocked`, `pending` (the backend accepts `pending_verification` — the UI tab label says "Pending" but the wire value is `pending_verification`). `all` omits the `status` query param (the backend also accepts `status=all`; omitting is equivalent and matches `Promos/` behavior). Clicking a tab resets pagination to page 1. Rationale: `deleted` users are not surfaced by default — the backend returns 404 on detail for tombstoned users anyway, and a "Deleted" tab would mislead.

### D11. Transaction display in detail dialog

The last 20 `loyalty_transactions` from `UserDetailResponse` SHALL render as a read-only table with columns: `type`, `amount`, `balance_after`, `description`, `created_at`. The list is already DESC-sorted by the backend; the UI MUST NOT re-sort. `amount` SHALL render with a sign (positive amounts prefixed with `+`). `type` SHALL be translated via `pages.users.detail.tx_type.<type>` (accrual / redemption / reversal / admin_adjustment). Rationale: the transaction feed is for audit; no interactive actions on rows.

### D12. Loyalty balance rendered as integer points, not rubles

The backend stores and returns `loyalty_balance: int` as **points** (not kopecks). Rationale: per `packages/shared` loyalty model, the unit is points (1 point = 1 ruble at accrual time, but they are conceptually distinct — admin-adjustments can push balance negative territory out of accrual logic). The big-number display SHALL format as `"1 234 балл."` (Russian spelled with proper locale thousand-separator) / `"1,234 pts"` (English). The adjust form's `delta` input SHALL therefore accept signed integers (points), not currency.

### D13. Refetch-after-every-mutation cache strategy

After any of `blockUser` / `unblockUser` / `adjustLoyalty` resolves successfully, the detail dialog's detail query AND the parent list query SHALL both be invalidated (refetched). Rationale: a successful block changes `status`, `active_orders_count` → 0, and may trigger a server-side loyalty reversal that affects `loyalty_balance`. The list row also changes. Aggressive caching is an anti-pattern for admin-tooling per the feature prompt. Alternative considered: optimistic update → rejected per D3 / correctness.

### D14. "Link to orders" stays out of Phase 6

The detail dialog MUST NOT surface a "К заказам пользователя" link to `OrdersPage?user_id=X`. Rationale: the current `admin-orders-api` list does not accept a `user_id` query param (verified against `services/core-api/src/core_api/routers/admin_orders.py`), so the link would produce an unfilterable page. Phase 7 can introduce that route once the param exists.

### D15. Vitest coverage, not Playwright

Per-component vitest suites: `UsersTable.test.tsx`, `UserStatusBadge.test.tsx`, `UserDetailDialog.test.tsx`, `BlockConfirmDialog.test.tsx`, `LoyaltyAdjustForm.test.tsx`, `api/admin-users.test.ts`. Rationale: matches the rest of `web/admin/`; Playwright coverage for the admin SPA has not been set up and is not in scope for phase 6.

### D16. i18n keys flat under `pages.users.*`

All new strings SHALL live under `pages.users.*` in `ru/common.json` and `en/common.json`, partitioned into sub-objects (`filters`, `search`, `columns`, `status`, `detail`, `detail.tx_type`, `block_confirm`, `adjust`). Rationale: matches `pages.promos.*`, `pages.menu.*` convention; avoids `react-i18next` nested-lookup lint warnings.

### D17. Native HTML checkbox + textarea

`web/admin/src/components/ui/` does not export `Checkbox` or `Textarea` primitives. The block-confirm checkbox SHALL be a native `<input type="checkbox">` styled with Tailwind. The adjust-reason SHALL be a native `<textarea>`. Rationale: adding shadcn primitives is out-of-scope; the native elements are accessible by default (keyboard navigation, screen-reader labels via `<label>` wrapping). Alternative considered: adopt shadcn Checkbox + Textarea — rejected as scope creep.

## Atomicity Analysis (INV-004)

This capability is frontend-only and performs **no state mutations beyond the HTTP boundary** — all atomicity concerns (block-cascading §7.6 refunds, loyalty adjust with `balance + delta` FOR UPDATE, single-transaction commit) live in core-api transactions, owned by the `admin-users-api` capability (phase6-plan lines 234-290).

The SPA MUST therefore:

- Not cache-patch optimistically in a way that could show a successful status flip before the server's atomic commit (D13: await the `block` / `unblock` / `adjust` response before swapping `status` / `loyalty_balance`).
- Not display an intermediate "cancellation in progress" state for the cascading order-cancellation; the server response has `cancelled_orders_count` already resolved per phase6-plan line 253.
- Not split loyalty adjust into two requests (validate + commit) — backend commits in one transaction, so the UI does one POST.

## State Machine Touch Points (PDD §6.5)

The User lifecycle is enforced server-side; the UI observes it via:

- **ACTIVE → BLOCKED**: `POST /block` button on an ACTIVE user (§6.5 row; cascades §7.6 order cancellations — server-side, not UI).
- **BLOCKED → ACTIVE**: `POST /unblock` button on a BLOCKED user (§6.5 row; no cascade).
- **PENDING → ACTIVE**: customer-driven (OTP verification); not an admin UI action.
- **ACTIVE → DELETED**: customer-driven (self-delete); not an admin UI action.
- **BLOCKED → DELETED**: not in PDD §6.5; forbidden (INV-016).
- **DELETED → *** and **PENDING → BLOCKED / DELETED**: forbidden (INV-016); backend 409s; UI does not expose affordance (D6).

No unlisted transitions are exposed in the UI (INV-016).

## 152-FZ Compliance (INV-013)

The UI MUST NOT render:

- `phone` (raw phone number).
- `phone_hash` (stored bcrypt-style hash — non-reversible, meaningless to operator, but displaying it would leak an OAuth-like-equivalent handle).

The `UserDetailResponse` from `admin-users-api` deliberately omits phone fields (phase6-plan line 336). The UI SHALL rely on `display_name` as the sole human-identifier column. If a future backend revision adds `phone` to the response, this UI MUST filter it out before rendering.

Search is by `display_name` only (backend constraint from phase6-plan line 216: "Телефон НЕ искать"). The UI MUST NOT expose a phone-search input.

## Risks / Trade-offs

- **[Risk]** Backend `admin-users-api` not merged before this UI lands → dialog and table receive 404s in dev. **Mitigation:** the phase6-plan explicit merge order (group 1 merge_order 2 before group 2) guarantees backend is merged into `admin_ui_phase` before this UI branch is merged; CI runs `vitest` which uses mocked `fetch`, so unit tests do not depend on backend presence. The integration smoke MUST be verified manually after rebase onto merged `admin_ui_phase`.
- **[Risk]** Admin races with a customer self-verification (PENDING → ACTIVE) between list fetch and block click → list shows PENDING, backend accepts block (ACTIVE row). **Mitigation:** accept the race — the resulting state (BLOCKED with cascaded cancellations) is correct; the UI refetches after the mutation resolves (D13).
- **[Risk]** Admin double-clicks "Заблокировать" (two in-flight blocks) → backend is idempotent per phase6-plan line 257 (returns 200 with `cancelled_orders_count=0` on no-op). **Mitigation:** still disable the submit button while the request is in flight to reduce duplicate requests; the backend idempotency is the safety net.
- **[Risk]** `loyalty_balance` rendered in a cached list row is stale after an admin adjust → operator sees old number. **Mitigation:** D13 invalidates the list after every mutation; the page-shell query re-reads.
- **[Risk]** The backend returns `insufficient_balance` as a raw `422` string — the exact JSON shape (`{code: 'insufficient_balance'}` vs. `{detail: '...'}`) is not fully pinned in phase6-plan. **Mitigation:** the 422-parse helper SHALL look for `'insufficient_balance'` as a substring anywhere in `detail` or top-level `code`; manual smoke-test after backend merge confirms shape. If shape is different, one-line fix.
- **[Risk]** Active orders count shown in the block warning is stale — admin opens detail, waits 10 minutes, a customer places a new order in the meantime, admin clicks block → N in the warning underestimates cascade. **Mitigation:** the backend re-computes at block time; the warning is an advisory, the server is the authority. Post-block result message reports the actual count.
- **[Trade-off]** No optimistic UI for block / adjust → admin perceives a one-round-trip delay. Accepted: correctness > latency for admin-rare, destructive actions.
- **[Trade-off]** Native `<input type=checkbox>` / `<textarea>` instead of shadcn primitives → slight visual inconsistency with the rest of the form. Accepted: adding primitives is out of scope.

## Migration Plan

No DB migration. Deployment steps:

1. Merge this UI change onto `admin_ui_phase` after `admin-users-api` (phase6-plan group 1 merge_order 2) is already on `admin_ui_phase`.
2. `npm run build` in `web/admin/` verifies bundle.
3. `npm test` runs vitest suite with mocked fetch.
4. Smoke test in dev compose:
   - List → filter by Active / Blocked / Pending → search by display_name → paginate.
   - Open detail on an ACTIVE user → verify "Заблокировать" + "Скорректировать" visible, "Разблокировать" absent.
   - Click "Заблокировать" → confirm dialog → check checkbox → confirm → result shows `cancelled_orders_count`; detail refetches to BLOCKED state.
   - Click "Разблокировать" on BLOCKED user → status flips to ACTIVE.
   - Click "Скорректировать баллы" → enter delta=+100 reason="test" → success snackbar, balance refetches.
   - Enter delta=-999999 (to provoke insufficient_balance) → inline error on delta.
   - Verify no `phone` or `phone_hash` rendered anywhere (INV-013 check).
   - Attempt to load `/admin/users` as a barista account → redirected by `ProtectedRoute` (INV-010 check).

Rollback: revert the single commit; `admin_ui_phase` loses the new route. If rollback is needed, restore the flat `UsersPage.tsx` stub alongside the revert.

## Open Questions

- **i18n file organization**: the spec says `locales/ru/common.json` + `locales/en/common.json` (plural form with `common.json`). The `admin-promocodes-ui` archive used `locales/ru.json` + `locales/en.json` (flat). Verify current file layout before writing (inspect `web/admin/src/i18n/` structure) and match existing convention — do not introduce a new layout.
- Exact shape of 422 `insufficient_balance` (see D8 Risk) — resolve during smoke test; the parser is forgiving enough to handle either `{code: 'insufficient_balance'}` or `{detail: 'insufficient_balance'}`.
