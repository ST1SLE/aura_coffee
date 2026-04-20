## 1. PREREQ — Verify backend contract and scout existing code

- [x] 1.1 PREREQ [web-admin] Read `openspec/changes/admin-users-ui/design.md` and `openspec/changes/admin-users-ui/specs/admin-users-ui/spec.md` in full before writing code.
- [x] 1.2 PREREQ [web-admin] Inspect `web/admin/src/pages/Promos/` (`PromosPage.tsx`, `PromosTable.tsx`, `PromoFormDialog.tsx`) + `web/admin/src/api/promocodes.ts` and mirror their file layout, naming, and state-management patterns.
- [x] 1.3 PREREQ [web-admin] Inspect `web/admin/src/components/Layout.tsx`, `ProtectedRoute.tsx`, `components/ui/{dialog,button,input,label,badge,table,notifier}.tsx` — confirm no `Checkbox` or `Textarea` primitives exist; native HTML elements will be used per D17.
- [x] 1.4 PREREQ [web-admin] Inspect `web/admin/src/i18n/locales/ru/common.json` + `.../en/common.json` — confirm nested layout; the new `pages.users.*` keys go into those two files (one commit adds both).
- [x] 1.5 PREREQ [web-admin] Verify `web/admin/src/lib/auth.ts` exposes a `useCurrentRole` hook (used by Layout's sidebar filter; the new page doesn't need it directly but the detail dialog may).

## 2. API client — `admin-users.ts`

- [x] 2.1 RED [web-admin] Create `web/admin/src/api/admin-users.test.ts` with failing tests: `listUsers` builds `/api/v1/admin/users?status=active&search=ivan&page=2&per_page=50`; test fails because `../api/admin-users` cannot be imported.
- [x] 2.2 RED [web-admin] Extend `admin-users.test.ts` with `listUsers` omits `status` when value is `'all'`; fails because module missing.
- [x] 2.3 RED [web-admin] Extend `admin-users.test.ts` with `getUser("abc")` fires GET `/api/v1/admin/users/abc`; fails.
- [x] 2.4 RED [web-admin] Extend `admin-users.test.ts` with `blockUser("abc")` fires POST `/api/v1/admin/users/abc/block` with no body; fails.
- [x] 2.5 RED [web-admin] Extend `admin-users.test.ts` with `unblockUser("abc")` fires POST `/api/v1/admin/users/abc/unblock`; fails.
- [x] 2.6 RED [web-admin] Extend `admin-users.test.ts` with `adjustLoyalty("abc", {delta: -50, reason: "test"})` fires POST `/api/v1/admin/users/abc/loyalty/adjust` with JSON body `{delta: -50, reason: "test"}` and `Content-Type: application/json`; fails.
- [x] 2.7 RED [web-admin] Extend `admin-users.test.ts` with 422 response from `adjustLoyalty` rejects with `ApiError` preserving `status === 422` and `body`; fails.
- [x] 2.8 GREEN [web-admin] Create `web/admin/src/api/admin-users.ts` with plain-TS interfaces (`UserStatus`, `UserStatusFilter`, `LoyaltyTransactionType`, `UserSummary`, `UserListResponse`, `LoyaltyTransactionItem`, `UserDetailResponse`, `BlockUserResponse`, `UnblockUserResponse`, `LoyaltyAdjustRequest`, `LoyaltyAdjustResponse`) and the five exported functions built on `authenticatedFetch`. Re-export `ApiError` — passes 2.1–2.7.
- [x] 2.9 REFACTOR [web-admin] Add a `parseAdjustError(err)` helper in `admin-users.ts` that returns `'insufficient_balance'` when the response body's `detail` or `code` field contains that substring (used by the adjust form). No behavior change to callers of the five functions.

## 3. `UserStatusBadge` component

- [x] 3.1 IMPL [web-admin] Create `web/admin/src/pages/Users/UserStatusBadge.tsx` — a presentational component that maps `UserStatus` values to distinct Tailwind color classes (green for `active`, red for `blocked`, amber for `pending_verification`, gray for `deleted`) and renders the localized label from `pages.users.status.<status>`. MUST NOT import anything OrderStatus-related.
- [x] 3.2 TEST [web-admin] Create `web/admin/src/pages/Users/UserStatusBadge.test.tsx` — assert each of the four statuses renders with a distinct class name and the correct localized text. Include a negative assertion that the component's source file does not import any order-badge module.

## 4. `UsersTable` component

- [x] 4.1 IMPL [web-admin] Create `web/admin/src/pages/Users/UsersTable.tsx` — pure presentational table accepting `{items: UserSummary[], onSelect: (id) => void}`. Uses shadcn `Table` primitive. Columns: display_name, status (via `UserStatusBadge`), loyalty_balance formatted as `"<N> балл."` / `"<N> pts"` via `Intl.NumberFormat(locale).format(n)`, created_at (ISO → localized date), "Детали" button.
- [x] 4.2 TEST [web-admin] Create `web/admin/src/pages/Users/UsersTable.test.tsx`:
  - Renders one row per passed-in item.
  - Clicking "Детали" invokes `onSelect` with the correct user id.
  - Loyalty balance cell formats `1234` as `"1 234 балл."` under `ru` locale.
  - Empty `items` array renders the empty-state row (`pages.users.empty`).
  - The DOM contains no occurrence of `phone` or `phone_hash` substrings.

## 5. `BlockConfirmDialog` component

- [x] 5.1 IMPL [web-admin] Create `web/admin/src/pages/Users/BlockConfirmDialog.tsx` — shadcn `Dialog` with three states (`idle` / `loading` / `done`). Props: `{open, onClose, user: UserDetailResponse, onConfirmed: (res: BlockUserResponse) => void}`. Renders interpolated warning using `active_orders_count`, a native `<input type="checkbox">` + `<label>`, and Confirm/Cancel buttons. Confirm is disabled while the checkbox is unchecked or `state === 'loading'`. On confirm → call `blockUser(user.id)` → on success move to `done` state and render the result text using `cancelled_orders_count`.
- [x] 5.2 TEST [web-admin] Create `web/admin/src/pages/Users/BlockConfirmDialog.test.tsx`:
  - Confirm button starts disabled, checkbox unchecked.
  - Checking the checkbox enables confirm.
  - Warning text substrings the provided `active_orders_count` (test with N=3 and N=0).
  - `active_orders_count: 0` still renders the dialog and starts with confirm disabled.
  - Clicking confirm invokes the mocked `blockUser` API; on resolved response, `onConfirmed` is called with the response and the result line `"Заблокирован. Отменено N заказов."` appears using the response's `cancelled_orders_count`.

## 6. `LoyaltyAdjustForm` component

- [x] 6.1 IMPL [web-admin] Create `web/admin/src/pages/Users/LoyaltyAdjustForm.tsx` — useState-managed form with `delta` (numeric text input, signed) and `reason` (native `<textarea>` with `maxLength=500`). Props: `{userId: string, onSuccess: () => void}`. Client validation per D8: `delta` must parse to non-zero integer, `reason` length ∈ [1, 500]. On submit → call `adjustLoyalty(userId, {delta, reason})`. On success → call `onSuccess()`, clear inputs, invoke notifier with `pages.users.adjust.success`. On 422 → use `parseAdjustError` + `parseFieldErrors` to map to inline errors (insufficient_balance → delta field error via `pages.users.adjust.error_insufficient`).
- [x] 6.2 TEST [web-admin] Create `web/admin/src/pages/Users/LoyaltyAdjustForm.test.tsx`:
  - `delta=0`, `reason="test"` → client-side inline error under delta, no HTTP request issued.
  - `delta=+100`, `reason=""` → client-side inline error under reason, no HTTP request.
  - `reason` length 501 → client-side inline error under reason, no HTTP request.
  - Happy path: `delta=+50`, `reason="manual bonus"` → mocked POST resolves → `onSuccess` is invoked, form fields are cleared, notifier is called with success key.
  - Mocked POST rejects with `ApiError(422, {detail: 'insufficient_balance'})` → inline error resolved from `pages.users.adjust.error_insufficient` appears under delta; form fields NOT cleared; `onSuccess` NOT invoked.

## 7. `UserDetailDialog` component

- [x] 7.1 IMPL [web-admin] Create `web/admin/src/pages/Users/UserDetailDialog.tsx` — shadcn `Dialog`. Props: `{userId: string | null, open: boolean, onClose: () => void, onMutated: () => void}`. On open → `getUser(userId)`; on close → clear local state. Renders: header (display_name, `UserStatusBadge`, created_at), big-number loyalty balance, a transactions `Table` (columns: type translated via `pages.users.detail.tx_type.*`, amount with sign prefix, balance_after, description, created_at). Conditional action buttons per D6. Block → opens `BlockConfirmDialog`; Unblock → direct `unblockUser` (with a simpler confirm toast — no checkbox gate required by §6.5 row since no cascade); Adjust → opens `LoyaltyAdjustForm` in a nested section or small inline dialog. After any mutation resolves → call `onMutated()` (parent refetches list) AND refetch the detail query.
- [x] 7.2 TEST [web-admin] Create `web/admin/src/pages/Users/UserDetailDialog.test.tsx`:
  - Renders transactions in the backend-provided order (DESC-confirming snapshot with three rows).
  - `status='active'` → Block + Adjust buttons visible; Unblock absent.
  - `status='blocked'` → Unblock + Adjust visible; Block absent.
  - `status='pending_verification'` → none of the three buttons rendered.
  - `status='deleted'` → none of the three buttons rendered.
  - Signed-amount formatting: `amount=-50` renders text `"-50"`; `amount=100` renders `"+100"`.
  - DOM contains no `phone` / `phone_hash` substrings.
  - Clicking Block opens `BlockConfirmDialog`; on `onConfirmed` callback → `onMutated` is invoked and detail refetches.
  - Clicking Unblock fires `unblockUser`; on success → `onMutated` invoked and detail refetches.
  - Opening Adjust and completing the form → `onMutated` invoked and detail refetches.

## 8. `UsersPage` shell

- [x] 8.1 IMPL [web-admin] Create `web/admin/src/pages/Users/UsersPage.tsx` — page shell that owns:
  - Status tabs (4) → `status` state.
  - Debounced search input (300ms) → `searchDebounced` state.
  - Pagination (prev/next/page-number) → `page` state.
  - Query key `[admin-users, status, searchDebounced, page]` — fetches via `listUsers`.
  - Renders `UsersTable` with `onSelect` opening `UserDetailDialog`.
  - `onMutated` from detail dialog triggers list refetch.
  - Use simple `useEffect` + fetch + local state (no react-query dependency; mirror `PromosPage.tsx` approach). If project already uses a fetch-cache helper, reuse it.
- [x] 8.2 IMPL [web-admin] Create `web/admin/src/pages/Users/index.tsx` — single-line re-export of `UsersPage` to match the `Promos/index.tsx` pattern.
- [x] 8.3 TEST [web-admin] Create `web/admin/src/pages/Users/UsersPage.test.tsx`:
  - Default render → fires `listUsers()` with no `status` and `page=1`.
  - Clicking "Active" tab → refetch with `status=active`, `page=1`.
  - Typing "ivan" across 4 keystrokes within 300ms → fires exactly ONE refetch (after debounce) with `search=ivan`.
  - Clearing search → refetch drops `search` param.
  - Clicking pagination "next" → refetch with `page=2`.

## 9. Route wiring in `App.tsx`

- [x] 9.1 IMPL [web-admin] Modify `web/admin/src/App.tsx`:
  - Replace import `{ UsersPage } from '@/pages/UsersPage'` with `{ UsersPage } from '@/pages/Users'`.
  - Wrap the `/users` `<Route>` in an inner `<ProtectedRoute allowedRoles={['admin']}>` mirroring the existing `/promos` wrapper (App.tsx:30-37).
- [x] 9.2 IMPL [web-admin] Delete `web/admin/src/pages/UsersPage.tsx` (the 12-line stub); git-remove — the page now lives in `pages/Users/`.

## 10. i18n coverage

- [x] 10.1 IMPL [web-admin] Add `pages.users.*` keys to `web/admin/src/i18n/locales/ru/common.json` covering: `title`, `description`, `empty`, `filters.status.{all,active,blocked,pending}`, `search.placeholder`, `columns.{name,status,balance,created_at,actions}`, `status.{active,blocked,pending_verification,deleted}`, `detail.{balance,transactions,block_button,unblock_button,adjust_button,tx_type.{accrual,redemption,reversal,admin_adjustment}}`, `block_confirm.{title,warning,checkbox,confirm,cancel,result}`, `adjust.{title,delta_label,delta_hint,reason_label,reason_placeholder,submit,success,error_insufficient}`, and a balance-format-unit key (`balance_unit_short`, e.g. `"балл."` / `"pts"`).
- [x] 10.2 IMPL [web-admin] Mirror every key from 10.1 into `web/admin/src/i18n/locales/en/common.json` with English translations. Keep the key tree exactly in sync — the `parity.test.ts` i18n test MUST pass.
- [x] 10.3 VERIFY [web-admin] Run `npm test -- i18n/locales/__tests__/parity.test.ts` — passes (no missing keys, no extra keys).

## 11. Integration verification

- [x] 11.1 VERIFY [web-admin] Run `npm test` from `web/admin/` — all new vitest suites pass (api/admin-users.test.ts, UserStatusBadge, UsersTable, BlockConfirmDialog, LoyaltyAdjustForm, UserDetailDialog, UsersPage).
- [x] 11.2 VERIFY [web-admin] Run `npm run build` from `web/admin/` — production bundle compiles without TypeScript errors.
- [x] 11.3 VERIFY [web-admin] Run `npm run lint` (or equivalent) from `web/admin/` — no new lint errors introduced.
- [x] 11.4 VERIFY [web-admin] Manual smoke test (optional, documented in design.md "Migration Plan"): after `admin-users-api` is merged into `admin_ui_phase`, start dev compose, sign in as admin, open `/users`, verify list/detail/block/unblock/adjust happy paths in the browser. Verify that signing in as barista and typing `/admin/users` lands on `/` (dashboard), not the users page (INV-010 check). Verify no `phone` or `phone_hash` visible anywhere in the rendered UI (INV-013 check). _Deferred to post-merge of admin-users-api — backend endpoints not available in this worktree per parallel orchestration design._
