## Context

**Affected modules**: `[web-admin]`.

Phase 5 delivered the staff-facing order backend (`admin-orders-api`, `order-actions-api`, `order-cancel`, `order-lifecycle`) while Phase 5.5 wired the sidebar to show the "Заказы" entry for roles `{ADMIN, BARISTA}`. The `/admin/orders` route currently mounts a 12-line placeholder that only renders a title and a translated description — there is no way for baristas to see the active feed, walk the state machine, or for admins to cancel an order from the admin SPA. PDD §7.1 Phase 6 lists this orphan fix as a must-have before launch.

Existing primitives this design reuses (no new shared code):
- `authenticatedFetch` + `ApiError` from `@/api/client` — Bearer-token propagation, 401 auto-redirect, structured error.
- `useCurrentRole` from `@/lib/auth` — reads `localStorage.staffRole` (source of truth is server; storage value is a UX hint).
- shadcn/ui primitives under `@/components/ui/*` — `dialog`, `badge`, `button`, `table`, `input`. `select` / `tabs` primitives do not ship with this repo yet; the design uses explicit `<button role="tab">` tab bars (same pattern `PromosPage` uses) and a native `<select>` for the type filter.
- `useNotifier` / `NotificationList` from `@/components/ui/notifier` — toast-like notifications for API errors (same pattern as `PromosPage`).
- i18n via `react-i18next` with keys under `pages.orders.*`.

Backend contract (frozen input to this change, from `admin-orders-api` spec):
- `GET /api/v1/admin/orders?status=<active|OrderStatus>&type=<OrderType>&page=<int>&per_page=<int>` → `OrderListResponse` with `orders`, `total_count`, `page`, `per_page`. RBAC `{ADMIN, BARISTA}`.
- `GET /api/v1/admin/orders/{order_id}` → `OrderResponse`. RBAC `{ADMIN, BARISTA}`. 404 on unknown.
- `PATCH /api/v1/orders/{order_id}/status` body `{"new_status": "<OrderStatus>"}` — staff transitions (per `order-actions-api`). RBAC `{ADMIN, BARISTA, COURIER}` (each role gets its own transition subset — server enforces INV-016).
- `POST /api/v1/orders/{order_id}/cancel` body `{"reason": "<string|null>"}` — admin cancel (per `order-cancel`).

**Important schema note:** `core_api.schemas.order_history.OrderResponse` exposes `{id, user_id, status, type, subtotal, discount_amount, delivery_fee, total, created_at, items[]}`. It deliberately does NOT expose `points_used`, customer `display_name`, or the `delivery_address` JSONB snapshot. Expanding this payload is tracked as a separate follow-up change (`admin-orders-detail-payload`); this UI renders only what the staff endpoint currently returns.

## Goals / Non-Goals

**Goals:**
- Replace the `/admin/orders` stub with a working list view that MUST support status-tab filtering (`active` + every `OrderStatus` + `all`), type filtering (all / pickup / delivery), pagination (`page`, `per_page`), and polling on the active-tab view only.
- Provide a detail modal that MUST render every field the backend exposes, plus the role-gated staff action buttons per PDD §6.1.
- Keep the client thin — no state-machine logic, no duplicated enum tables, no business validation. UI decides which button to *show*; the server decides whether the transition is legal (INV-016).
- Tests MUST cover URL/query-param formation, role-gated button visibility, empty states, and the cancel confirmation flow. No snapshot tests (brittle).

**Non-Goals:**
- No WebSocket / SSE. Polling only.
- No backend changes. The payload extension is a follow-up.
- No courier-side transitions (`READY → IN_DELIVERY`, delivery `READY → COMPLETED`). Those belong to `CourierShell`.
- No repeat-order / refund surfaces on this page.
- No CSV / export. No bulk operations.

## Decisions

### Decision 1 — Directory layout: replace file with folder

The current `web/admin/src/pages/OrdersPage.tsx` SHALL be deleted and replaced by a folder `web/admin/src/pages/Orders/` with:

```
Orders/
  index.tsx              # re-exports OrdersPage; mirrors pages/Promos/index.tsx
  OrdersPage.tsx         # container: filters, pagination, polling, fetch orchestration
  OrdersTable.tsx        # presentational: rows + "Детали" button
  OrdersTable.test.tsx
  OrderDetailDialog.tsx  # modal: breakdown + role-gated action buttons + cancel confirm
  OrderDetailDialog.test.tsx
  StatusBadge.tsx        # thin <Badge> wrapper colored by OrderStatus
```

**Alternatives considered:**
- *Single-file OrdersPage.tsx.* Rejected: four distinct concerns (list, row, modal, badge) would balloon one file to 500+ lines and make the role-gating tests hard to isolate.
- *Colocate the dialog under `@/components/`.* Rejected: the modal is page-local (reads `pages.orders.detail.*` i18n, knows staff-actions); extracting it would force a premature generic abstraction.

**Rationale:** The folder layout mirrors `pages/Promos/` and `pages/Menu/` exactly, so reviewers and future contributors pay no extra cognitive cost.

### Decision 2 — API client stays thin; no state-machine

`web/admin/src/api/admin-orders.ts` SHALL expose four functions and MUST NOT contain any state-machine logic, transition guards, or role checks. Errors from the server MUST bubble as `ApiError` (status + body); the client MUST NOT remap 403 into a domain-specific error.

```ts
export type AdminOrderStatusFilter = OrderStatus | 'active' | 'all';

export interface ListAdminOrdersParams {
  status?: AdminOrderStatusFilter;
  type?: OrderType;
  page?: number;
  per_page?: number;
}

export function listAdminOrders(params?: ListAdminOrdersParams): Promise<OrderListResponse>;
export function getAdminOrder(orderId: string): Promise<OrderResponse>;
export function updateOrderStatus(orderId: string, newStatus: OrderStatus): Promise<OrderResponse>;
export function cancelAdminOrder(orderId: string, reason?: string | null): Promise<OrderResponse>;
```

**URL-building contract (stable, testable):**
- `status === 'all'` MUST omit the `status` query-param (server default is `active`, so `all` is an explicit "drop the filter" request — the client enforces this translation).
- `status === undefined` MUST omit the query-param entirely.
- `type === undefined` MUST omit the query-param.
- `page` / `per_page` MUST be stringified only when set.

**Wire contract (mirrors backend exactly):**
- `updateOrderStatus` → `PATCH /api/v1/orders/{id}/status` with `{"new_status": "<value>"}`. The field name is `new_status`, not `status` — this mirrors `core_api.schemas.order.OrderStatusUpdate`. This decision overrides the task-description shorthand (`{status: '...'}`), which would fail Pydantic validation.
- `cancelAdminOrder` → `POST /api/v1/orders/{id}/cancel` with `{"reason": reason ?? null}`. No reason is optional per `order-cancel` spec.

**Alternatives considered:**
- *Treat `all` as a sentinel the server understands.* Rejected: the server only accepts `"active"` or a concrete `OrderStatus`; `"all"` as a server value would need a backend change.
- *Use `fetch` directly.* Rejected: `authenticatedFetch` already handles token injection, 401 auto-redirect, and structured errors consistently with the rest of the admin SPA.

### Decision 3 — Role-gated buttons live in the modal, not the table

Per PDD §6.1 the staff-transition matrix SHALL be:

| Current status | Role          | Button label (i18n)                           | Target transition                             |
|----------------|---------------|-----------------------------------------------|-----------------------------------------------|
| `PAID`         | BARISTA/ADMIN | `pages.orders.actions.accept` — "Принять"     | `PATCH /status {new_status: "preparing"}`    |
| `PREPARING`    | BARISTA/ADMIN | `pages.orders.actions.ready` — "Готов"        | `PATCH /status {new_status: "ready"}`        |
| `READY`+PICKUP | BARISTA/ADMIN | `pages.orders.actions.handout` — "Выдан"      | `PATCH /status {new_status: "completed"}`    |
| any status ∉ {COMPLETED, CANCELLED} | ADMIN | `pages.orders.actions.cancel` — "Отменить" | `POST /cancel {reason: null}`        |

Buttons SHALL only be rendered in `OrderDetailDialog`. The table row MUST contain only a "Детали" button. **Rationale:** rendering four-way action buttons inline would produce a row that jumps columns as status changes, and multiplies state handling across all visible rows. A modal-scoped action also forces an explicit "read the items first" UX beat before the irreversible transition.

**Alternatives considered:**
- *Inline actions per row.* Rejected for the reasons above.
- *Context menu.* Rejected: shadcn/ui context-menu primitive is not in the repo and adding it is premature.

Role gating uses `useCurrentRole()`:
- Button visibility MUST be computed from `role` and the rendered `order.status` + `order.type`.
- Visibility MUST NOT gate security — the server is the authority (INV-010 / INV-016). The UI gate is a UX affordance; a barista hitting `/cancel` directly would still get 403.

### Decision 4 — Cancel button goes through a confirmation dialog

"Отменить" on the detail modal SHALL open a nested confirmation dialog (`<Dialog>` within `<Dialog>` is supported by the shadcn/ui primitive) with two buttons — "Да, отменить" (destructive variant) and "Нет". The API call SHALL fire only on explicit confirm. After success the detail dialog SHALL refetch the order to render the new `CANCELLED` status, and the underlying list SHALL refetch.

**Rationale:** cancellation is irreversible by admin (refunds are auto-triggered server-side per `order-cancel`). A click-away-safe confirmation is the minimum viable safeguard.

**Alternatives considered:**
- *Inline confirm (two clicks on the same button).* Rejected: error-prone and not screen-reader-friendly.
- *Require a reason textarea.* The `order-cancel` schema accepts an optional reason; adding the input now widens scope. Left for a follow-up if operations asks for it.

### Decision 5 — Polling: `setInterval` on the active tab only

When the Status filter is `active`, `OrdersPage` SHALL refetch the list every 10 seconds using `setInterval` inside a `useEffect`. The interval MUST be cleared on:
- Status-tab change (any non-`active` tab pauses polling).
- Component unmount.
- `document.visibilityState === 'hidden'` (pause when tab is backgrounded; resume on `visibilitychange` → `visible`).

**Rationale:** PDD §4.5 permits polling ≤5s; 10s is conservative and still feels live. Only the active feed needs it — finalized feeds (`COMPLETED`, `CANCELLED`) don't change. React Query is not in the repo; rolling our own `useEffect` + `setInterval` avoids a new dependency and mirrors the simplicity of `PromosPage`'s reload pattern.

**Alternatives considered:**
- *react-query's `refetchInterval`.* Rejected: adds a runtime dependency and a provider, too large for a single page.
- *Poll on every tab.* Rejected: wastes requests on inherently-static finalized lists.
- *Shorter interval (≤5s).* Rejected: 10s is well inside the PDD ceiling and halves the server load.

### Decision 6 — Status / type enum surface

The UI SHALL import enum string literals from the API client (`OrderStatus`, `OrderType`) as union types. It MUST NOT redefine the enums. Status labels and type labels SHALL be translated via `pages.orders.status.<state>` and `pages.orders.type.<value>` keys — the component MUST NOT hard-code Russian or English copy.

`StatusBadge.tsx` SHALL be a pure function `({status}: {status: OrderStatus}) => JSX` returning a shadcn/ui `<Badge>` with a `variant`/`className` mapped from status:

| `OrderStatus` | Badge color class                              |
|---------------|------------------------------------------------|
| `CREATED`     | `bg-gray-200 text-gray-800`                    |
| `PAID`        | `bg-blue-100 text-blue-800`                    |
| `PREPARING`   | `bg-orange-100 text-orange-800`                |
| `READY`       | `bg-green-100 text-green-800`                  |
| `IN_DELIVERY` | `bg-purple-100 text-purple-800`                |
| `COMPLETED`   | `bg-neutral-100 text-neutral-700`              |
| `CANCELLED`   | `bg-red-100 text-red-800`                      |

A grep confirms no existing `StatusBadge` component in `web/admin/src/` — so a local one is added under `pages/Orders/StatusBadge.tsx`.

### Decision 7 — Pagination via URL query-params (not URL path)

`OrdersPage` SHALL reflect current `status`, `type`, `page`, `per_page` in the browser URL via `useSearchParams`. Deep-link from a bookmark / shared URL SHALL restore the same view. `per_page` defaults to 20 and is not user-configurable in this change (hard-coded).

**Rationale:** mirrors `pages/Promos/PromosPage` ergonomics and lets an admin paste a "Помоги посмотреть заказ в `READY`" link into chat.

### Decision 8 — Error handling

All API calls MUST route through a try/catch that:
- On `ApiError.status === 401` → `authenticatedFetch` already navigates to login. Component SHALL additionally call `notify` with `common.sessionExpired` for the brief flash before navigation.
- On `ApiError.status === 403` → `notify('pages.orders.errors.forbidden', 'error')`. Do NOT redirect; the user is authenticated but the action is not allowed (e.g. admin route + barista token).
- On `ApiError.status === 409` (illegal transition per INV-016) → `notify('pages.orders.errors.illegal_transition', 'error')` and refetch the order (the visible status is stale).
- On `ApiError.status === 404` (order gone / wrong id) → close the modal, `notify('pages.orders.errors.not_found', 'error')`, refetch the list.
- Other → `notify('common.error', 'error')`.

The cancel-confirm dialog MUST disable both confirm/close buttons while the request is in flight.

### Decision 9 — Money formatting

All integer-kopeck values from the backend (`subtotal`, `discount_amount`, `delivery_fee`, `total`, `unit_price`, `line_total`) MUST be rendered via a shared helper `formatKopecks(n: number): string` that outputs e.g. `"350,00 ₽"` (`Intl.NumberFormat('ru-RU', {style: 'currency', currency: 'RUB'})`). The helper lives inside `pages/Orders/` as module-private — no new export into `@/lib`. When the customer SPA or another admin page needs it, extraction can happen in a follow-up.

**Rationale:** INV (prices in kopecks) + single page scope → no premature shared util.

## Risks / Trade-offs

- **[Polling → stale cache under rapid status churn]** → Mitigation: every transition action (accept/ready/handout/cancel) eagerly refetches the list on success in addition to the 10s timer. Worst-case user-visible staleness is 10s for orders changed by *another* staffer.

- **[Role-gating drift — UI shows a button the backend rejects with 403]** → Mitigation: Decision 8 maps 403 to a visible error and refetches the order so the status/role mismatch is obvious. The UI gate is correctness-advisory; server is authoritative (INV-010, INV-016). Tests assert visibility rules but do not assert 403 cannot happen.

- **[Detail modal shows less than the task's original description]** → Mitigation: Non-Goals + Open Question below flag the payload extension as a follow-up so the gap is tracked. UI components accept optional future fields without markup surgery (e.g. the breakdown list is `.map()` over an array of `{label, value}`).

- **[Polling while tab is in background wastes requests]** → Mitigation: `visibilitychange` listener in Decision 5 pauses the interval when the tab is hidden.

- **["Все" tab cannot be expressed server-side]** → The server accepts only `"active"` or a concrete `OrderStatus`; there is no `status=all`. Merging three parallel requests (`active` + `COMPLETED` + `CANCELLED`) client-side breaks pagination semantics (`total_count` is per-request, not merged) and produces ambiguous page offsets. Mitigation: **drop the "Все" tab for this cycle**. The seven concrete tabs (Активные / Оплачен / Готовится / Готов / В пути / Завершён / Отменён) cover the full lifecycle. If operations asks for a combined view, a follow-up change SHALL extend the backend to accept `status=all` and the UI SHALL add the eighth tab without restructuring. See Open Questions.

- **[Confirmation dialog nested inside another dialog — focus trap / aria]** → Mitigation: the shadcn/ui `Dialog` primitive handles focus trapping; tests assert focus is returned to "Отменить" after close. Manual QA step on keyboard navigation listed in tasks.md.

## Migration Plan

No data migration. No schema change. No feature flag — this change only replaces a stub page. Rollback = revert the commit; the stub page returns.

Deploy steps:
1. Merge the PR into `admin_ui_phase` → `main`.
2. CI (frontend) runs `pnpm -w test` + `pnpm -w build`. No backend CI impact.
3. Nginx serves the new `web/admin` bundle. No cache invalidation needed beyond the standard cache-busting via `vite build` hashed asset names.

## Open Questions

1. **"Все" tab semantics.** Dropped from this cycle (see Risks). The seven concrete status tabs suffice; a follow-up change MAY add `status=all` server-side plus the eighth tab.

2. **Cancel reason.** `order-cancel` accepts an optional reason. Should the confirm dialog include a small reason textarea, or is that left for the follow-up? **Provisional answer:** no textarea this cycle. `reason` is sent as `null`.

3. **Detail payload follow-up.** When `admin-orders-detail-payload` ships, `display_name` / `delivery_address` / `points_used` SHALL slot into the existing modal without restructuring — the breakdown list is array-driven and the customer section is a single placeholder div. No action required now.
