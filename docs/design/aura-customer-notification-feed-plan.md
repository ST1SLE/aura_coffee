# Aura Customer Notification Feed Plan

## Packet 1 - Profile Notification Feed

Status: complete

Files:

- `services/core-api/src/core_api/schemas/notification_feed.py`
- `services/core-api/src/core_api/services/notification_feed.py`
- `services/core-api/src/core_api/routers/notifications.py`
- `services/core-api/src/core_api/main.py`
- `services/core-api/src/core_api/rbac_matrix.py`
- `services/core-api/tests/test_customer_notifications.py`
- `web/customer/src/api/notifications.ts`
- `web/customer/src/api/notifications.test.ts`
- `web/customer/src/pages/Profile/Notifications/NotificationsPage.tsx`
- `web/customer/src/pages/Profile/Notifications/NotificationsPage.test.tsx`
- `web/customer/src/pages/ProfilePage.tsx`
- `web/customer/src/pages/ProfilePage.test.tsx`
- `web/customer/src/App.tsx`
- `web/customer/src/i18n/locales/en/common.json`
- `web/customer/src/i18n/locales/ru/common.json`
- `docs/audit-results/2026-05-02-audit-synthesis-and-remediation-plan.md`
- `docs/design/aura-customer-notification-feed-plan.md`

Context:

The May 2 audit left the customer notification feed as backlog. Backend
notification creation is already centralized in `core_api.services.notification`
and the database already has `notifications(user_id, created_at DESC)` for the
feed. The missing piece is a customer-visible read surface.

Decision:

Add a customer-only, read-only feed at `GET /api/v1/profile/notifications`,
scoped to the current user and filtered to `channel=in_app`. SMS notification
rows stay internal delivery/audit rows and are not duplicated in the customer
feed. Add `/profile/notifications` in the customer SPA, linked from Profile.

Out of scope:

- unread/read state, because the schema has no read marker
- notification creation semantics
- SMS worker behavior
- order/payment/delivery state transitions

Acceptance:

- customers can open Profile -> Notifications and see their own in-app
  notification rows newest first
- the feed excludes other users' notifications and SMS delivery rows
- rows show localized RU/EN message text, timestamp, and a link to the order
  when `order_id` is present
- empty, loading, error, and pagination states are covered
- server-side RBAC remains the authority; frontend route guards are UX only

Verification:

- `docker compose exec -T core-api pytest services/core-api/tests/test_customer_notifications.py services/core-api/tests/test_route_coverage.py -q`
- `docker compose exec -T core-api ruff check services/core-api/src/core_api/schemas/notification_feed.py services/core-api/src/core_api/services/notification_feed.py services/core-api/src/core_api/routers/notifications.py services/core-api/src/core_api/main.py services/core-api/src/core_api/rbac_matrix.py services/core-api/tests/test_customer_notifications.py`
- `cd web/customer && npm run typecheck`
- `cd web/customer && npm run lint`
- `cd web/customer && npm test -- src/api/notifications.test.ts src/pages/Profile/Notifications/NotificationsPage.test.tsx src/pages/ProfilePage.test.tsx`
- `cd web/customer && npm run build`
- Browser smoke on `/profile/notifications` at phone and desktop widths,
  checking no horizontal overflow, page errors, or unexpected API failures.
- Browser smoke captured 320px, 390px, and 1280px screenshots under
  `/tmp/aura-customer-notifications-*.png` after the idempotent Phase 4 QA seed.

## LDD Decision

This packet touches a customer-scoped read surface and therefore must verify
INV-002/INV-013 behavior, but it does not add a state-machine transition,
transaction boundary, notification creation path, SMS enqueue, or required LDD
marker emission. Required trajectory markers: none. Verification focuses on
RBAC, own-user scoping, SMS-row exclusion, and log redaction/no raw PII in
captured GRACE logs.
