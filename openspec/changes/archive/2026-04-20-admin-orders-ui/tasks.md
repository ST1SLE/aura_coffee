## 1. Scaffolding

- [x] 1.1 [web-admin] PREREQ: create the directory `web/admin/src/pages/Orders/` (empty; subsequent tasks add files one-by-one).
- [x] 1.2 [web-admin] PREREQ: add `pages.orders.*` keys skeleton to `web/admin/src/i18n/locales/ru/common.json` (RU copy only in this task, EN mirrors in 1.3).
- [x] 1.3 [web-admin] PREREQ: add `pages.orders.*` keys skeleton to `web/admin/src/i18n/locales/en/common.json` (same key tree as 1.2; EN copy).

## 2. API client

- [x] 2.1 [web-admin] RED: create `web/admin/src/api/admin-orders.test.ts` asserting `listAdminOrders({status: 'preparing', type: 'delivery', page: 2, per_page: 20})` triggers one `fetch` call with URL containing `/api/v1/admin/orders?status=preparing&type=delivery&page=2&per_page=20` (mirror `menu.test.ts` mocking pattern). Test MUST fail (module does not exist yet → ImportError).
- [x] 2.2 [web-admin] RED: add test to `admin-orders.test.ts` asserting `listAdminOrders({status: 'active'})` issues a URL that contains `status=active` but NOT `type=`, `page=`, or `per_page=`.
- [x] 2.3 [web-admin] RED: add test to `admin-orders.test.ts` asserting `listAdminOrders()` (no args) hits `/api/v1/admin/orders` with no query string.
- [x] 2.4 [web-admin] RED: add test to `admin-orders.test.ts` asserting that `listAdminOrders()` rejects with an `ApiError` whose `status === 403` when the server responds with 403.
- [x] 2.5 [web-admin] RED: add test to `admin-orders.test.ts` asserting `getAdminOrder('00000000-0000-0000-0000-000000000001')` issues `GET` to a URL ending with `/api/v1/admin/orders/00000000-0000-0000-0000-000000000001`.
- [x] 2.6 [web-admin] RED: add test to `admin-orders.test.ts` asserting `updateOrderStatus('abc', 'preparing')` issues `PATCH` to `/api/v1/orders/abc/status` with JSON body exactly `{"new_status": "preparing"}`.
- [x] 2.7 [web-admin] RED: add test to `admin-orders.test.ts` asserting `cancelAdminOrder('abc')` issues `POST` to `/api/v1/orders/abc/cancel` with JSON body exactly `{"reason": null}`.
- [x] 2.8 [web-admin] RED: add test to `admin-orders.test.ts` asserting `cancelAdminOrder('abc', 'customer asked')` sends body `{"reason": "customer asked"}`.
- [x] 2.9 [web-admin] GREEN: create `web/admin/src/api/admin-orders.ts` with `listAdminOrders`, `getAdminOrder`, `updateOrderStatus`, `cancelAdminOrder` built on `authenticatedFetch` + `ApiError`; exports the `OrderStatus`, `OrderType`, `AdminOrderStatusFilter`, `OrderItemResponse`, `OrderResponse`, `OrderListResponse` TypeScript types. Query-string builder treats `undefined` and `'all'` as "omit" → passes 2.1–2.8.
- [x] 2.10 [web-admin] REFACTOR: extract the query-string builder to a module-private `buildListQuery` helper (mirrors `promocodes.ts`); re-run all tests under `admin-orders.test.ts` to confirm green.

## 3. StatusBadge component

- [x] 3.1 [web-admin] IMPL: create `web/admin/src/pages/Orders/StatusBadge.tsx` — pure function component `({status}) => JSX` using `@/components/ui/badge` with the status → Tailwind color map from `design.md` Decision 6, a `data-testid="status-badge-<status>"`, and the `pages.orders.status.<status>` translation as the label.
- [x] 3.2 [web-admin] TEST: skip — this is a pure presentational component with no logic; coverage comes indirectly through `OrdersTable.test.tsx` and `OrderDetailDialog.test.tsx` where it is rendered with concrete statuses.

## 4. OrdersTable component

- [x] 4.1 [web-admin] IMPL: create `web/admin/src/pages/Orders/OrdersTable.tsx` — accepts `{ rows, onSelect, emptyLabel }`; renders a `@/components/ui/table` with columns id-short / created-at / type / `StatusBadge` / total / details-button; each row has `data-testid="order-row-<id>"`; details button has `data-testid="order-details-<id>"` and `onClick={() => onSelect(row.id)}`. When `rows.length === 0` render `<p>{emptyLabel}</p>` instead of `<tbody>`.
- [x] 4.2 [web-admin] TEST: create `web/admin/src/pages/Orders/OrdersTable.test.tsx` with three `describe`/`it` blocks asserting (a) rows render with test ids, (b) clicking Details calls `onSelect` with the id, (c) empty rows render `emptyLabel` and no `order-row-` elements. Use `@testing-library/react` `render` + `screen.getByTestId` / `queryByTestId` (mirror `PromosTable.test.tsx` layout).
- [x] 4.3 [web-admin] REFACTOR: verify `OrdersTable` stays presentational (no `useState`, no network); if any state leaked in during 4.1, push it into the container.

## 5. OrderDetailDialog — breakdown rendering

- [x] 5.1 [web-admin] IMPL: create `web/admin/src/pages/Orders/OrderDetailDialog.tsx` skeleton — props `{order, open, onClose, onAction}`; uses `@/components/ui/dialog`; renders header (short id + `StatusBadge` + created-at), items list, breakdown rows (subtotal / discount / delivery / total), and short `user_id`. Implement `formatKopecks(n)` as a module-private helper using `Intl.NumberFormat('ru-RU', {style: 'currency', currency: 'RUB'})`; render `discount_amount` prefixed with `-` when `> 0`.
- [x] 5.2 [web-admin] TEST: create `web/admin/src/pages/Orders/OrderDetailDialog.test.tsx`; add one test asserting breakdown rendering — pass `order` with `subtotal=35000, discount_amount=5000, delivery_fee=0, total=30000` and assert DOM contains `350,00 ₽`, `-50,00 ₽`, `0,00 ₽`, `300,00 ₽`.
- [x] 5.3 [web-admin] TEST: add to `OrderDetailDialog.test.tsx` a test asserting the modal does NOT render any element whose text matches `pages.orders.detail.display_name` / `.address` / `.points_used` (these keys are intentionally absent this cycle).

## 6. OrderDetailDialog — role-gated staff actions

- [x] 6.1 [web-admin] IMPL: add role-gated action buttons to `OrderDetailDialog.tsx` using `useCurrentRole()` from `@/lib/auth`. Wire the visibility matrix from `spec.md` → "Role-gated staff action buttons". Each button carries `data-testid` per spec. Clicks call the corresponding API (`updateOrderStatus` for accept/ready/handout; cancel goes to the confirmation sub-dialog in section 7).
- [x] 6.2 [web-admin] TEST: add to `OrderDetailDialog.test.tsx` — test `barista on PAID` sees `order-action-accept` but not `order-action-cancel`. Mock `useCurrentRole` via `vi.mock('@/lib/auth', ...)`; mock `fetch`.
- [x] 6.3 [web-admin] TEST: add to `OrderDetailDialog.test.tsx` — test `admin on PAID` sees both `order-action-accept` and `order-action-cancel`.
- [x] 6.4 [web-admin] TEST: add to `OrderDetailDialog.test.tsx` — test `barista on PREPARING` sees `order-action-ready` but not `order-action-cancel`.
- [x] 6.5 [web-admin] TEST: add to `OrderDetailDialog.test.tsx` — test `barista on READY pickup` sees `order-action-handout`.
- [x] 6.6 [web-admin] TEST: add to `OrderDetailDialog.test.tsx` — test `barista on READY delivery` does NOT see `order-action-handout`.
- [x] 6.7 [web-admin] TEST: add to `OrderDetailDialog.test.tsx` — test `barista on COMPLETED` sees no `order-action-*` buttons.
- [x] 6.8 [web-admin] TEST: add to `OrderDetailDialog.test.tsx` — test `admin on CANCELLED` sees no `order-action-*` buttons.
- [x] 6.9 [web-admin] TEST: add to `OrderDetailDialog.test.tsx` — click `order-action-accept` → mocked fetch is called with `PATCH /api/v1/orders/<id>/status` body `{"new_status": "preparing"}`; `onAction` spy invoked.

## 7. Cancel confirmation sub-dialog

- [x] 7.1 [web-admin] IMPL: add a nested confirmation `<Dialog>` inside `OrderDetailDialog.tsx` triggered by "Отменить"; confirm button `data-testid="order-cancel-confirm"`; abort button `data-testid="order-cancel-abort"`; both disabled while request is in flight.
- [x] 7.2 [web-admin] TEST: add to `OrderDetailDialog.test.tsx` — happy-path: click `order-action-cancel`, then `order-cancel-confirm` → exactly one `POST /api/v1/orders/<id>/cancel` with body `{"reason": null}`, `onAction` invoked after success.
- [x] 7.3 [web-admin] TEST: add to `OrderDetailDialog.test.tsx` — abort path: click `order-action-cancel`, then `order-cancel-abort` → no fetch call; sub-dialog closes.

## 8. OrdersPage container

- [x] 8.1 [web-admin] IMPL: create `web/admin/src/pages/Orders/OrdersPage.tsx` with `useSearchParams` to read/write `status` / `type` / `page`; default `status=active`, `page=1`, `per_page=20`. Render status-tab row (7 tabs), native `<select>` type filter, `<OrdersTable>` (data from `listAdminOrders`), pagination controls (Previous/Next), and `<OrderDetailDialog>` keyed off currently-selected order id.
- [x] 8.2 [web-admin] IMPL: add polling — `useEffect` with `setInterval(10_000)` only when `status === 'active'` AND `document.visibilityState === 'visible'`; add `visibilitychange` listener to pause/resume; clear interval on filter change and unmount.
- [x] 8.3 [web-admin] IMPL: add the error-classification helper inside `OrdersPage.tsx` (maps `ApiError.status` → notification key per spec "Error handling" requirement); use it in every API call path.
- [x] 8.4 [web-admin] IMPL: create `web/admin/src/pages/Orders/index.tsx` re-exporting `OrdersPage`.
- [x] 8.5 [web-admin] IMPL: update `web/admin/src/App.tsx` — change the `OrdersPage` import path from `@/pages/OrdersPage` to `@/pages/Orders`; `allowedRoles` on the outer `ProtectedRoute` is unchanged.
- [x] 8.6 [web-admin] IMPL: delete the legacy file `web/admin/src/pages/OrdersPage.tsx`.

## 9. i18n content

- [x] 9.1 [web-admin] IMPL: fill out `pages.orders.*` keys in `web/admin/src/i18n/locales/ru/common.json` per the exhaustive list in `spec.md` → "i18n keys".
- [x] 9.2 [web-admin] IMPL: fill out the same key set in `web/admin/src/i18n/locales/en/common.json`. RU and EN SHALL have identical key shapes.

## 10. Verification

- [x] 10.1 [web-admin] VERIFY: run `pnpm --filter @aura-coffee/admin test` — all new tests under `web/admin/src/api/admin-orders.test.ts`, `web/admin/src/pages/Orders/OrdersTable.test.tsx`, and `web/admin/src/pages/Orders/OrderDetailDialog.test.tsx` pass; no regressions elsewhere.
- [x] 10.2 [web-admin] VERIFY: run `pnpm --filter @aura-coffee/admin typecheck` — zero TypeScript errors.
- [x] 10.3 [web-admin] VERIFY: run `pnpm --filter @aura-coffee/admin build` — Vite build succeeds.
- [x] 10.4 [web-admin] VERIFY: manual smoke — start the dev server, log in as admin, navigate to `/admin/orders`, confirm the seven tabs render, type filter renders, and clicking "Детали" on any row opens the modal. If no server + seed data is available locally, record in PR description that smoke was deferred.
