# Aura Staff Mobile Polish Plan

## Packet 1 - Staff Tables And Menu Mobile Layout

Status: complete

Files:

- `web/admin/src/pages/Orders/OrdersTable.tsx`
- `web/admin/src/pages/Users/UsersTable.tsx`
- `web/admin/src/pages/Promos/PromosTable.tsx`
- `web/admin/src/pages/Menu/index.tsx`
- `web/admin/src/pages/Menu/CategoryList.tsx`
- `web/admin/src/pages/Menu/MenuItemsTable.tsx`
- `web/admin/src/pages/Menu/ModifiersPanel.tsx`
- `web/admin/src/components/Layout.tsx`
- `docs/design/aura-staff-mobile-polish-plan.md`

Context:

The May 2 staff UX audit downgraded table-heavy staff pages to backlog polish:
orders, users, promos, and menu management remain awkward on phones even when
horizontal overflow prevents a total layout break.

Decision:

Keep all existing routes, API calls, role checks, and mutation handlers intact.
Change only presentation so operational rows read as compact cards on mobile,
then return to normal tables on desktop. Stack the menu category selector above
items on smaller viewports and make modifier forms/list rows wrap safely.

Acceptance:

- orders, users, promos, and menu item rows expose their key fields without
  horizontal table scrolling on phone widths
- primary row actions remain visible and keep their existing handlers
- menu category selector stacks above item management on mobile
- modifier add/edit rows wrap instead of squeezing controls
- no backend, RBAC, auth/session, order transition, promocode state, menu CRUD,
  stop-list, PII/logging, or API contract behavior changes

Verification:

- `cd web/admin && npm run typecheck`
- `cd web/admin && npm run lint`
- `cd web/admin && npm test -- src/components/Layout.test.tsx src/pages/Orders/OrdersTable.test.tsx src/pages/Orders/OrdersPage.test.tsx src/pages/Users/UsersTable.test.tsx src/pages/Users/UsersPage.test.tsx src/pages/Promos/PromosTable.test.tsx src/pages/Promos/PromosPage.test.tsx src/pages/Menu/CategoryList.test.tsx src/pages/Menu/MenuItemsTable.test.tsx src/pages/Menu/ModifiersPanel.test.tsx`
- `cd web/admin && npm run build`
- Browser smoke on the canonical nginx URL for `/admin/orders`,
  `/admin/users`, `/admin/promos`, and `/admin/menu` at phone and desktop widths.
- Browser smoke captured 320px, 390px, and 1280px screenshots under
  `/tmp/aura-staff-mobile-polish-screenshots`.
- Browser smoke asserted no horizontal overflow, no page errors, no API 4xx/5xx
  responses, and expected route retention for `/admin/orders`, `/admin/users`,
  `/admin/promos`, and `/admin/menu`.

## LDD Decision

LDD assertions are not required for this packet if implementation remains
presentation-only in `M-WEB-ADMIN`. LDD becomes required if a later packet
changes server-side auth, RBAC, order transitions, promocode transitions,
payment/refund behavior, menu mutation semantics, PII logging, or required
GRACE marker emission.
