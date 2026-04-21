## Why

Phase 6 (PDD §7.1 item 2) requires an admin user management UI. The current `web/admin/src/pages/UsersPage.tsx` is a 12-line i18n-title stub with no list, detail, block/unblock, or loyalty-adjustment affordances. Admins cannot manage user lifecycle (§6.5) or correct loyalty balances through the panel — operator workflow goes through direct DB or backend API calls, breaking the PDD-mandated admin surface (INV-010). The backend `admin-users-api` (phase6-plan group 1, merge_order 2) ships the contracts; this change consumes them.

## What Changes

- **NEW** `web/admin/src/api/admin-users.ts` — typed client for `/api/v1/admin/users/*`: `listUsers`, `getUser`, `blockUser`, `unblockUser`, `adjustLoyalty`. Surfaces `ApiError` for downstream `parseFieldErrors` use (mirror of `api/promocodes.ts`).
- **REMOVE** the flat `web/admin/src/pages/UsersPage.tsx` stub.
- **NEW** `web/admin/src/pages/Users/` directory mirroring the `Promos/` pattern:
  - `index.tsx` re-export shell.
  - `UsersPage.tsx` — page shell: status tabs (All/Active/Blocked/Pending), debounced (300ms) search by `display_name`, pagination, list table, detail dialog mounting.
  - `UsersTable.tsx` — columns: display_name, status (UserStatusBadge), loyalty_balance ("1 234 балл."), created_at, "Детали" button.
  - `UserStatusBadge.tsx` — separate badge for `UserStatus` (active/blocked/pending_verification/deleted) with distinct colors from the OrderStatus badge (own enum, own palette).
  - `UserDetailDialog.tsx` — modal: header (display_name/status/created_at), big loyalty balance, last 20 transactions table (type/amount/balance_after/description/created_at), conditional action buttons.
  - `BlockConfirmDialog.tsx` — explicit-confirm modal with N-active-orders warning (from `user.active_orders_count`) + checkbox gate; result row "Заблокирован. Отменено N заказов."
  - `LoyaltyAdjustForm.tsx` — react-hook-form: `delta` (signed int, ≠0) + `reason` (textarea 1..500). On 422 `insufficient_balance` → inline error on `delta`. On success → refetch + clear + snackbar.
- **MODIFY** `web/admin/src/App.tsx`:
  - Replace `from '@/pages/UsersPage'` with `from '@/pages/Users'`.
  - Wrap the `/users` route in inner `<ProtectedRoute allowedRoles={['admin']}>` (currently shares the admin+barista layout — RBAC matrix says admin-only; mirror the `/promos` pattern).
- **NEW** vitest coverage: `UsersTable.test.tsx`, `UserStatusBadge.test.tsx`, `UserDetailDialog.test.tsx`, `BlockConfirmDialog.test.tsx`, `LoyaltyAdjustForm.test.tsx`, `api/admin-users.test.ts`.
- **NEW** i18n keys in both `ru/common.json` and `en/common.json` covering: title, status filter tabs, search placeholder, table columns, status labels, detail labels (balance, transactions, action buttons), block-confirm (title/warning/checkbox/confirm/cancel/result), loyalty-adjust (title/labels/hint/placeholder/submit/error_insufficient).

## Capabilities

### New Capabilities
- `admin-users-ui`: Admin-only SPA surface for user list, detail, lifecycle actions (block/unblock per §6.5), and manual loyalty adjustments (§6.5 ACTIVE/BLOCKED only). Consumes the backend `admin-users-api` capability. Server is the source of truth for `status`, `active_orders_count`, and `loyalty_balance`; the UI does not duplicate state-machine enforcement (relies on 409/422 from backend for forbidden transitions).

### Modified Capabilities
<!-- none — backend contracts (admin-users-api, phase6-plan group 1) live in a separate capability delivered by the parallel feature. -->

## Non-Goals

- Self-delete / DELETE user from admin UI — `ACTIVE → DELETED` is a customer-side path (§6.5), not in Phase 6 scope.
- Display of phone / phone_hash anywhere in the UI (INV-013: phone_hash is a non-reversible hash; surfacing it is forbidden).
- Embedded order-history list inside the user detail modal — premature scope; deferred to Phase 7 (a "К заказам" link to `OrdersPage` filtered by `user_id` is **not** introduced because `/admin/orders` does not currently expose a `user_id` query-param).
- Bulk operations (bulk-block, bulk-adjust, CSV export) — not in PDD scope.
- Skipping the block-confirm even when `active_orders_count == 0` — UX contract: confirm always required.
- Client-side state-machine enforcement (computing whether a transition is legal) — server returns 409 `invalid_user_state` and the UI surfaces it; no duplicated rules.
- Adjusting loyalty for `PENDING` / `DELETED` users — the "Скорректировать баллы" button is hidden for those statuses (backend returns 409 anyway; we don't even render the affordance).

## Impact

- **MVP Phase:** Phase 6 — Admin Panel (PDD §7.1 item 2).
- **Affected code:**
  - `web/admin/src/pages/Users/` (new directory, 6 components + 5 tests)
  - `web/admin/src/pages/UsersPage.tsx` (deleted)
  - `web/admin/src/api/admin-users.ts`, `web/admin/src/api/admin-users.test.ts` (new)
  - `web/admin/src/App.tsx` (import switch + inner `ProtectedRoute` for `/users`)
  - `web/admin/src/i18n/locales/ru/common.json`, `web/admin/src/i18n/locales/en/common.json` (new `pages.users.*` keys)
- **APIs consumed:**
  - `GET /api/v1/admin/users` (list, query: `status`, `search`, `page`, `per_page`)
  - `GET /api/v1/admin/users/{user_id}` (detail incl. `loyalty_balance`, last 20 `loyalty_transactions`, `active_orders_count`)
  - `POST /api/v1/admin/users/{user_id}/block`
  - `POST /api/v1/admin/users/{user_id}/unblock`
  - `POST /api/v1/admin/users/{user_id}/loyalty/adjust` (body: `{delta, reason}`)
- **Dependencies:** requires `admin-users-api` (phase6-plan group 1, merge_order 2) merged into `admin_ui_phase` before integration. Sidebar gating is already enforced by the role-filtered `Layout` from phase 5.5 `admin-layout-rbac-wiring`; the inner `ProtectedRoute` adds the route-level admin gate.
- **Inviolable Rules touched:**
  - INV-010 (admin-only surface) — enforced via inner `ProtectedRoute`.
  - INV-013 (PII isolation) — UI never renders `phone` or `phone_hash`.
- **No backend, schema, or DB changes** in this capability.
