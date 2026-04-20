## Why

Phase 5 shipped the staff-facing `/api/v1/admin/orders*` backend (see `admin-orders-api` spec) but the corresponding admin UI was never built — `web/admin/src/pages/OrdersPage.tsx` is still a 12-line placeholder while the sidebar entry is already live for roles `{ADMIN, BARISTA}`. Baristas and admins have no way to see the staff order feed, accept/ready/handout orders, or cancel them through the admin SPA. PDD Phase 6 (§7.1) lists this orphaned UI as a must-fix before launch.

## What Changes

- Add a typed API client `web/admin/src/api/admin-orders.ts` wrapping `GET /api/v1/admin/orders`, `GET /api/v1/admin/orders/{id}`, `PATCH /api/v1/orders/{id}/status`, and `POST /api/v1/orders/{id}/cancel`, reusing the `authenticatedFetch` + `AuthError` pattern from `menu.ts` / `promocodes.ts`.
- Replace the single-file `pages/OrdersPage.tsx` stub with a `pages/Orders/` directory containing `OrdersPage.tsx` (list + filters + pagination), `OrdersTable.tsx`, `OrderDetailDialog.tsx`, `StatusBadge.tsx`, and an `index.tsx` barrel.
- Status tab filter (Активные / Оплачен / Готовится / Готов / В пути / Завершён / Отменён) and type dropdown (Все / Самовывоз / Доставка); pagination via query-params (`page`, `per_page`). The "Все" status tab is deliberately omitted this cycle — see `design.md` → Open Questions (the server accepts only `"active"` or a concrete `OrderStatus`).
- Table columns: short order id, `created_at`, type, status badge, total (kopecks → ₽), "Детали" button.
- Order detail modal: items list, short `user_id`, money breakdown (subtotal / discount / delivery_fee / total), and role-gated staff action buttons. Customer `display_name`, `delivery_address`, and `points_used` are deliberately **out of scope** for this cycle — `order_history.OrderResponse` does not expose them and expanding the staff payload is tracked as a follow-up change.
- Staff actions per PDD §6.1 (role-aware via `useCurrentRole`):
  - `{BARISTA, ADMIN}` on `PAID` → "Принять" (`PREPARING`).
  - `{BARISTA, ADMIN}` on `PREPARING` → "Готов" (`READY`).
  - `{BARISTA, ADMIN}` on `READY` **and** `type=pickup` → "Выдан" (`COMPLETED`).
  - `{ADMIN}` on any status `∉ {COMPLETED, CANCELLED}` → "Отменить" (POST `/cancel`, confirmation modal).
- Lightweight polling on the "Active" status tab (10s refetch, paused when user switches to finalized tabs) — no WebSocket/SSE per PDD §4.5.
- i18n keys `pages.orders.*` in `ru/common.json` and `en/common.json` (filters, columns, status labels, action labels, cancel confirm copy, detail labels).
- Update `App.tsx` import to consume the new `pages/Orders/` barrel; `allowedRoles` for the `/orders` route is unchanged (already `{ADMIN, BARISTA}` after Phase 5.5).
- Tests (vitest + RTL): `OrdersTable.test.tsx`, `OrderDetailDialog.test.tsx`, `api/admin-orders.test.ts` covering role-gated button visibility, cancel confirmation flow, URL/query-param formation, and `403 → AuthError` passthrough.

## Capabilities

### New Capabilities
- `admin-orders-ui`: React admin SPA surface for the staff order feed — list with status/type filters and pagination, order detail modal with money breakdown, role-gated staff state-transition buttons (accept / ready / handout / cancel), and smart polling on the active tab.

### Modified Capabilities
_None — backend contracts (`admin-orders-api`, `order-actions-api`, `order-cancel`, `order-lifecycle`) are already in place and this change only consumes them from the admin SPA._

## Non-Goals

- **No WebSocket / SSE / server-push.** PDD §4.5 explicitly permits polling ≤5s for the staff feed; we use a single 10s interval on the active tab only.
- **No courier transitions (`READY → IN_DELIVERY`, `IN_DELIVERY → COMPLETED` for delivery orders).** Those live in `CourierShell` / `courier-panel-ui` and are out of scope.
- **No customer-side order history / tracking changes.** This is strictly the `/admin/*` SPA.
- **No backend changes.** `admin-orders-api`, `order-actions-api`, and `order-cancel` specs are frozen inputs. In particular, the staff detail payload (`order_history.OrderResponse`) is not extended in this change — customer `display_name`, `delivery_address` snapshot, and `points_used` therefore do NOT appear in the detail modal this cycle.
- **No new shared design-system primitives.** We reuse existing shadcn/ui components (Dialog, Table, Badge, Button, Select, Tabs) and only add thin page-local wrappers.
- **No real-time stop-list / menu / user edits from the orders screen.** Staff actions are limited to the four transitions listed above plus cancel.

**Follow-up (not in this change):** a separate change `admin-orders-detail-payload` SHOULD extend the staff detail endpoint with `points_used`, a PII-bounded `display_name`, and the delivery-address snapshot (INV-010 / INV-013 analysis included). The UI slots in this change are written to accept new optional fields without markup rework.

## Impact

- **Affected code**:
  - New: `web/admin/src/api/admin-orders.ts` (+ `.test.ts`), `web/admin/src/pages/Orders/{index,OrdersPage,OrdersTable,OrderDetailDialog,StatusBadge}.tsx` (+ `OrdersTable.test.tsx`, `OrderDetailDialog.test.tsx`).
  - Modified: `web/admin/src/App.tsx` (route import), `web/admin/src/i18n/locales/{ru,en}/common.json` (new keys).
  - Removed: single-file `web/admin/src/pages/OrdersPage.tsx`.
- **APIs consumed (no changes to contracts)**:
  - `GET /api/v1/admin/orders?status=&type=&page=&per_page=`
  - `GET /api/v1/admin/orders/{order_id}`
  - `PATCH /api/v1/orders/{order_id}/status` body `{ "status": "<OrderStatus>" }`
  - `POST /api/v1/orders/{order_id}/cancel`
- **Specs touched**: new `admin-orders-ui` capability under `openspec/specs/admin-orders-ui/spec.md`.
- **PDD references**: §4.5 (staff feed), §6.1 (order lifecycle transitions), §7.1 Phase 6 (admin panel orphan fix), INV-010 (role isolation — sidebar + route already gated; this UI only talks to staff endpoints).
- **MVP phase**: Phase 6 (Admin Panel, orphan fix).
- **Runtime cost**: 1 refetch / 10s per active admin/barista on the Active tab. Polling pauses on every other tab and on unmount; no background refetch.
