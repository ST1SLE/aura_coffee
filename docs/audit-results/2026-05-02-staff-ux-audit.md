# Staff/Admin/Barista/Courier UX and Operations Audit

Date: 2026-05-02

Scope: `web/admin` role routing, admin CRUD pages, barista workflow, courier workflow, logout/session switching, order feed freshness, stop-list scope, settings, users/loyalty/promos, dashboard analytics, forms/errors/empty states, mobile staff usability, i18n/a11y, and whether staff roles can execute PDD responsibilities.

Method: source inspection and non-destructive checks only. No runtime stack was started and no tests were run for this audit.

## Executive Summary

The admin/barista surface is broadly present: staff login exists, admin CRUD pages exist for menu/users/promos/settings, baristas can see orders and stop-list controls, and the backend RBAC matrix has explicit staff/admin route entries. The largest operational risks are in the courier workflow and staff operations recovery paths.

Two issues can block real staff operations:

1. The courier frontend and backend disagree on assignment DTO shape, so courier cards can fail to render or show unusable data.
2. Delivery assignments become visible/takeable before the order is `READY`, conflicting with the PDD workflow and creating avoidable courier/barista races.

Mobile staff usability is also incomplete: the admin/barista layout hides the desktop sidebar and does not provide a mobile navigation replacement.

## Prioritized Findings

### P0 - Courier assignment API contract does not match the courier UI

Impact: Couriers may be unable to execute their PDD responsibility of accepting, picking up, and delivering orders.

Evidence:

- Frontend courier type and card expect `delivery_address.address_line`, `total`, and `requested_time`: `web/admin/src/api/courier.ts:42-61`, `web/admin/src/pages/Courier/AssignmentCard.tsx:55-58`.
- `AvailableTab` renders every API row through `AssignmentCard`: `web/admin/src/pages/Courier/AvailableTab.tsx:81-98`.
- Backend available assignments return `delivery_address_snapshot`, not `delivery_address`: `services/core-api/src/core_api/services/delivery_assignment.py:342-349`.
- Backend "mine" assignments return only `id`, `order_id`, `status`, and timestamps; no address, total, or requested time: `services/core-api/src/core_api/routers/courier.py:128-136`.
- Backend mutation endpoints return status-only dictionaries, not `CourierAssignmentResponse`: `services/core-api/src/core_api/routers/courier.py:149-166`, `178-195`, `208-225`.
- Frontend tests mock the frontend-desired shape rather than the backend shape: `web/admin/src/pages/Courier/AvailableTab.test.tsx:29-40`, `web/admin/src/pages/Courier/MineTab.test.tsx:22-33`.

Suggested fix:

- Define one backend `CourierAssignmentResponse` schema and use it for all courier list and mutation responses.
- Normalize snapshot as `delivery_address` or change the frontend type and card to consume `delivery_address_snapshot`.
- Include `total` and `requested_time` for `mine`, not only `available`.
- Add an integration-style test that renders `AvailableTab`/`MineTab` with actual router/service response shapes or generated OpenAPI types.

### P0 - Courier can take delivery assignments before the order is ready

Impact: The delivery workflow can expose not-yet-ready orders to couriers. A courier can claim an assignment while the barista is still preparing it, then hit `order_not_ready` on pickup. This conflicts with the PDD handoff model and creates operational confusion.

Evidence:

- PDD says `READY -> IN_DELIVERY` happens when the courier takes the delivery order, with `order.type = DELIVERY`: `docs/PRODUCT_DESIGN_DOCUMENT.md:371-377`.
- Development flow says delivery assignment is triggered when the order moves to `READY`: `docs/development-plan.xml:188-193`.
- Backend currently creates `DeliveryAssignment(AWAITING_COURIER)` on `PAID -> PREPARING` for delivery orders: `services/core-api/src/core_api/services/order_lifecycle.py:159-168`.
- The available courier feed filters only on assignment status, not joined order status: `services/core-api/src/core_api/services/delivery_assignment.py:330-340`.
- `take_assignment` only checks assignment status `AWAITING_COURIER`: `services/core-api/src/core_api/services/delivery_assignment.py:120-146`.
- `pickup_assignment` later rejects non-`READY` orders: `services/core-api/src/core_api/services/delivery_assignment.py:196-198`.

Suggested fix:

- Prefer creating the assignment on `PREPARING -> READY` for delivery orders, matching the PDD and development plan.
- Alternatively, if pre-assignment is desired, update the PDD/UX language and separate "claim delivery" from "pickup order"; keep `available` filtered or labelled so couriers do not interpret it as ready for pickup.
- Add state-machine tests covering "preparing delivery order is not visible/takeable to courier" or the explicitly approved alternative behavior.

### P1 - Admin can enter the courier route, but backend courier APIs are courier-only

Impact: Admins see a courier surface that cannot load data. Depending on intended product behavior, this either blocks admin delivery supervision or creates a misleading empty/failed page.

Evidence:

- Frontend route allows both `admin` and `courier` into the courier shell: `web/admin/src/App.tsx:95-103`.
- Backend RBAC allows only `COURIER` for all courier endpoints: `services/core-api/src/core_api/rbac_matrix.py:115-120`.
- `CourierShell` says it is mounted behind a route that allows admin+courier: `web/admin/src/pages/Courier/CourierShell.tsx:14-20`.
- `AvailableTab` handles only 409 mutation races; query 401/403/500 states have no visible error branch and can collapse to an empty list after failure: `web/admin/src/pages/Courier/AvailableTab.tsx:46-79`.

Suggested fix:

- Decide the product rule:
  - If admins should supervise deliveries, add admin-authorized backend endpoints with explicit semantics.
  - If admins should not use courier operations, make `/courier` courier-only in `App.tsx`.
- Render query error states for courier tabs, especially 403, instead of showing an empty operational feed.

### P1 - Staff logout and session refresh are only partially implemented in the admin SPA

Impact: Staff sessions expire after access-token TTL without refresh, and logout does not revoke the refresh token that the backend issues. This hurts session switching and leaves stale backend refresh sessions.

Evidence:

- Backend login issues both access and refresh tokens: `services/core-api/src/core_api/routers/staff_auth.py:41-72`.
- Backend supports refresh rotation and logout revocation: `services/core-api/src/core_api/routers/staff_auth.py:75-126`.
- Access token TTL defaults to 900 seconds; refresh TTL defaults to 604800 seconds: `services/core-api/src/core_api/settings.py:11-14`.
- Frontend `staffLogin` returns only `access_token` and `role`, discarding `refresh_token`: `web/admin/src/api/client.ts:152-185`.
- Frontend `logout()` only clears localStorage and navigates; it does not call `/api/v1/staff/auth/logout`: `web/admin/src/api/client.ts:65-70`.

Suggested fix:

- Add explicit staff refresh-token storage and rotation, or simplify backend/client contracts if short sessions are intended.
- On logout, call backend staff logout when a refresh token exists, then clear local state even if revocation fails.
- Add tests for role switching: admin -> logout -> courier login; expired access token -> refresh or clean login redirect.

### P1 - Admin/barista mobile navigation is missing

Impact: Staff on phones can lose access to key pages. The desktop sidebar is hidden below `md`, while the mobile header only exposes title, logout, and language switcher.

Evidence:

- Sidebar containing nav links is `hidden md:flex`: `web/admin/src/components/Layout.tsx:69-100`.
- Mobile header renders title, logout, and language switcher, but no nav/drawer/bottom tabs: `web/admin/src/components/Layout.tsx:103-120`.
- Admin/barista pages depend on that layout for access to dashboard/orders/menu/users/promos/settings: `web/admin/src/App.tsx:60-94`.

Suggested fix:

- Add a mobile navigation drawer or bottom nav using the same `NAV_BY_ROLE` source.
- Include order/menu shortcuts for baristas and the full admin set for admins.
- Add viewport tests or Playwright screenshots for at least admin and barista at mobile width.

### P2 - Order feed freshness is weaker than the staff real-time expectation

Impact: Baristas and admins can miss changes for up to 10 seconds on the active feed, and non-active filtered views do not poll. This is noticeable in an operations screen.

Evidence:

- `OrdersPage` contract references "real-time feed within 5s" but code uses 10-second polling: `web/admin/src/pages/Orders/OrdersPage.tsx:21-34`, `56-58`.
- Polling only runs for the `active` status filter and pauses when the document is hidden: `web/admin/src/pages/Orders/OrdersPage.tsx:213-245`.
- Courier tabs use 5-second React Query polling: `web/admin/src/pages/Courier/AvailableTab.tsx:46-51`, `web/admin/src/pages/Courier/MineTab.tsx:70-75`.

Suggested fix:

- Align staff order feed polling with the 5-second expectation, or document the intended 10-second SLA.
- Consider polling selected order detail while the dialog is open.
- Longer term, use SSE/WebSocket/event stream for staff order updates.

### P2 - Admin operations recovery paths are incomplete for refund failure and courier offline cases

Impact: Admins may not be able to fulfill required exception-handling responsibilities inside the staff SPA.

Evidence:

- PDD says `REFUND_FAILED` is non-terminal and admin must resolve it via retry or manual refund: `docs/PRODUCT_DESIGN_DOCUMENT.md:413-422`.
- Source search found no admin refund/retry UI or router path under `web/admin/src` or `services/core-api/src/core_api/routers`.
- Requirements explicitly leave courier-offline recovery as an open question: `docs/requirements.xml:111`.
- There is no admin delivery reassignment or courier supervision screen in the route set: `web/admin/src/App.tsx:60-103`.

Suggested fix:

- Add an admin operations queue for failed refunds, stuck deliveries, and cancelled/exceptional orders.
- Expose a retry-refund action backed by a server-side endpoint with RBAC and LDD assertions.
- Define courier-offline recovery in the PDD before implementing manual reassignment or cancellation behavior.

### P2 - Table-heavy staff pages are not mobile-optimized

Impact: Even where horizontal overflow prevents total layout breakage, staff workflows are awkward on phones, especially orders, users, promos, and menu management.

Evidence:

- Shared table primitive wraps tables in horizontal overflow: `web/admin/src/components/ui/table.tsx:23-31`.
- Orders, users, and promos render full tables with action buttons: `web/admin/src/pages/Orders/OrdersTable.tsx:73-110`, `web/admin/src/pages/Users/UsersTable.tsx:60-107`, `web/admin/src/pages/Promos/PromosTable.tsx:89-159`.
- Menu layout is a fixed side-by-side flex with a 14rem category column: `web/admin/src/pages/Menu/index.tsx:76-95`, `web/admin/src/pages/Menu/CategoryList.tsx:171-172`.

Suggested fix:

- For mobile, render operational lists as cards with primary actions visible.
- Stack the menu category selector above items, or turn it into a select/tabs pattern on small viewports.
- Add mobile snapshots for order detail, stop-list toggles, courier tabs, user detail, promo form, and settings.

### P3 - A11y gaps in icon buttons and tabs

Impact: Keyboard and screen-reader usability is incomplete in several staff controls.

Evidence:

- Menu item edit/delete icon buttons have no accessible text or `aria-label`: `web/admin/src/pages/Menu/MenuItemsTable.tsx:176-190`.
- Category edit/delete buttons rely on `title` only: `web/admin/src/pages/Menu/CategoryList.tsx:257-275`.
- Modifier edit/delete icon buttons have no accessible text or `aria-label`: `web/admin/src/pages/Menu/ModifiersPanel.tsx:248-260`.
- Courier tab buttons set `role="tab"` and `aria-selected`, but no `aria-controls`/tabpanel relationship: `web/admin/src/pages/Courier/CourierPage.tsx:37-55`, `65-81`.

Suggested fix:

- Add localized `aria-label`s for all icon-only edit/delete controls.
- Connect tab buttons to tab panels with `aria-controls` and `role="tabpanel"`.
- Add a focused accessibility test slice for menu controls and courier tabs.

## Role Responsibility Coverage

### Admin

Covered:

- Admin route set includes dashboard, orders, menu, users, promos, and settings: `web/admin/src/components/Layout.tsx:40-46`.
- Backend RBAC protects admin-only users/promos/settings/stats routes: `services/core-api/src/core_api/rbac_matrix.py:97-114`.
- Settings page covers shop coordinates, delivery, loyalty, timing, and working hours through a full-snapshot form: `web/admin/src/pages/Settings/SettingsPage.tsx:177-193`.
- Users page supports status filters, search, block/unblock, and loyalty adjustment: `web/admin/src/pages/Users/UsersPage.tsx:122-204`, `web/admin/src/pages/Users/UserDetailDialog.tsx:176-212`.
- Promos page supports filters, search, create/edit, activate/deactivate: `web/admin/src/pages/Promos/PromosPage.tsx:173-230`.

Gaps:

- No visible refund-failure recovery flow.
- No courier supervision/reassignment flow.
- Admin `/courier` route conflicts with backend courier-only RBAC.

### Barista

Covered:

- Barista route set is orders + menu: `web/admin/src/components/Layout.tsx:40-46`.
- Barista can accept paid orders and mark preparing orders ready: `web/admin/src/pages/Orders/OrderDetailDialog.tsx:71-118`.
- Barista can complete ready pickup orders: `web/admin/src/pages/Orders/OrderDetailDialog.tsx:81-84`, `110-118`.
- Barista can toggle menu item and modifier availability/stop-list without full CRUD: `web/admin/src/pages/Menu/MenuItemsTable.tsx:167-173`, `web/admin/src/pages/Menu/ModifiersPanel.tsx:236-241`.

Gaps:

- Delivery assignments are exposed before `READY`, weakening the barista-to-courier handoff.
- Mobile barista navigation is missing.
- Active order feed polling is 10 seconds, not 5 seconds.

### Courier

Covered:

- Courier route has available/mine tabs and 5-second polling: `web/admin/src/pages/Courier/CourierPage.tsx:36-55`, `web/admin/src/pages/Courier/AvailableTab.tsx:46-51`, `web/admin/src/pages/Courier/MineTab.tsx:70-75`.
- Courier API endpoints exist for available, mine, take, pickup, and deliver: `services/core-api/src/core_api/routers/courier.py:83-225`.
- Delivery service enforces owner checks on pickup/deliver: `services/core-api/src/core_api/services/delivery_assignment.py:193-198`, `246-254`.

Gaps:

- DTO mismatch likely breaks rendering and operational use.
- Available/take semantics can happen before order readiness.
- Mine endpoint lacks address and order economics required by the card UI.
- No visible error handling for query failures.

## Positive Notes

- Server-side RBAC is explicit in `ROUTE_MATRIX`, and the frontend correctly treats role hints as UX-only rather than security boundaries.
- Admin CRUD pages generally have loading and empty states.
- Promo and settings forms include field-level validation/error parsing.
- User blocking includes a confirmation flow for active-order cancellation risk.
- i18n coverage has both RU and EN locale files, with parity tests present under `web/admin/src/i18n/locales/__tests__`.

## Verification Status

Commands/checks performed:

- Source inspection with `rg`, `find`, `nl`, and targeted reads.
- No destructive commands.
- No runtime stack started.
- No tests run.

GRACE/LDD gate:

- This audit did not modify runtime code or tests.
- LDD assertions were not added or run because the requested output was a documentation-only audit report.
- Any implementation of the P0/P1 fixes touching courier/order transitions, auth/session flows, refunds, RBAC, or PII/logging will require the GRACE LDD gate before completion.
