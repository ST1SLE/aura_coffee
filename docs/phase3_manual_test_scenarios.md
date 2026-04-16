---
Pre-flight

./scripts/up.sh

Banner must show Migrations: applied ✓. If it shows FAILED, stop — run docker compose logs
db-migrate.

> Dev notes
> - OTP / notification SMS: dev stack sets SMS_BACKEND=log. All SMS (OTP and order
>   notifications) are printed to `docker compose logs sms-worker` as:
>     [SMS:log] to=<phone> msg=<text>
> - ЮKassa: dev stack uses ЮKassa TEST shop creds (YUKASSA_BASE_URL points to the
>   sandbox, YUKASSA_SHOP_ID/SECRET_KEY are test values). Test card numbers are
>   documented at https://yookassa.ru/developers/payment-acceptance/testing-and-going-live/testing
>   Use 5555 5555 5555 4477 (any future expiry, any CVC) for a successful payment
>   and 5555 5555 5555 4444 for a declined one.
> - Webhook delivery in dev: ЮKassa sandbox cannot reach localhost directly. Two
>   options below:
>     (a) expose payment-worker via a tunnel (ngrok/cloudflared) and register the
>         public URL in the ЮKassa merchant dashboard;
>     (b) simulate webhook calls locally with curl (see Block 4.3/4.4). Port bypass:
>         the webhook is exposed on port 8241 by default (see .env.example), and the
>         IP whitelist is disabled when YUKASSA_WEBHOOK_IPS=* (dev default).
> - Loyalty balance: each customer starts with 0 баллов. To test point redemption
>   you must either pay for one prior order that reaches COMPLETED (accrual), or
>   insert an ACCRUAL transaction directly (see Part D).

---
Part A — Get admin JWT

1. Open http://localhost:8240/admin → browser lands on /admin/dashboard.
2. Log in with admin / admin123.
3. Keep this tab open.

For API testing get a token:
curl -s -X POST http://localhost:8240/api/v1/staff/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"login":"admin","password":"admin123"}' | jq -r .access_token
Save as $ADMIN_TOKEN.

---
Part B — Get customer JWT (OTP workaround)

1. Open http://localhost:8240/ → navigate to login.
2. Enter phone +79991234567, submit.
3. Pull OTP from logs:
docker compose logs --tail 20 sms-worker | grep '[SMS:log]'
4. Enter the code on the verify page. Keep tab open.

For API testing:
curl -s -X POST http://localhost:8240/api/v1/auth/send-code \
  -H 'Content-Type: application/json' \
  -d '{"phone":"+79991234567"}'
# get code from: docker compose logs --tail 20 sms-worker | grep '[SMS:log]'
curl -s -X POST http://localhost:8240/api/v1/auth/verify-code \
  -H 'Content-Type: application/json' \
  -d '{"phone":"+79991234567","code":"<code>"}' | jq -r .access_token
Save as $CUST_TOKEN.

Second customer (needed for 4.8, 10.3):
Repeat the flow with +79991234568 → save as $CUST2_TOKEN.

---
Part C — Staff tokens (barista, courier)

Staff users are created by seed migrations (login / password):
- barista1 / barista123
- courier1 / courier123

curl -s -X POST http://localhost:8240/api/v1/staff/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"login":"barista1","password":"barista123"}' | jq -r .access_token
# save as $BAR_TOKEN
curl -s -X POST http://localhost:8240/api/v1/staff/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"login":"courier1","password":"courier123"}' | jq -r .access_token
# save as $COUR_TOKEN

If seed logins differ, check `database/seeds/` and adjust.

---
Part D — Test data prep

Menu baseline (replays Phase 2 prep). Create if missing:

- Category Кофе (type=drink, sort_order=1, visible)
- Item Эспрессо (base_price=15000, available=true) — save $ESPRESSO_ID
- Item Капучино (base_price=0, available=true) — save $CAPPUCCINO_ID
  - Sizes: M(26000), L(30000)
  - Modifier: Vanilla syrup (5500, available=true) — save $VANILLA_ID

All prices above are in **копейки** (150₽ → 15000). Verify via:
curl -s http://localhost:8240/api/v1/menu | jq '.[0].items[] | {name,base_price}'

Seed a loyalty balance of 500 баллов for the main test customer (needed for
Block 3 point redemption). Run from the host:
docker compose exec core-api python -c "
from shared.db import SessionLocal
from shared.models import User, LoyaltyAccount, LoyaltyTransaction
from shared.enums import LoyaltyTransactionType
s = SessionLocal()
u = s.query(User).filter_by(phone_hash_lookup_hash='<paste hash from auth step>').first()
# OR look up by phone directly if helper available
acct = s.query(LoyaltyAccount).filter_by(user_id=u.id).one()
acct.balance += 500
s.add(LoyaltyTransaction(user_id=u.id, type=LoyaltyTransactionType.ADMIN_ADJUSTMENT,
                         amount=500, balance_after=acct.balance, description='test seed'))
s.commit()
print('balance:', acct.balance)
"
Easier: log in to admin SPA → Users → find customer → "Adjust loyalty" (if UI
exposes it). Note whichever method works; the assertions below assume balance ≥ 500.

Seed one promocode via admin SQL (Phase 5 will add UI). From host:
docker compose exec db psql -U postgres -d aura -c "
INSERT INTO promocodes (id, code, discount_type, discount_value, min_order_amount,
 valid_from, valid_until, max_uses, max_uses_per_user, current_uses, is_active, created_at)
VALUES (gen_random_uuid(), 'WELCOME10', 'PERCENT', 10, 0,
 now() - interval '1 day', now() + interval '30 days', 100, 5, 0, true, now());
INSERT INTO promocodes (id, code, discount_type, discount_value, min_order_amount,
 valid_from, valid_until, max_uses, max_uses_per_user, current_uses, is_active, created_at)
VALUES (gen_random_uuid(), 'FLAT50', 'FIXED_AMOUNT', 5000, 0,
 now() - interval '1 day', now() + interval '30 days', 100, 5, 0, true, now());
INSERT INTO promocodes (id, code, discount_type, discount_value, min_order_amount,
 valid_from, valid_until, max_uses, max_uses_per_user, current_uses, is_active, created_at)
VALUES (gen_random_uuid(), 'EXPIRED', 'PERCENT', 50, 0,
 now() - interval '30 days', now() - interval '1 day', 100, 5, 0, true, now());
"

---
Block 1 — Checkout: happy paths

Before each scenario: clear cart (DELETE /api/v1/cart) to isolate state.

1.1 Pickup, no modifiers, ASAP
- Add Эспрессо × 2 to cart (POST /api/v1/cart/items via UI or API).
- Submit:
curl -s -X POST http://localhost:8240/api/v1/orders \
  -H "Authorization: Bearer $CUST_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"type":"PICKUP"}' | jq
- Expect HTTP 201. Response: `status=CREATED`, `type=PICKUP`, `subtotal=30000`,
  `discount_amount=0`, `points_used=0`, `delivery_fee=0`, `total=30000`,
  `estimated_accrual=1500` (5% of 30000), `items[].line_total=15000` × 2,
  `requested_time=null`, `estimated_ready_at` ≈ now + 15 min.
- Save returned `id` as $ORDER_ID.
- DB check: cart STILL present in Redis (deleted only after PAID).
  docker compose exec redis redis-cli KEYS 'cart:*'
  → at least one entry.

1.2 Delivery, with modifier and size
- Add Капучино M + Vanilla syrup × 1 and × 2 separately until subtotal ≥ 50000
  (min_delivery_amount). Example: Капучино M × 3 (780) + syrup × 3 = 96500.
- Submit:
curl -s -X POST http://localhost:8240/api/v1/orders \
  -H "Authorization: Bearer $CUST_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"type":"DELIVERY","delivery_address":{"text":"Москва, Тверская 1","lat":55.7601,"lon":37.6086,"apartment":"12","entrance":"2","floor":"3"}}' | jq
- Expect HTTP 201. Response: `type=DELIVERY`, `delivery_fee=20000`,
  `total=subtotal+20000`, `estimated_accrual` computed from `after_points` only
  (excludes delivery fee — INV-003).
- `delivery_address_snapshot` persisted (verify with GET detail).

1.3 Total = 0 skips ЮKassa (full points coverage)
- Add Эспрессо × 1 (price 15000). Require loyalty balance ≥ 150 (15000 коп).
- Submit:
curl -s -X POST http://localhost:8240/api/v1/orders \
  -H "Authorization: Bearer $CUST_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"type":"PICKUP","points_to_use":15000}' | jq
- Expect HTTP 201. Response: `status=PAID` (not CREATED), `total=0`,
  `points_used=15000`. No `confirmation_url`.
- DB check: cart was deleted from Redis, loyalty balance decreased by 15000.
- No Celery task enqueued for payment:
  docker compose logs payment-worker --tail 20 | grep -i 'create_payment'
  → no fresh entry.

---
Block 2 — Checkout validation

2.1 Empty cart
- Clear cart. POST /api/v1/orders → 400 "Корзина пуста".

2.2 Stop-list enforcement
- Admin: set Эспрессо available=false.
- Customer cart has Эспрессо. POST /api/v1/orders → 409,
  body references the unavailable item. No Order row created:
  docker compose exec db psql -U postgres -d aura -c "SELECT count(*) FROM orders WHERE status='CREATED' AND created_at > now()-interval '1 min';"
- Re-enable Эспрессо after test.

2.3 Working hours — scheduled time in the past
curl -s -X POST http://localhost:8240/api/v1/orders \
  -H "Authorization: Bearer $CUST_TOKEN" -H 'Content-Type: application/json' \
  -d '{"type":"PICKUP","requested_time":"2000-01-01T10:00:00Z"}'
- Expect 409 with reason referring to time slot.

2.4 Working hours — outside shop hours
- Temporarily shrink working hours via SQL so the current time is outside:
  UPDATE shop_settings SET working_hours = '{"mon":{"open":"03:00","close":"03:05"},"tue":{"open":"03:00","close":"03:05"},...}' WHERE id=1;
- POST /api/v1/orders (ASAP) → 409, validator finds next opening or rejects.
- Restore working hours to defaults afterwards.

2.5 Delivery — outside radius
- Submit delivery order with `lat=0, lon=0` (far from shop) → 409 "outside delivery radius".

2.6 Delivery — below min amount
- Cart with single Эспрессо (subtotal 15000 < 50000). Submit DELIVERY:
  → 409, message about min delivery amount.

2.7 Delivery — no address
- Cart subtotal ≥ 50000 but body omits `delivery_address`: → 422 validation error.

---
Block 3 — Pricing chain

3.1 Promocode PERCENT
- Add Эспрессо × 2 (subtotal 30000). Submit:
  `{"type":"PICKUP","promocode_code":"WELCOME10"}`
- Expect `discount_amount=3000`, `total=27000`, `estimated_accrual=1350` (5% of 27000).

3.2 Promocode FIXED_AMOUNT
- Same cart, `promocode_code=FLAT50` → `discount_amount=5000`, `total=25000`.

3.3 Promocode — expired
- `promocode_code=EXPIRED` → 409, message references promocode.

3.4 Promocode — min order amount
- Insert a promocode with min_order_amount=100000. Cart 30000 → 409.

3.5 Promocode — per-user limit
- Call 5 successful orders with WELCOME10 (decrement loyalty to avoid running out
  of cash; use small carts). 6th attempt → 409, "max_uses_per_user".

3.6 Loyalty — request more than balance
- `points_to_use: 999999`, balance=500 → `points_used` capped at `min(balance, after_promo)`.
  No error.

3.7 Loyalty — reservation recorded
- Before/after an order with points_to_use=100, query:
  SELECT type, amount, balance_after FROM loyalty_transactions
  WHERE user_id=<id> ORDER BY created_at DESC LIMIT 3;
- Expect a `RESERVATION` row with amount=-100. Balance decremented immediately.

3.8 Free delivery threshold
- Cart subtotal ≥ 150000 (free_delivery_threshold). DELIVERY order → `delivery_fee=0`.

3.9 Estimated accrual excludes delivery
- DELIVERY order, subtotal=100000, delivery_fee=20000, no promo/points.
- Expect `total=120000` but `estimated_accrual=5000` (5% of subtotal, not of total).

---
Block 4 — Payment (ЮKassa)

4.1 Payment creation kicks off
- Place a pickup order with total > 0 (Block 1.1).
- Within ~5s, observe:
  docker compose logs payment-worker --tail 50 | grep -E 'create_payment|yukassa'
  → sees a POST /v3/payments call.
- Poll order detail until `confirmation_url` is populated:
  watch -n1 'curl -s -H "Authorization: Bearer $CUST_TOKEN" http://localhost:8240/api/v1/orders/$ORDER_ID | jq .confirmation_url'
- Expect a ЮKassa URL within 5–10s.

4.2 Customer completes payment (sandbox)
- Open `confirmation_url` in browser → ЮKassa test page.
- Pay with test card 5555 5555 5555 4477 (any CVC, future expiry).
- Within ~30s (webhook delivery or polling fallback — §6.1), GET the order:
  `status=PAID`, loyalty reservation confirmed (balance unchanged vs before order),
  and cart is gone from Redis.

4.3 Webhook simulated — payment.succeeded
Skip 4.2 if no ЮKassa tunnel. Place a new order, wait until Payment row has
`yukassa_payment_id` populated (DB query or poll):
  PAY_ID=$(docker compose exec -T db psql -U postgres -d aura -t -c "SELECT yukassa_payment_id FROM payments WHERE order_id='$ORDER_ID';" | xargs)
Then POST a fake webhook:
curl -s -X POST http://localhost:8241/webhooks/yukassa \
  -H 'Content-Type: application/json' \
  -d "{\"event\":\"payment.succeeded\",\"object\":{\"id\":\"$PAY_ID\",\"status\":\"succeeded\",\"paid\":true}}"
- GET the order → `status=PAID`.
- SMS in log: `[SMS:log] ... Заказ №<8hex> оплачен`.

4.4 Webhook simulated — payment.canceled
- Place a fresh order (with promocode WELCOME10 + points_to_use=50 so we can
  observe unreservation).
- Get PAY_ID as above. POST:
curl -s -X POST http://localhost:8241/webhooks/yukassa \
  -H 'Content-Type: application/json' \
  -d "{\"event\":\"payment.canceled\",\"object\":{\"id\":\"$PAY_ID\",\"status\":\"canceled\"}}"
- Expect: order `status=CANCELLED`, loyalty balance restored, `promocodes.current_uses`
  decremented, `promocode_usages` row removed.
- In-app notification recorded (GET notifications via DB: SELECT * FROM notifications
  WHERE order_id=... ORDER BY created_at DESC).

4.5 Webhook idempotency
- Replay the exact same webhook payload → order state unchanged, no duplicate
  notifications. Worker logs should show "already processed" / skip.

4.6 Webhook IP blacklist (if enabled)
- Set YUKASSA_WEBHOOK_IPS=1.2.3.4 in .env, restart payment-worker.
- POST webhook from localhost → 403.
- Restore YUKASSA_WEBHOOK_IPS=* afterwards.

4.7 Payment failure retry + cancel
- Temporarily break ЮKassa creds (YUKASSA_SECRET_KEY=bad) and restart worker.
- Place an order. Observe 3 retry attempts in logs, then:
  - Order → `CANCELLED`
  - Payment → `PAYMENT_FAILED`
  - Loyalty/promocode (if any) reverted.
- Restore creds after test.

4.8 Foreign order access
curl -s -o /dev/null -w '%{http_code}\n' \
  -H "Authorization: Bearer $CUST2_TOKEN" \
  http://localhost:8240/api/v1/orders/$ORDER_ID
- Expect 404 (INV-013 — no leak of existence).

---
Block 5 — Order lifecycle (staff transitions)

Use an order in `status=PAID` (from Block 4.2 or 4.3). Call as $BAR_TOKEN /
$COUR_TOKEN / $ADMIN_TOKEN.

5.1 PAID → PREPARING (barista)
curl -s -X PATCH http://localhost:8240/api/v1/orders/$ORDER_ID/status \
  -H "Authorization: Bearer $BAR_TOKEN" -H 'Content-Type: application/json' \
  -d '{"new_status":"PREPARING"}' | jq
- 200. SMS: "... готовится".

5.2 PREPARING → READY (barista)
- Same pattern. SMS: "... готов".

5.3 READY → COMPLETED — pickup path (barista)
- For a PICKUP order: PATCH new_status=COMPLETED → 200.
- DB: loyalty_transactions has an ACCRUAL row with amount = 5% of (total - delivery_fee).
- Loyalty balance increased.

5.4 READY → IN_DELIVERY (courier, delivery order only)
- Create a DELIVERY order and advance to READY.
- PATCH as $COUR_TOKEN with new_status=IN_DELIVERY → 200.
- Attempting the same on a PICKUP order → 409.

5.5 IN_DELIVERY → COMPLETED (courier)
- PATCH new_status=COMPLETED → 200. Accrual happens now.

5.6 Forbidden transition — backward
- On a PREPARING order: PATCH new_status=PAID → 409 "transition_forbidden".

5.7 Forbidden transition — from COMPLETED
- On a COMPLETED order: PATCH new_status=PREPARING → 409.

5.8 Role enforcement
- As $BAR_TOKEN: PATCH READY→IN_DELIVERY → 403 / 409 (barista can't move to IN_DELIVERY).
- As $COUR_TOKEN: PATCH PAID→PREPARING → 403 / 409.
- As $CUST_TOKEN: PATCH any → 403 (customer cannot transition).

5.9 Transition on unknown order
- PATCH /api/v1/orders/<random-uuid>/status → 404.

---
Block 6 — Cancellation

6.1 Customer cancel — allowed only in PAID
- Order in `status=PAID`:
curl -s -X POST http://localhost:8240/api/v1/orders/$ORDER_ID/cancel \
  -H "Authorization: Bearer $CUST_TOKEN" -H 'Content-Type: application/json' \
  -d '{"reason":"передумал"}' | jq
- Expect 200, `status=CANCELLED`, `cancelled_by=customer`, `cancelled_at` set.
- Refund task enqueued: docker compose logs payment-worker | grep initiate_refund
- SMS: "... отменён, средства возвращены".

6.2 Customer cancel in PREPARING — forbidden
- Advance a paid order to PREPARING, then POST cancel as customer → 409
  (INV-005: only admin can cancel after PREPARING).

6.3 Customer cancel — foreign order
- POST cancel on someone else's order → 403 or 404. No leakage of existence.

6.4 Admin cancel in PREPARING
- POST cancel as $ADMIN_TOKEN on a PREPARING order → 200, `cancelled_by=admin`.
- Loyalty returned (REVERSAL transaction), promocode.current_uses decremented.

6.5 Admin cancel in IN_DELIVERY — forbidden
- POST cancel on IN_DELIVERY order → 409 (PDD §7.6: not cancellable after dispatch).

6.6 Admin cancel of COMPLETED — forbidden
- → 409.

6.7 Cancel of total=0 order — no refund
- Use order from 1.3 (total=0, status=PAID). Cancel as admin → 200.
- payment-worker log: no initiate_refund fired (payment.amount=0).
- Loyalty returned (balance back to pre-order value).

6.8 Refund webhook — refund.succeeded
- After 6.1, grab PAY_ID and simulate:
curl -s -X POST http://localhost:8241/webhooks/yukassa \
  -H 'Content-Type: application/json' \
  -d "{\"event\":\"refund.succeeded\",\"object\":{\"id\":\"test_refund_1\",\"payment_id\":\"$PAY_ID\",\"status\":\"succeeded\"}}"
- Payment row → `status=REFUNDED`.

---
Block 7 — Notifications

7.1 In-app feed
- GET /api/v1/notifications (if UI route exists) or SQL check:
  SELECT type, channel, message_ru, status FROM notifications
  WHERE user_id=<id> ORDER BY created_at DESC LIMIT 10;
- Every status transition from Blocks 5–6 should have an IN_APP row.

7.2 SMS delivery
- For each SMS-eligible status (PAID, PREPARING, READY, COMPLETED-delivery,
  CANCELLED), verify a `[SMS:log]` line in sms-worker logs with message ≤70 chars
  and including "Aura Coffee".

7.3 SMS not sent on IN_DELIVERY or COMPLETED-pickup
- IN_DELIVERY and COMPLETED (for PICKUP) are in-app-only per PDD §6.1. Confirm
  no extra SMS line in logs around that transition timestamp.

7.4 Language preference
- Change user preferred_language to EN (PATCH /api/v1/profile or SQL).
- Trigger a transition → notification.message_en is used; SMS line is English.
- Restore language afterwards.

7.5 SMS retry on worker failure
- Stop sms-worker: docker compose stop sms-worker
- Trigger an order transition → notification row created with status=PENDING.
- Start worker: docker compose start sms-worker
- Within ~30s, status flips to SENT (retry succeeded). Order flow NOT blocked.

---
Block 8 — Order history & detail

8.1 List own orders
curl -s -H "Authorization: Bearer $CUST_TOKEN" \
  'http://localhost:8240/api/v1/orders?page=1&per_page=5' | jq
- 200, items sorted by created_at DESC, `total_count` ≥ number of orders placed.

8.2 Pagination bounds
- `per_page=100` → 422 (capped at 50).
- `page=0` → 422.

8.3 Next page
- `page=2&per_page=2` returns next slice. Merging pages equals total_count items
  with no duplicates.

8.4 Foreign orders excluded
- As $CUST2_TOKEN list /api/v1/orders → does NOT contain $ORDER_ID (belongs to CUST).

8.5 GET detail includes snapshot immutability
- GET /api/v1/orders/$ORDER_ID as owner → returns items with `menu_item_name_ru`,
  `unit_price`, `modifiers_snapshot` that reflect the state AT checkout time.
- Now admin-edit Капучино M price to something extreme, then GET the order again
  → snapshot still shows the old price (INV-014). Revert the admin edit.

8.6 Admin JWT can't access customer history endpoints
curl -s -o /dev/null -w '%{http_code}\n' \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8240/api/v1/orders
- Expect 403 (ROUTE_MATRIX — customer-only).

---
Block 9 — Repeat order

9.1 Happy path
- Pick a completed order with multiple lines. POST /api/v1/orders/$ORDER_ID/repeat
  → 200, `added_to_cart=N`, `skipped=[]`.
- GET /api/v1/cart → cart populated with same items at CURRENT prices.

9.2 Stop-listed item skipped
- Admin: set one item on the source order to available=false. Repeat →
  that line missing from cart, `skipped` contains it with reason referencing "недоступен".
- Re-enable item.

9.3 Archived item skipped
- SQL: UPDATE menu_items SET archived=true WHERE id='<x>';
- Repeat → skipped with reason "больше не в меню".
- Revert archived=false.

9.4 Missing size skipped (whole line)
- Delete a size_option referenced by the order (admin UI or SQL). Repeat →
  the entire line is skipped, reason references size.

9.5 Missing modifier attached, item still added
- Delete a modifier referenced by the order. Repeat → item is added but without
  that modifier, `skipped` lists the modifier-level reason.

9.6 All lines unavailable
- Source order with single line → stop-list it. Repeat → 422
  "Ни одна позиция из этого заказа сейчас недоступна". Cart remains empty.

9.7 Foreign order
- As $CUST2_TOKEN POST repeat on CUST's order → 404.

---
Block 10 — Cross-cutting

10.1 Auth required on order routes
for path in \
  /api/v1/orders \
  /api/v1/orders/any-uuid \
  /api/v1/orders/any-uuid/cancel; do
  curl -s -o /dev/null -w "$path -> %{http_code}\n" "http://localhost:8240$path"
done
- Expect 401 for each (no token).

10.2 Staff route matrix
- Customer token on PATCH .../status → 403.
- Staff token on GET /api/v1/orders (customer history) → 403.

10.3 INV-013 no-leak: foreign order detail
- As $CUST2_TOKEN GET /api/v1/orders/$ORDER_ID → 404 (NOT 403, so existence is
  not disclosed).

10.4 Accept-Language in order responses
curl -s -H "Authorization: Bearer $CUST_TOKEN" -H 'Accept-Language: en' \
  http://localhost:8240/api/v1/orders/$ORDER_ID | jq '.items[0].menu_item_name_en, .items[0].menu_item_name_ru'
- Both fields present in snapshot regardless of header (snapshot stores both).
  Any display-level localization is client-side.

10.5 Idempotency on double-submit
- Place an order and IMMEDIATELY re-POST the same body (while cart still present
  in Redis before payment webhook). Should yield a second order (current design
  does not dedupe on the client — document the observed behavior).
- After PAID and cart auto-delete, re-POST same body → 400 "Корзина пуста".

10.6 Latency smoke
- time curl -s -X POST .../orders ... with a small cart.
- SLA (PDD §4.1): ≤500ms p95 on create. A single dev box usually reports ~100–300ms;
  anything >1s should be investigated.

10.7 DB invariants after a full happy path
Pick one order that went CREATED → PAID → PREPARING → READY → COMPLETED.
Run:
docker compose exec db psql -U postgres -d aura -c "
SELECT o.status, o.total, p.status AS pay_status,
       (SELECT sum(amount) FROM loyalty_transactions WHERE order_id=o.id) AS net_points,
       (SELECT count(*) FROM order_items WHERE order_id=o.id) AS n_items,
       (SELECT count(*) FROM notifications WHERE order_id=o.id) AS n_notifs
FROM orders o JOIN payments p ON p.order_id=o.id WHERE o.id='$ORDER_ID';
"
- `status=COMPLETED`, `pay_status=SUCCEEDED`,
- `net_points` ≥ 0 (RESERVATION cancelled out by REDEMPTION, plus ACCRUAL).
- `n_items` matches the order,
- `n_notifs` ≥ number of status transitions that emitted notifications.
