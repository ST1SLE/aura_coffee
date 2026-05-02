# Aura Admin Exception Queue Plan

## Packet 1 - Failed Refund Queue

Status: complete

Files:

- `services/core-api/src/core_api/routers/admin_orders.py`
- `services/core-api/src/core_api/services/order_history.py`
- `services/core-api/tests/test_admin_orders_list.py`
- `web/admin/src/api/admin-orders.ts`
- `web/admin/src/api/admin-orders.test.ts`
- `web/admin/src/pages/Orders/OrdersPage.tsx`
- `web/admin/src/pages/Orders/OrdersPage.test.tsx`
- `web/admin/src/i18n/locales/en/common.json`
- `web/admin/src/i18n/locales/ru/common.json`
- `docs/audit-results/2026-05-02-audit-synthesis-and-remediation-plan.md`
- `docs/design/aura-admin-exception-queue-plan.md`

Context:

The May 2 staff UX audit identified missing admin recovery paths for failed
refunds and courier-offline cases. The failed-refund path is already specified
in PDD §6.2: `REFUND_FAILED` is non-terminal, and an admin can retry the refund.
The retry command already exists in the order detail dialog, but admins have to
find affected orders manually.

Decision:

Add a read-only `refund_failed` filter to the existing staff orders feed and
surface it as an admin-only `Refund issues` tab. Reuse the existing order detail
dialog and retry command so mutation behavior, payment-worker ownership, and
LDD marker expectations stay unchanged.

Courier-offline recovery is intentionally out of scope because the requirements
still leave that behavior undefined. Manual reassignment/cancellation needs a
PDD decision before code.

Acceptance:

- admins can open `/admin/orders?status=refund_failed` and see orders with
  `Payment.status = REFUND_FAILED`
- the tab is visible only for admin role hints in the staff SPA
- the failed-refund queue can still be narrowed by pickup/delivery type
- regular active/completed/cancelled order filters retain their existing
  behavior and polling rules
- the existing detail dialog remains the only retry entry point, and the
  existing retry endpoint remains admin-only
- no order, payment, refund, delivery, auth, PII logging, or state-machine
  mutation behavior changes in this packet

Verification:

- `docker compose exec -T core-api pytest services/core-api/tests/test_admin_orders_list.py services/core-api/tests/test_admin_orders_detail.py services/core-api/tests/test_admin_refund_retry.py -q`
- `docker compose exec -T core-api ruff check services/core-api/src/core_api/services/order_history.py services/core-api/src/core_api/routers/admin_orders.py services/core-api/tests/test_admin_orders_list.py`
- `cd web/admin && npm run typecheck`
- `cd web/admin && npm run lint`
- `cd web/admin && npm test -- src/api/admin-orders.test.ts src/pages/Orders/OrdersPage.test.tsx src/pages/Orders/OrderDetailDialog.test.tsx`
- `cd web/admin && npm run build`
- Browser smoke on `/admin/orders?status=refund_failed` at phone and desktop
  widths, checking no horizontal overflow, page errors, or unexpected API
  failures.
- Browser smoke captured 320px, 390px, and 1280px screenshots under
  `/tmp/aura-admin-refund-queue-*.png`.

## LDD Decision

LDD assertions are not required for this packet if implementation remains a
read-only list filter plus frontend discoverability. The existing refund retry
mutation and payment-worker `REFUND_FAILED -> REFUND_PENDING` transition are
unchanged and keep their existing LDD requirements. LDD becomes required if a
later packet changes retry semantics, payment/refund state transitions, broker
side effects, auth/RBAC enforcement, PII logging, or required marker emission.
