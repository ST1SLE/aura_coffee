# admin-users-ui Specification

## Purpose
TBD - created by archiving change admin-users-ui. Update Purpose after archive.
## Requirements
### Requirement: Admin-only route gating for `/users`

The admin SPA SHALL restrict access to `/users` to users with role `admin`. The sidebar link filter (from `admin-layout-rbac-wiring`) is display-only; a route-level guard MUST also be present. References PDD §4.5, INV-010.

#### Scenario: Barista navigates to /users by URL

- **WHEN** a signed-in barista types `/admin/users` into the browser URL bar
- **THEN** `ProtectedRoute allowedRoles={['admin']}` redirects to `/` (dashboard root) without mounting `UsersPage`

#### Scenario: Admin navigates to /users

- **WHEN** a signed-in admin navigates to `/admin/users`
- **THEN** `UsersPage` mounts and the list query fires against `/api/v1/admin/users`

#### Scenario: Courier navigates to /users by URL

- **WHEN** a signed-in courier types `/admin/users` into the browser URL bar
- **THEN** the route guard redirects away and the list request is never issued

### Requirement: Users list page renders paginated server data

`UsersPage` SHALL render a paginated list of `UserSummary` objects fetched from `GET /api/v1/admin/users`. References PDD §7.1 Phase 6 item 2.

The table SHALL expose columns: `display_name`, `status` (via `UserStatusBadge`), `loyalty_balance` formatted as integer points (e.g. `"1 234 балл."`), `created_at`, and a "Детали" action that opens `UserDetailDialog` for the selected user. The list MUST NOT render `phone` or `phone_hash` in any column (INV-013).

#### Scenario: List renders rows returned by backend

- **WHEN** the list endpoint returns `{ items: [{ id, display_name: "Иван", status: "active", loyalty_balance: 1234, created_at: "2026-04-01T10:00:00Z" }, ...], page, per_page, total }`
- **THEN** the table renders one row per item with `"Иван"`, an active-state badge, `"1 234 балл."`, and a formatted created-at cell

#### Scenario: List pagination advances page parameter

- **WHEN** the admin clicks "next page" with `page=1, per_page=20`
- **THEN** the next request issues `?page=2&per_page=20` and replaces the current rows

#### Scenario: Empty list shows empty state

- **WHEN** the list endpoint returns `{ items: [], page: 1, per_page: 20, total: 0 }`
- **THEN** an empty-state message (`pages.users.empty`) is rendered and no table body rows appear

### Requirement: Status filter tabs drive server-side filtering

`UsersPage` SHALL render four tabs — "All" / "Active" / "Blocked" / "Pending" — that map 1:1 to `?status=` query parameter values `all`, `active`, `blocked`, `pending_verification`. References PDD §6.5.

The "All" tab SHALL omit the `status` query parameter (equivalent to backend's `status=all` default). Switching tabs SHALL reset pagination to page 1.

#### Scenario: Active tab triggers status=active request

- **WHEN** the admin clicks the "Active" tab from the "All" tab with any prior page
- **THEN** the next list request includes `?status=active` AND `page=1`

#### Scenario: Pending tab sends pending_verification value

- **WHEN** the admin clicks the "Pending" tab
- **THEN** the next list request includes `?status=pending_verification` (not `?status=pending`)

#### Scenario: All tab omits status parameter

- **WHEN** the admin clicks the "All" tab after previously filtering by `active`
- **THEN** the next list request URL contains no `status=` query parameter

### Requirement: Debounced display_name search

`UsersPage` SHALL debounce the `display_name` search input by 300ms before firing a list request with `?search=<value>`. References phase6-plan line 214 (`search: str (опционально) — prefix match`).

The search MUST be for `display_name` only; no phone / phone_hash search input MAY exist (INV-013, phase6-plan line 216).

#### Scenario: Rapid typing collapses into single request

- **WHEN** the admin types "ivan" across 4 keystrokes within 300ms
- **THEN** exactly one list request fires, 300ms after the last keystroke, with `?search=ivan`

#### Scenario: Clearing the input drops the search parameter

- **WHEN** the admin clears the search box (empty string)
- **THEN** the next list request after the 300ms debounce contains no `search=` parameter

### Requirement: User detail dialog shows balance, status, and last 20 transactions

`UserDetailDialog` SHALL fetch `GET /api/v1/admin/users/{user_id}` when opened and render:

- Header: `display_name`, `UserStatusBadge(status)`, `created_at`.
- A big-number loyalty balance (points, not rubles).
- A table of the 20 most recent `loyalty_transactions` (already DESC-sorted by the backend), with columns: `type`, `amount` (signed), `balance_after`, `description`, `created_at`.

The UI MUST NOT re-sort the transaction list, MUST NOT render `phone` or `phone_hash`, and MUST NOT embed a user-orders history list.

References PDD §6.5 (user detail), §7.1 Phase 6 item 2, phase6-plan lines 222-231, INV-013.

#### Scenario: Transactions render in backend-provided order

- **WHEN** the backend returns `loyalty_transactions: [{ created_at: "2026-04-19" }, { created_at: "2026-04-18" }, { created_at: "2026-04-10" }]`
- **THEN** the UI renders the rows in exactly that order (newest first)

#### Scenario: Signed amounts are visible

- **WHEN** a transaction has `amount: -50`
- **THEN** the rendered cell text is `"-50"` (with sign); a transaction with `amount: 100` renders as `"+100"`

#### Scenario: Detail dialog never renders phone fields

- **WHEN** the detail endpoint response is rendered
- **THEN** the dialog DOM contains no occurrence of any `phone`, `phone_hash`, or hashed-phone substring

### Requirement: Action buttons are gated by server-provided status

The detail dialog SHALL expose action buttons conditionally on `UserDetailResponse.status`. References PDD §6.5 (User Lifecycle), INV-016.

| status                 | "Заблокировать" | "Разблокировать" | "Скорректировать баллы" |
|------------------------|:----------------:|:-----------------:|:------------------------:|
| `active`               | ✅               | —                 | ✅                       |
| `blocked`              | —                | ✅                | ✅                       |
| `pending_verification` | —                | —                 | —                        |
| `deleted`              | —                | —                 | —                        |

The UI MUST NOT render disabled-but-present buttons; the affordance MUST be absent entirely to prevent foot-guns on forbidden transitions.

#### Scenario: Active user sees block and adjust, not unblock

- **WHEN** `status == "active"`
- **THEN** "Заблокировать" is visible, "Скорректировать баллы" is visible, "Разблокировать" is absent

#### Scenario: Blocked user sees unblock and adjust, not block

- **WHEN** `status == "blocked"`
- **THEN** "Разблокировать" is visible, "Скорректировать баллы" is visible, "Заблокировать" is absent

#### Scenario: Pending user sees no action buttons

- **WHEN** `status == "pending_verification"`
- **THEN** none of the three action buttons render

#### Scenario: Deleted user sees no action buttons

- **WHEN** `status == "deleted"`
- **THEN** none of the three action buttons render (the detail dialog still renders read-only info for audit)

### Requirement: Block confirmation requires explicit checkbox gate

`BlockConfirmDialog` SHALL render when the admin clicks "Заблокировать" from the detail dialog, for every ACTIVE user regardless of `active_orders_count`. References PDD §6.5, §7.6 Order Cancellation Chain.

The warning MUST interpolate `user.active_orders_count` (`N`) and read:
> "Будут отменены N активных заказов с полным рефандом."

An explicit checkbox "Я понимаю, что все активные заказы будут отменены" MUST be unchecked on open. The confirm button ("Заблокировать") MUST be disabled while the checkbox is unchecked, and enabled once checked. The cancel button is always enabled.

After the POST resolves, the dialog SHALL display the result line:
> "Заблокирован. Отменено {cancelled_orders_count} заказов."

The dialog MUST NOT auto-skip for users with `active_orders_count == 0` — the confirm step is a UX contract.

#### Scenario: Confirm button starts disabled

- **WHEN** the confirm dialog opens
- **THEN** the "Заблокировать" confirm button has `disabled` attribute and the checkbox is unchecked

#### Scenario: Checking checkbox enables confirm

- **WHEN** the admin checks the "Я понимаю..." checkbox
- **THEN** the confirm button becomes enabled

#### Scenario: Warning text interpolates N

- **WHEN** the user has `active_orders_count: 3`
- **THEN** the warning text contains the substring `"3 активных заказов"` (or appropriate pluralized form per locale)

#### Scenario: Zero active orders still requires confirm

- **WHEN** the user has `active_orders_count: 0`
- **THEN** the dialog STILL renders, the checkbox starts unchecked, and the confirm button stays disabled until checked

#### Scenario: Confirm triggers onConfirm and shows result

- **WHEN** the admin clicks "Заблокировать" after checking the checkbox
- **THEN** `onConfirm` is invoked (backing `POST /block`), and on success the result line `"Заблокирован. Отменено N заказов."` appears using `cancelled_orders_count` from the response

### Requirement: Loyalty adjust form validates and handles insufficient balance

`LoyaltyAdjustForm` SHALL render when the admin clicks "Скорректировать баллы" from the detail dialog. The form exposes two fields: `delta` (signed integer) and `reason` (textarea, 1..500 chars). References PDD §6.5, phase6-plan lines 269-290, INV-004.

Client-side validation (before any POST):
- `delta` MUST be a non-zero integer; zero → field error, no POST.
- `reason` MUST have `1 <= length <= 500` after trim; empty or overlong → field error, no POST.

Server-side error handling:
- `422` with body indicating `insufficient_balance` MUST render an inline field error under `delta` using i18n key `pages.users.adjust.error_insufficient`.
- Other 422 responses with `loc` paths MUST map `detail[].loc` to their respective field inputs (same `parseFieldErrors` pattern as `api/promocodes.ts`).

On success:
- The parent's refetch callback MUST be invoked (list + detail re-fetch).
- The form fields MUST be cleared.
- A snackbar (via the existing `notifier`) MUST show the localized "Баланс изменён" text.

#### Scenario: delta=0 blocks submit client-side

- **WHEN** the admin enters `delta=0`, `reason="test"` and clicks submit
- **THEN** an inline validation error appears under `delta` and **no** HTTP request is issued

#### Scenario: empty reason blocks submit client-side

- **WHEN** the admin enters `delta=+100`, `reason=""` and clicks submit
- **THEN** an inline validation error appears under `reason` and **no** HTTP request is issued

#### Scenario: overlong reason blocks submit client-side

- **WHEN** the admin enters `reason` with length 501
- **THEN** an inline validation error appears under `reason` and **no** HTTP request is issued

#### Scenario: Successful adjust triggers refetch and snackbar

- **WHEN** the adjust endpoint returns 200 with `{ transaction_id, new_balance, delta }`
- **THEN** the parent's `onSuccess` callback is invoked, the form fields are cleared, and a "Баланс изменён" snackbar is shown

#### Scenario: 422 insufficient_balance shows inline delta error

- **WHEN** the adjust endpoint returns 422 with a body indicating `insufficient_balance` (matched by the substring in `detail` or `code`)
- **THEN** an inline error sourced from `pages.users.adjust.error_insufficient` appears under `delta`, the form fields are **not** cleared, and the parent's `onSuccess` callback is NOT invoked

### Requirement: Adjust button is hidden for PENDING / DELETED users

The detail dialog MUST NOT render "Скорректировать баллы" when `status` is `pending_verification` or `deleted`. References PDD §6.5, phase6-plan line 285 (backend returns 409 for these statuses anyway).

#### Scenario: Pending user has no adjust button

- **WHEN** `status == "pending_verification"`
- **THEN** the "Скорректировать баллы" button is absent from the detail dialog

#### Scenario: Deleted user has no adjust button

- **WHEN** `status == "deleted"`
- **THEN** the "Скорректировать баллы" button is absent from the detail dialog

### Requirement: Mutations invalidate list and detail caches

After any successful `POST /block`, `POST /unblock`, or `POST /loyalty/adjust`, the UI SHALL refetch both the detail query and the parent list query. References phase6-plan line 1009-1010 ("refetch после каждой mutation").

The UI MUST NOT apply optimistic updates that would render a new status, `active_orders_count`, or `loyalty_balance` before the server response is received.

#### Scenario: Successful block refetches detail and list

- **WHEN** `POST /block` resolves with 200
- **THEN** the detail query fires again (status now `blocked`) AND the list query fires again (row updated)

#### Scenario: Successful adjust refetches detail

- **WHEN** `POST /loyalty/adjust` resolves with 200
- **THEN** the detail query fires again and the balance big-number reflects the new value from the refetch, not from local state

### Requirement: `UserStatusBadge` is distinct from `OrderStatus` badge

`UserStatusBadge.tsx` SHALL be a dedicated component that maps `UserStatus` values to color tones. It MUST NOT share a file, import, or alias with any `OrderStatus` badge. References phase6-plan lines 1006-1008.

| status                 | tone                        |
|------------------------|-----------------------------|
| `active`               | success / green             |
| `blocked`              | destructive / red           |
| `pending_verification` | warning / amber             |
| `deleted`              | muted / gray                |

Each label MUST be localized via `pages.users.status.<status>` in both `ru/common.json` and `en/common.json`.

#### Scenario: Blocked badge tone differs from completed-order badge

- **WHEN** comparing `UserStatusBadge` for `blocked` against any order-status badge in the SPA
- **THEN** the components render distinct class names / color utilities (no shared import)

#### Scenario: Every user status has a localized label

- **WHEN** each of `active`, `blocked`, `pending_verification`, `deleted` is rendered
- **THEN** the visible label resolves from `pages.users.status.<status>` in the active locale (no raw enum text on screen)

### Requirement: API client covers five admin-users endpoints

`web/admin/src/api/admin-users.ts` SHALL export five typed functions over `authenticatedFetch`:

- `listUsers({status?, search?, page?, perPage?})` → `UserListResponse` — issues `GET /api/v1/admin/users` with query string.
- `getUser(userId)` → `UserDetailResponse` — issues `GET /api/v1/admin/users/{userId}`.
- `blockUser(userId)` → `BlockUserResponse` — issues `POST /api/v1/admin/users/{userId}/block`.
- `unblockUser(userId)` → `{ user_id, status }` — issues `POST /api/v1/admin/users/{userId}/unblock`.
- `adjustLoyalty(userId, {delta, reason})` → `LoyaltyAdjustResponse` — issues `POST /api/v1/admin/users/{userId}/loyalty/adjust` with JSON body `{delta, reason}`.

All functions MUST propagate `ApiError` (from `api/client.ts`) on non-2xx responses. The `ApiError` instance MUST preserve `status` and `body` for field-level error parsing.

#### Scenario: listUsers builds correct query string

- **WHEN** `listUsers({status: 'active', search: 'иван', page: 2, perPage: 50})` is called
- **THEN** exactly one HTTP request fires to `/api/v1/admin/users?status=active&search=%D0%B8%D0%B2%D0%B0%D0%BD&page=2&per_page=50` (query key is `per_page`, snake_case to match backend)

#### Scenario: getUser builds correct URL

- **WHEN** `getUser("abc-123")` is called
- **THEN** exactly one HTTP request fires to `/api/v1/admin/users/abc-123` with method GET

#### Scenario: adjustLoyalty sends delta and reason in body

- **WHEN** `adjustLoyalty("abc-123", {delta: -50, reason: "test"})` is called
- **THEN** exactly one HTTP POST fires to `/api/v1/admin/users/abc-123/loyalty/adjust` with body `{"delta": -50, "reason": "test"}` and `Content-Type: application/json`

#### Scenario: 422 from adjust propagates ApiError with body

- **WHEN** the adjust endpoint returns 422 with body `{"detail": "insufficient_balance"}`
- **THEN** `adjustLoyalty` rejects with an `ApiError` whose `status === 422` and `body.detail === 'insufficient_balance'`

#### Scenario: 401 triggers login redirect (via client.ts)

- **WHEN** any of the five endpoints returns 401
- **THEN** `authenticatedFetch` (owned by `api/client.ts`) clears the access token and redirects to `/admin/login` — this client layer does not duplicate that logic

### Requirement: i18n keys cover all user-visible strings in RU + EN

All user-visible strings introduced by this change MUST be localized in both `web/admin/src/i18n/locales/ru/common.json` and `.../en/common.json` under the `pages.users.*` namespace. Partitions SHALL include:

- `pages.users.title` + `pages.users.description`
- `pages.users.filters.status.{all,active,blocked,pending}`
- `pages.users.search.placeholder`
- `pages.users.columns.{name,status,balance,created_at,actions}`
- `pages.users.status.{active,blocked,pending_verification,deleted}`
- `pages.users.detail.{balance,transactions,block_button,unblock_button,adjust_button}`
- `pages.users.detail.tx_type.{accrual,redemption,reversal,admin_adjustment}`
- `pages.users.block_confirm.{title,warning,checkbox,confirm,cancel,result}`
- `pages.users.adjust.{title,delta_label,delta_hint,reason_label,reason_placeholder,submit,error_insufficient,success}`
- `pages.users.empty`

No user-visible string MAY appear hard-coded in the components. The existing file layout (`locales/ru/common.json`, `locales/en/common.json` or `locales/ru.json`, `locales/en.json` — whichever the project currently uses) MUST be matched; this change does NOT introduce a new file-layout convention.

#### Scenario: Language switch updates labels

- **WHEN** the user toggles the app language from RU to EN on the users page
- **THEN** every visible label (tabs, columns, status chips, buttons, dialog strings) switches to the EN translation with no fallback placeholder strings visible

#### Scenario: No hard-coded Russian or English strings in components

- **WHEN** scanning the source files under `web/admin/src/pages/Users/` for raw Cyrillic or English user-facing strings (excluding constants like API paths)
- **THEN** every such string is either routed through `t(...)` from `react-i18next` or lives in an enum constant (not user-visible)

