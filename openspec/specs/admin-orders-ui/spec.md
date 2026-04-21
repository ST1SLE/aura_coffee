# admin-orders-ui Specification

## Purpose
TBD - created by archiving change admin-orders-ui. Update Purpose after archive.
## Requirements
### Requirement: Admin orders API client

The admin SPA SHALL expose an API client module at `web/admin/src/api/admin-orders.ts` containing exactly four functions — `listAdminOrders`, `getAdminOrder`, `updateOrderStatus`, `cancelAdminOrder` — all built on the existing `authenticatedFetch` + `ApiError` primitives from `@/api/client`. The module MUST NOT contain state-machine logic, role gating, or transition validation; those concerns live in React components and on the server (INV-016).

- `listAdminOrders(params?: ListAdminOrdersParams): Promise<OrderListResponse>` SHALL issue `GET /api/v1/admin/orders` with query-params derived from `params` as follows: `status` → emitted unless `undefined` or the string `"all"`; `type` → emitted unless `undefined`; `page` → emitted when a positive integer; `per_page` → emitted when a positive integer. Omitted params MUST NOT appear in the URL at all (no empty `?status=` or trailing `&`).
- `getAdminOrder(orderId: string): Promise<OrderResponse>` SHALL issue `GET /api/v1/admin/orders/{orderId}`.
- `updateOrderStatus(orderId: string, newStatus: OrderStatus): Promise<OrderResponse>` SHALL issue `PATCH /api/v1/orders/{orderId}/status` with JSON body `{"new_status": "<value>"}`. The body field name SHALL be `new_status`, matching `core_api.schemas.order.OrderStatusUpdate`.
- `cancelAdminOrder(orderId: string, reason?: string | null): Promise<OrderResponse>` SHALL issue `POST /api/v1/orders/{orderId}/cancel` with JSON body `{"reason": <reason or null>}`. When `reason` is `undefined` the body field SHALL be `null`.
- Any non-2xx response SHALL throw `ApiError` from `@/api/client`. The client MUST NOT remap 403 to a domain-specific error type.

#### Scenario: listAdminOrders builds URL with all params set
- **WHEN** `listAdminOrders({status: 'preparing', type: 'delivery', page: 2, per_page: 20})` is called
- **THEN** exactly one `fetch` call SHALL be made AND the request URL SHALL contain `/api/v1/admin/orders` with query params `status=preparing`, `type=delivery`, `page=2`, `per_page=20`

#### Scenario: listAdminOrders omits undefined params
- **WHEN** `listAdminOrders({status: 'active'})` is called
- **THEN** the request URL SHALL contain `status=active` AND SHALL NOT contain any of `type=`, `page=`, `per_page=`

#### Scenario: listAdminOrders with no params hits the bare endpoint
- **WHEN** `listAdminOrders()` is called
- **THEN** the request URL SHALL equal `/api/v1/admin/orders` with no query string

#### Scenario: listAdminOrders propagates 403 as ApiError
- **GIVEN** the server returns HTTP 403 with body `{"detail": "forbidden"}`
- **WHEN** `listAdminOrders()` is awaited
- **THEN** the promise SHALL reject with an `ApiError` instance whose `status === 403`

#### Scenario: getAdminOrder issues a detail GET
- **WHEN** `getAdminOrder('00000000-0000-0000-0000-000000000001')` is called
- **THEN** the request URL SHALL end with `/api/v1/admin/orders/00000000-0000-0000-0000-000000000001` AND the method SHALL be `GET`

#### Scenario: updateOrderStatus sends the correct wire body
- **WHEN** `updateOrderStatus('abc', 'preparing')` is called
- **THEN** the request URL SHALL end with `/api/v1/orders/abc/status`, the method SHALL be `PATCH`, the `Content-Type` header SHALL be `application/json`, and the JSON body SHALL equal `{"new_status": "preparing"}`

#### Scenario: cancelAdminOrder with no reason sends null
- **WHEN** `cancelAdminOrder('abc')` is called
- **THEN** the request URL SHALL end with `/api/v1/orders/abc/cancel`, the method SHALL be `POST`, and the JSON body SHALL equal `{"reason": null}`

#### Scenario: cancelAdminOrder passes the provided reason
- **WHEN** `cancelAdminOrder('abc', 'customer asked')` is called
- **THEN** the JSON body SHALL equal `{"reason": "customer asked"}`

### Requirement: Orders page route and directory layout

The admin SPA SHALL replace the single-file stub at `web/admin/src/pages/OrdersPage.tsx` with a directory `web/admin/src/pages/Orders/` that exports the page through `index.tsx`. The route `/orders` in `web/admin/src/App.tsx` SHALL import from `@/pages/Orders` (barrel) rather than `@/pages/OrdersPage`. The route's `allowedRoles` SHALL remain `{ADMIN, BARISTA}` as set by Phase 5.5.

Directory contents:
- `index.tsx` — re-exports `OrdersPage`
- `OrdersPage.tsx` — container component
- `OrdersTable.tsx` — presentational table
- `OrdersTable.test.tsx`
- `OrderDetailDialog.tsx` — modal for a single order
- `OrderDetailDialog.test.tsx`
- `StatusBadge.tsx` — status badge component (locally scoped)

#### Scenario: Orders barrel exports OrdersPage
- **WHEN** a caller imports `{ OrdersPage }` from `@/pages/Orders`
- **THEN** the import SHALL resolve to the `OrdersPage` React function component

#### Scenario: App.tsx wires the new barrel
- **WHEN** a test reads `web/admin/src/App.tsx`
- **THEN** the file SHALL import `OrdersPage` from `@/pages/Orders` (directory barrel) AND SHALL NOT import from `@/pages/OrdersPage` (single-file form)

#### Scenario: Legacy stub file is removed
- **WHEN** a filesystem check runs after this change
- **THEN** `web/admin/src/pages/OrdersPage.tsx` SHALL NOT exist

### Requirement: Orders list view — filters, pagination, polling

`OrdersPage` SHALL render:
- A status-tab row with exactly seven tabs in this order: `active`, `paid`, `preparing`, `ready`, `in_delivery`, `completed`, `cancelled`. The "active" tab SHALL be selected by default. Labels SHALL come from `pages.orders.status.<state>` (with `active` labelled via `pages.orders.filters.active`).
- A type filter — a native `<select>` with three options: "Все" (value `all`), "Самовывоз" (value `pickup`), "Доставка" (value `delivery`). Default `all`.
- A paginated table rendered via `OrdersTable` with columns: id (first 8 chars), `created_at`, type (translated), status (`StatusBadge`), total (kopecks → `ru-RU` currency-formatted), "Детали" button.
- Pagination controls (Previous / Next) that adjust the current `page`. `per_page` SHALL be fixed at 20.

Current `status`, `type`, `page` SHALL be reflected in the URL via `useSearchParams`. Changing a filter SHALL reset `page` to 1.

Polling: while the selected status tab is `active` AND `document.visibilityState === 'visible'`, the list SHALL refetch every 10 000 ms via a `setInterval` cleaned up on tab change, unmount, and `visibilitychange → hidden`. Switching to any non-`active` tab SHALL stop polling until the user returns to `active`.

An empty list (zero rows for the current filter) SHALL render a placeholder with copy `pages.orders.empty`.

#### Scenario: Default view hits active feed
- **WHEN** `OrdersPage` mounts with no URL params
- **THEN** exactly one request SHALL be issued with `status=active&page=1&per_page=20`

#### Scenario: Selecting a status tab updates URL and refetches
- **GIVEN** the page is mounted on the `active` tab
- **WHEN** the user clicks the `preparing` tab
- **THEN** the URL SHALL update to include `status=preparing` AND a new request SHALL be issued with `status=preparing&page=1&per_page=20`

#### Scenario: Changing filter resets pagination
- **GIVEN** the page is on `status=active&page=3`
- **WHEN** the user selects `type=delivery`
- **THEN** the URL SHALL update to `status=active&type=delivery&page=1` AND the request SHALL be issued with `page=1`

#### Scenario: Empty list renders the empty-state copy
- **GIVEN** the server returns `{orders: [], total_count: 0, page: 1, per_page: 20}`
- **WHEN** the page finishes loading
- **THEN** the rendered DOM SHALL contain the translation of `pages.orders.empty`

#### Scenario: Polling fires while on active tab
- **GIVEN** the page is mounted on the `active` tab and the tab is visible
- **WHEN** 10 000 ms of simulated time passes
- **THEN** a second list request SHALL have been issued with the same filter params

#### Scenario: Polling pauses on non-active tabs
- **GIVEN** the page is mounted on the `completed` tab
- **WHEN** 30 000 ms of simulated time passes
- **THEN** exactly one list request SHALL have been issued (no polling)

### Requirement: OrdersTable component

`OrdersTable` SHALL be a presentational component accepting `{ rows: OrderResponse[]; onSelect: (id: string) => void; emptyLabel: string }` and nothing else. Each rendered row SHALL carry `data-testid="order-row-<id>"` and the "Детали" button SHALL carry `data-testid="order-details-<id>"`. Clicking "Детали" SHALL invoke `onSelect` with the row's full `order.id` string. When `rows.length === 0` the component SHALL render `emptyLabel` instead of an empty table body.

#### Scenario: Rows render with test ids
- **GIVEN** `rows=[{id: 'uuid-A', ...}, {id: 'uuid-B', ...}]`
- **WHEN** the component is rendered
- **THEN** the DOM SHALL contain elements matching `[data-testid="order-row-uuid-A"]` AND `[data-testid="order-row-uuid-B"]`

#### Scenario: Clicking Details invokes onSelect with the id
- **GIVEN** `rows=[{id: 'uuid-A', ...}]` and a spy `onSelect`
- **WHEN** the user clicks `[data-testid="order-details-uuid-A"]`
- **THEN** `onSelect` SHALL have been invoked exactly once with `'uuid-A'`

#### Scenario: Empty rows render emptyLabel
- **GIVEN** `rows=[]` and `emptyLabel="Нет заказов"`
- **WHEN** the component is rendered
- **THEN** the DOM SHALL contain the text `"Нет заказов"` AND SHALL NOT contain any `[data-testid^="order-row-"]` element

### Requirement: OrderDetailDialog component — content

`OrderDetailDialog` SHALL accept `{ order: OrderResponse | null; open: boolean; onClose: () => void; onAction: () => void }` and render a shadcn/ui dialog with the following sections when `open && order`:
- Header: the short order id (first 8 chars), a `StatusBadge`, and created-at (locale-formatted).
- Items list: one line per `OrderItemResponse` with name (`menu_item_name_ru` if locale is RU, else `menu_item_name_en`), size label (if present), quantity, `unit_price` (kopecks → ₽), and `line_total` (kopecks → ₽).
- Money breakdown: a labelled row for each of `subtotal`, `discount_amount`, `delivery_fee`, `total`, all kopecks-formatted. `discount_amount` SHALL render as a negative value (e.g. `-100,00 ₽`) to signal a reduction; `0` discount renders `0,00 ₽` without a minus.
- Staff id line: the short `user_id` (first 8 chars) with a `pages.orders.detail.user_id` label.
- Action row: the role-gated transition buttons AND the admin cancel button (see the dedicated requirement below).

The modal SHALL NOT render `display_name`, `delivery_address`, or `points_used` — the `order_history.OrderResponse` payload does not expose them (a follow-up change tracks the payload extension).

`onAction` SHALL be invoked after any successful state change (accept / ready / handout / cancel) so the parent can refetch the list.

#### Scenario: Modal renders breakdown in kopecks → rubles
- **GIVEN** `order.subtotal=35000, order.discount_amount=5000, order.delivery_fee=0, order.total=30000`
- **WHEN** the modal is rendered
- **THEN** the DOM SHALL contain the strings `"350,00 ₽"` (subtotal), `"-50,00 ₽"` (discount), `"0,00 ₽"` (delivery), and `"300,00 ₽"` (total)

#### Scenario: Modal omits PII fields
- **WHEN** the modal renders any order
- **THEN** the DOM SHALL NOT contain a label matching `pages.orders.detail.display_name`, `pages.orders.detail.address`, or `pages.orders.detail.points_used` (these keys SHALL NOT exist in the i18n files at this cycle)

### Requirement: Role-gated staff action buttons

The `OrderDetailDialog` SHALL render action buttons according to the table below, using `useCurrentRole()` to read the current role. Buttons for which the current role is NOT in the listed set MUST NOT appear in the DOM.

| Order status | Order type | Roles that see "Принять"   | Roles that see "Готов"    | Roles that see "Выдан"   | Roles that see "Отменить"  |
|--------------|-----------|----------------------------|---------------------------|--------------------------|----------------------------|
| `paid`       | any       | `{admin, barista}`         | —                         | —                        | `{admin}`                  |
| `preparing`  | any       | —                          | `{admin, barista}`        | —                        | `{admin}`                  |
| `ready`      | `pickup`  | —                          | —                         | `{admin, barista}`       | `{admin}`                  |
| `ready`      | `delivery`| —                          | —                         | —                        | `{admin}`                  |
| `in_delivery`| any       | —                          | —                         | —                        | `{admin}`                  |
| `created`    | any       | —                          | —                         | —                        | `{admin}`                  |
| `completed`  | any       | —                          | —                         | —                        | —                          |
| `cancelled`  | any       | —                          | —                         | —                        | —                          |

Clicking "Принять" SHALL call `updateOrderStatus(orderId, 'preparing')`. Clicking "Готов" SHALL call `updateOrderStatus(orderId, 'ready')`. Clicking "Выдан" SHALL call `updateOrderStatus(orderId, 'completed')`. Clicking "Отменить" SHALL open the confirmation sub-dialog and, on confirm, call `cancelAdminOrder(orderId)`.

Buttons SHALL carry test ids: `data-testid="order-action-accept"`, `data-testid="order-action-ready"`, `data-testid="order-action-handout"`, `data-testid="order-action-cancel"`.

#### Scenario: Barista on PAID sees Accept, not Cancel
- **GIVEN** the current role is `barista` and `order.status === 'paid'`
- **WHEN** the modal renders
- **THEN** the DOM SHALL contain `[data-testid="order-action-accept"]` AND SHALL NOT contain `[data-testid="order-action-cancel"]`

#### Scenario: Admin on PAID sees Accept and Cancel
- **GIVEN** the current role is `admin` and `order.status === 'paid'`
- **WHEN** the modal renders
- **THEN** the DOM SHALL contain both `[data-testid="order-action-accept"]` AND `[data-testid="order-action-cancel"]`

#### Scenario: Barista on PREPARING sees Ready, not Cancel
- **GIVEN** the current role is `barista` and `order.status === 'preparing'`
- **WHEN** the modal renders
- **THEN** the DOM SHALL contain `[data-testid="order-action-ready"]` AND SHALL NOT contain `[data-testid="order-action-cancel"]`

#### Scenario: Barista on READY pickup sees Handout
- **GIVEN** the current role is `barista`, `order.status === 'ready'`, `order.type === 'pickup'`
- **WHEN** the modal renders
- **THEN** the DOM SHALL contain `[data-testid="order-action-handout"]`

#### Scenario: Barista on READY delivery does NOT see Handout
- **GIVEN** the current role is `barista`, `order.status === 'ready'`, `order.type === 'delivery'`
- **WHEN** the modal renders
- **THEN** the DOM SHALL NOT contain `[data-testid="order-action-handout"]`

#### Scenario: Barista on COMPLETED sees no action buttons
- **GIVEN** the current role is `barista` and `order.status === 'completed'`
- **WHEN** the modal renders
- **THEN** the DOM SHALL NOT contain any element matching `[data-testid^="order-action-"]`

#### Scenario: Admin on CANCELLED sees no action buttons
- **GIVEN** the current role is `admin` and `order.status === 'cancelled'`
- **WHEN** the modal renders
- **THEN** the DOM SHALL NOT contain any element matching `[data-testid^="order-action-"]`

### Requirement: Cancel confirmation sub-dialog

Clicking "Отменить" SHALL open a nested shadcn/ui dialog with the copy `pages.orders.cancel_confirm.title` and `pages.orders.cancel_confirm.body`, a destructive-variant confirm button labelled `pages.orders.cancel_confirm.confirm` (test id `order-cancel-confirm`), and a cancel button labelled `pages.orders.cancel_confirm.cancel` (test id `order-cancel-abort`).

- Clicking the abort button or dismissing the sub-dialog SHALL close it WITHOUT issuing any request.
- Clicking the confirm button SHALL call `cancelAdminOrder(order.id)`.
- While the request is in flight, both buttons SHALL be disabled.
- On success the sub-dialog SHALL close, `onAction` SHALL be invoked, and the outer modal SHALL refetch the order to show `CANCELLED` status.
- On `ApiError.status === 409` (illegal transition) the component SHALL notify the user via `pages.orders.errors.illegal_transition` and refetch the order.

#### Scenario: Cancel flow — happy path
- **GIVEN** the current role is `admin`, `order.status === 'paid'`, and the modal is rendered
- **WHEN** the user clicks `[data-testid="order-action-cancel"]`, then `[data-testid="order-cancel-confirm"]`
- **THEN** exactly one `POST /api/v1/orders/<id>/cancel` request SHALL have been issued with body `{"reason": null}`

#### Scenario: Cancel flow — abort does not call the API
- **GIVEN** the current role is `admin` and the modal is rendered
- **WHEN** the user clicks `[data-testid="order-action-cancel"]`, then `[data-testid="order-cancel-abort"]`
- **THEN** no cancel request SHALL have been issued AND the sub-dialog SHALL be closed

### Requirement: StatusBadge component

`StatusBadge` SHALL be a pure function component accepting `{ status: OrderStatus }` and returning a shadcn/ui `<Badge>` with a color class mapped deterministically from the status value. It SHALL carry `data-testid="status-badge-<status>"` and render the translation of `pages.orders.status.<status>`.

| `OrderStatus`   | Tailwind class set                          |
|-----------------|---------------------------------------------|
| `created`       | `bg-gray-200 text-gray-800`                 |
| `paid`          | `bg-blue-100 text-blue-800`                 |
| `preparing`     | `bg-orange-100 text-orange-800`             |
| `ready`         | `bg-green-100 text-green-800`               |
| `in_delivery`   | `bg-purple-100 text-purple-800`             |
| `completed`     | `bg-neutral-100 text-neutral-700`           |
| `cancelled`     | `bg-red-100 text-red-800`                   |

#### Scenario: StatusBadge renders test id and translation
- **GIVEN** `<StatusBadge status="preparing" />`
- **WHEN** the component is rendered
- **THEN** the DOM SHALL contain `[data-testid="status-badge-preparing"]` AND the translation of `pages.orders.status.preparing`

### Requirement: i18n keys

Both `web/admin/src/i18n/locales/ru/common.json` and `.../en/common.json` SHALL contain the following keys under `pages.orders`:

- `title`, `description`
- `filters.active`, `filters.type`, `filters.type_all`, `filters.type_pickup`, `filters.type_delivery`
- `columns.id`, `columns.created_at`, `columns.type`, `columns.status`, `columns.total`, `columns.actions`
- `status.created`, `status.paid`, `status.preparing`, `status.ready`, `status.in_delivery`, `status.completed`, `status.cancelled`
- `type.pickup`, `type.delivery`
- `actions.accept`, `actions.ready`, `actions.handout`, `actions.cancel`, `actions.details`
- `cancel_confirm.title`, `cancel_confirm.body`, `cancel_confirm.confirm`, `cancel_confirm.cancel`
- `detail.title`, `detail.user_id`, `detail.items`, `detail.subtotal`, `detail.discount`, `detail.delivery_fee`, `detail.total`, `detail.unit_price`, `detail.quantity`
- `empty`
- `pagination.previous`, `pagination.next`, `pagination.page` (with placeholder `{{page}}`)
- `errors.illegal_transition`, `errors.forbidden`, `errors.not_found`

The RU and EN files SHALL contain the same key set — a missing key on either side is a defect.

#### Scenario: RU and EN key sets match
- **WHEN** a test diffs the flattened keysets of `ru/common.json` and `en/common.json` restricted to the `pages.orders.*` prefix
- **THEN** the symmetric difference SHALL be empty

#### Scenario: All documented keys resolve
- **WHEN** a test calls `i18next.t(key)` for every key listed above, under both `ru` and `en` locales
- **THEN** every call SHALL return a non-empty string that is NOT equal to the key itself (i.e. no missing-translation fallback)

### Requirement: Error handling in the orders UI

All API interactions originating from `OrdersPage` and `OrderDetailDialog` SHALL route errors via a single helper that classifies `ApiError.status` and notifies the user. The helper SHALL:
- On `401` — emit `common.sessionExpired` (the underlying `authenticatedFetch` already navigates to login; this is a brief flash).
- On `403` — emit `pages.orders.errors.forbidden`.
- On `404` — close any open modal, emit `pages.orders.errors.not_found`, refetch the list.
- On `409` — emit `pages.orders.errors.illegal_transition` and refetch the currently-open order.
- On any other non-2xx — emit `common.error`.

#### Scenario: 409 on status PATCH refetches the order
- **GIVEN** the modal is open for order `X`
- **WHEN** a PATCH returns 409
- **THEN** the helper SHALL emit `pages.orders.errors.illegal_transition` AND a subsequent `GET /api/v1/admin/orders/X` SHALL be issued to refresh the rendered status

#### Scenario: 404 closes the modal
- **GIVEN** the modal is open for order `X`
- **WHEN** any request for `X` returns 404
- **THEN** the modal SHALL close AND the list SHALL refetch

