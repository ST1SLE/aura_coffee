# Phase 4 — Manual UI clickthrough (Delivery)

Goal: exercise the delivery feature end-to-end — saved addresses, delivery checkout, the courier panel, and the assignment state machine — through Chrome + a few curl calls. Backend invariants (state machine transitions, optimistic lock, radius, geocode cache) are covered by the automated suite; Section 5 here is only the thin smoke-test over the exposed endpoints.

## Pre-flight

1. Bring the stack up from the repo root:

   ```
   ./scripts/up.sh
   ```

   Wait for the banner line `Migrations: applied ✓`. If it says `FAILED`, stop and run `docker compose logs db-migrate`.

2. Export the NGINX port from `.env` (per-worktree values differ — `8240`/`8250`/`8260`):

   ```
   export BASE=http://localhost:$(grep '^NGINX_PORT=' .env | cut -d= -f2)
   echo "$BASE"    # e.g. http://localhost:8260
   ```

   URLs:
   - Customer SPA: `$BASE/`
   - Admin SPA:    `$BASE/admin/`

3. Three log tails, each in its own terminal, kept running throughout the session:

   ```
   docker compose logs -f sms-worker        # OTP task delivery (codes are PII → не логируются)
   docker compose logs -f core-api          # HTTP errors, order transitions
   docker compose logs -f payment-worker    # fake YooKassa auto-drive → PAID
   ```

4. Payment is faked. `.env.example` sets `YUKASSA_BACKEND=fake` and `YUKASSA_FAKE_OUTCOME=success`. Checkout now enqueues `payment_worker.tasks.create_payment` on the `payments` queue; the fake client fires `yukassa_fake_callback` with `countdown=1`, which POSTs `payment.succeeded` to `payment-webhook`. End-to-end: `CREATED → PAID` in ~2 s. If you see `payment-worker` logs with `ModuleNotFoundError: psycopg2` — rebuild the image (`docker compose build payment-worker && docker compose up -d payment-worker`); the driver was added recently.

5. **Yandex Maps API key.** `.env.example` has `YANDEX_MAPS_API_KEY=` (empty by default). With an empty key, `/api/v1/maps/suggest` and `/api/v1/maps/geocode` both return `HTTP 503 {"reason": "maps_unavailable"}` — this is the fallback path Section 1.2 tests. If you want to also test the happy path, put a real key in `.env` and `docker compose up -d core-api`.

6. **Seed manual-QA data** (idempotent — can re-run any time):

   ```
   docker compose exec core-api python -m database.seeds.phase4_manual_test
   # phase4_manual_test seed applied
   ```

   Inserts: `shop_settings` (needed for Haversine radius check), staff `courier/courier123` + `barista/barista123`, one menu category + "Cappuccino (QA)" drink + size option, customer `+79991234567` with one default delivery address (Красная площадь, inside 5-км radius).

7. Get customer + admin + courier + barista JWTs (for Section 5 curl blocks):

   ```
   # admin (pre-seeded by database/seeds/initial_admin.py)
   ADMIN_TOKEN=$(curl -s -X POST $BASE/api/v1/staff/auth/login \
     -H 'Content-Type: application/json' \
     -d '{"login":"admin","password":"admin123"}' | jq -r .access_token)

   # courier (from phase4_manual_test seed)
   COURIER_TOKEN=$(curl -s -X POST $BASE/api/v1/staff/auth/login \
     -H 'Content-Type: application/json' \
     -d '{"login":"courier","password":"courier123"}' | jq -r .access_token)

   # barista (from phase4_manual_test seed)
   BARISTA_TOKEN=$(curl -s -X POST $BASE/api/v1/staff/auth/login \
     -H 'Content-Type: application/json' \
     -d '{"login":"barista","password":"barista123"}' | jq -r .access_token)

   # customer — request OTP, then read code directly from Redis (the real SMS
   # payload is PII-scrubbed in sms-worker logs). phone_hash is sha256 of the
   # full phone string with leading +.
   PHONE=+79991234567
   PH=$(echo -n "$PHONE" | sha256sum | cut -d' ' -f1)
   curl -s -X POST $BASE/api/v1/auth/send-code \
     -H 'Content-Type: application/json' -d "{\"phone\":\"$PHONE\"}"
   sleep 1
   OTP=$(docker compose exec -T redis redis-cli GET "otp:$PH" | jq -r .code)
   CUST_TOKEN=$(curl -s -X POST $BASE/api/v1/auth/verify-code \
     -H 'Content-Type: application/json' \
     -d "{\"phone\":\"$PHONE\",\"code\":\"$OTP\"}" | jq -r .access_token)
   ```

   *If `/send-code` returns `{"detail":"Too many requests …"}`, you hit the min/hour/day rate-limiter. Clear it:*
   ```
   docker compose exec -T redis redis-cli DEL "sms_rate:$PH:min" "sms_rate:$PH:hour" "sms_rate:$PH:day"
   ```

8. Reset between runs (wipes DB, Redis, volumes — re-run the seed from step 6 after):

   ```
   ./scripts/down.sh && ./scripts/up.sh
   docker compose exec core-api python -m database.seeds.phase4_manual_test
   ```

---

## Section 1 — Customer: Saved addresses (`/profile/addresses`)

Open the Customer SPA. Log in with phone `+79991234567` (from the seed). Grab the OTP code from Redis — see pre-flight step 7, or the one-liner in the Appendix.

### 1.1 Empty state

1. Navigate to `/profile` → click the link to `/profile/addresses` (or enter the URL directly).
2. Expected: page heading, empty list, a single "Добавить адрес" / "Add address" button.

### 1.2 Add address — Yandex suggest unavailable (default dev stack)

With `YANDEX_MAPS_API_KEY` empty, the autocomplete dropdown is degraded to a plain text input and the geocode call happens only on save.

1. Click "Add address". The form opens with fields: label, address (autocomplete), apartment, entrance, floor, comment.
2. Type any address string, e.g. `ул. Ленина, 1`. Expected: no dropdown appears; DevTools → Network shows `/api/v1/maps/suggest?text=...` returning `HTTP 503 {"reason":"maps_unavailable"}`.
3. Fill label = `Дом`, leave other fields empty, click "Сохранить" / "Save".
4. With an empty API key, the geocode call also 503s. Expected: red error below the form (`errors.delivery.generic` — a localized "Адреса недоступны" / "Address service is unavailable"). The address is **not** saved. This is the documented fallback; for the happy path use 1.3 with a real key.

### 1.3 Add address — happy path (real API key)

*Skip this block if you did not set a real `YANDEX_MAPS_API_KEY`.*

1. In the form, start typing `Москва, Тверская`. After ~300 ms, a dropdown appears with Yandex suggestions (`GET /api/v1/maps/suggest`).
2. Click a suggestion. The text field fills with the canonical address; `lat`/`lon` are captured in form state (not visible to the user).
3. Fill apartment = `12`, entrance = `2`, floor = `3`, comment = `домофон 123`, label = `Офис`.
4. Click "Save". Expected: form closes, the new address appears in the list with label, full text, and apartment/entrance/floor on a secondary line.

### 1.4 Out-of-radius error

1. In the form, pick a suggestion far outside the delivery zone (e.g. another city).
2. Click "Save". Expected: `POST /api/v1/profile/addresses` returns `HTTP 422` with a detail string about radius; UI shows the red localized "Адрес вне зоны доставки" / "Address outside delivery area" error and keeps the form open.

### 1.5 Edit

1. Click the edit (pencil) icon on an existing row. Expected: the form opens pre-filled with the current values.
2. Change the comment, click "Save". Expected: form closes, the row's comment is updated in place (no full page reload).

### 1.6 Make primary

1. Create a second address (any other address). Expected: the first one keeps its blue "Основной" / "Primary" badge; the second has no badge.
2. On the second row, click "Сделать основным" / "Make Primary". Expected: the badge moves to the second row; the first one loses it. Refresh — persists.

### 1.7 Delete

1. On any non-primary row, click the trash icon. Expected: browser confirm dialog.
2. Confirm. Expected: `DELETE /api/v1/profile/addresses/{id}` returns `204`; the row disappears immediately.
3. Cancel the dialog on another row. Expected: nothing happens, row stays.

### 1.8 Session expiry

1. In DevTools, delete `accessToken` from `localStorage`, then click "Add address".
2. Expected: the request fails with `401`; the app redirects back to `/login` (does not silently hang).

---

## Section 2 — Customer: Checkout with delivery (`/checkout`)

Phase 4 wires up the `/checkout` page that was a stub in Phase 3. Before starting: make sure the cart is non-empty. UI way: go to `/menu`, add one item. API way (useful when the menu UI is broken or you want a reproducible cart):

```
# menu_item_id=1 / size_option_id=1 come from the phase4_manual_test seed
curl -s -X POST $BASE/api/v1/cart/items \
  -H "Authorization: Bearer $CUST_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"menu_item_id":1,"size_option_id":1,"quantity":1}' | jq '.items | length'
# Expect: ≥ 1
```

### 2.1 Pickup path (smoke)

1. Navigate to `/checkout`. Expected: order-type radio with "Самовывоз" / "Pickup" and "Доставка" / "Delivery", Pickup selected by default.
2. Click "Оформить" / "Submit". Expected:
   - `POST /api/v1/orders` returns `201`; the response body includes `id` and `type: "pickup"`.
   - Browser navigates to `/orders/{id}` → lands on `NotFoundPage` (the customer order detail route is still a stub — see Section 6). Hit back and check `core-api` log for a matching `order.created` line.

### 2.2 Delivery with saved address

Requires at least one saved address from Section 1 (use 1.3 or create one via API if maps are offline — Section 5.2).

1. On `/checkout`, select "Доставка". Expected: the delivery panel opens; the "Сохранённый адрес" / "Saved address" radio is selected by default and shows a list of your saved addresses.
2. Pick one address, click "Submit". Expected: the request body is `{"type":"delivery","delivery_address_id":"<uuid>"}`; response `201`; navigation to `/orders/{id}` (stub).
3. Check `core-api` log — you should see the order get created, then within ~2 s transition to `PAID` driven by `payment-worker` fake.

### 2.3 Delivery with new inline address + "Save for future"

*Happy path requires a real `YANDEX_MAPS_API_KEY`.*

1. On `/checkout` → Delivery → pick the "Новый адрес" / "New address" radio. Expected: the AddressAutocomplete + apartment/entrance/floor/comment block appears, plus a "Сохранить на будущее" / "Save for future" checkbox.
2. Type a valid address, pick a suggestion, tick "Save for future", click "Submit". Expected:
   - `POST /api/v1/orders` body contains `delivery_address: {text, lat, lon, apartment, …}` (no `delivery_address_id`).
   - After order success, a second call `POST /api/v1/profile/addresses` fires — it is best-effort, so an error there logs a console warning but does not block the order.
3. Navigate to `/profile/addresses`. Expected: the newly-saved address is in the list.

### 2.4 Validation & error paths

- Submit with Delivery selected and no address chosen. Expected: submit button stays disabled (or the form shows a localized required-field error).
- With maps offline, submit an inline new address. Expected: geocode 503 → red "Адреса недоступны" / "Address service unavailable", order is **not** created.
- Pick a saved address that is out of radius (edit one in DB, or use 1.4 to create one if you got 422 to succeed by lowering the shop radius). Expected: `POST /api/v1/orders` returns `422` with the radius reason; UI shows the same localized radius error; no order.

---

## Section 3 — End-to-end: walk an order to a courier

There is no admin UI for order status transitions in Phase 4 — use curl. `core-api` log in the background is your ground truth.

### 3.1 Prepare

1. From Section 2.2 (or via API: see Section 2 prereq for cart seed, then `POST $BASE/api/v1/orders`), create a delivery order and note its `id`.
2. Poll status — fake YuKassa flips it to `paid` in ~2 s:
   ```
   for i in 1 2 3 4 5 6 7 8; do
     STATUS=$(curl -s $BASE/api/v1/orders/$ORDER_ID \
       -H "Authorization: Bearer $CUST_TOKEN" | jq -r .status)
     echo "t=${i}s status=$STATUS"
     [ "$STATUS" = "paid" ] && break
     sleep 1
   done
   # Expect: paid within ~3s
   ```

### 3.2 PAID → PREPARING (triggers assignment creation)

`PATCH /orders/{id}/status` allows `{BARISTA, COURIER, ADMIN}` — admin works here.

```
curl -s -X PATCH $BASE/api/v1/orders/$ORDER_ID/status \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"new_status":"preparing"}' | jq .status
# Expect: "preparing"
```

Expected side effect: a `DeliveryAssignment` row is created with `status=AWAITING_COURIER`. Confirm via the courier endpoint:

```
curl -s $BASE/api/v1/courier/assignments/available \
  -H "Authorization: Bearer $COURIER_TOKEN" | jq '.[] | .order_id'
# Expect: $ORDER_ID is in the list
```

### 3.3 PREPARING → READY

```
curl -s -X PATCH $BASE/api/v1/orders/$ORDER_ID/status \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"new_status":"ready"}' | jq .status
# Expect: "ready"
```

### 3.4 Courier: Take → Pickup → Deliver

Open the admin SPA at `/admin/login` and log in as `courier` / `courier123`. You should land directly on `/admin/courier` (the courier bypasses the admin layout — Section 4).

**Available tab.**
1. The order from 3.3 is visible as a card with time, total, and address. Refetches every 5 s (watch DevTools → Network; you'll see `/api/v1/courier/assignments/available` fire on a 5 s cadence).
2. Click "Взять" / "Take" on the card. Expected: the card moves to the Mine tab; `POST /api/v1/courier/assignments/{id}/take` returns `{"status":"courier_assigned"}`.

**Race test.** Before clicking Take, also call `take` from a second tab (via curl with the same `$COURIER_TOKEN`, or open an incognito window and Take a different pending assignment from there — the server-side optimistic lock is the point).

```
# simulate a second taker racing for the same assignment
curl -s -X POST $BASE/api/v1/courier/assignments/$ASSIGNMENT_ID/take \
  -H "Authorization: Bearer $COURIER_TOKEN"
# Expect the second call: HTTP 409 {"detail":{"reason":"already_taken"}}
```

In the UI, a second tab that tried to Take after you: expect a toast "Заказ уже взят другим курьером" / "Already taken" and the Available list refetches.

**Mine tab.**
3. Switch to Mine tab. The card now shows a "Забрал" / "Pickup" button (status COURIER_ASSIGNED).
4. Click "Pickup". Expected: `POST …/pickup` returns `{"status":"picked_up"}`; the button on the card changes to "Доставлен" / "Deliver"; in the background the Order also transitions `READY → IN_DELIVERY` (verify with the GET order curl from 3.1).
5. Click "Deliver". Expected: `POST …/deliver` returns `{"status":"delivered"}`; the order becomes `COMPLETED`; loyalty is accrued (confirm user balance changed via whatever profile/loyalty API you use, or in DB).

### 3.5 Forbidden transitions (spot check)

```
# pickup before take — wrong starting state
curl -s -o /dev/null -w '%{http_code}\n' \
  -X POST $BASE/api/v1/courier/assignments/$FRESH_ASSIGN_ID/pickup \
  -H "Authorization: Bearer $COURIER_TOKEN"
# Expect: 409
```

### 3.6 Admin cancel while assigned

1. Create another delivery order, walk it through 3.2 so an assignment exists in `AWAITING_COURIER`.
2. Cancel via admin:
   ```
   curl -s -X POST $BASE/api/v1/orders/$ORDER2_ID/cancel \
     -H "Authorization: Bearer $ADMIN_TOKEN" \
     -H 'Content-Type: application/json' \
     -d '{"reason":"admin_decision"}'
   # Expect: HTTP 200, order.status == "cancelled"
   ```
3. Refetch available assignments — the cancelled order should have disappeared (assignment moved to `CANCELLED`).

---

## Section 4 — Admin: Courier panel login & role isolation

All in the Admin SPA (`/admin/`).

### 4.1 Courier login → direct to `/courier`

1. Log in as `courier` / `courier123`. Expected: you land on `/admin/courier` immediately; you do NOT pass through `/admin/` (dashboard) and the sidebar with Menu/Orders/Users is not rendered — the CourierShell is a stripped-down layout.
2. Manually navigate to `/admin/menu`. Expected: ProtectedRoute rejects (courier is not in `['admin','barista']`) → redirect back to `/admin/courier` or `/admin/login`.

### 4.2 Admin can also see `/courier`

1. Log out, log in as `admin` / `admin123`. You land on `/admin/` (dashboard stub).
2. Navigate to `/admin/courier` directly. Expected: the page renders (admin is allowed on the courier route too, useful for on-call debugging).

### 4.3 Barista cannot hit courier API

`BARISTA_TOKEN` comes from pre-flight step 7 (seed already has barista/barista123).

```
curl -s -o /dev/null -w '%{http_code}\n' \
  $BASE/api/v1/courier/assignments/available \
  -H "Authorization: Bearer $BARISTA_TOKEN"
# Expect: 403
```

---

## Section 5 — API-only checks

### 5.1 Maps proxy

```
# Suggest with empty YANDEX_MAPS_API_KEY (default dev)
curl -s -o /dev/null -w '%{http_code}\n' \
  "$BASE/api/v1/maps/suggest?text=Тверская&lang=ru_RU" \
  -H "Authorization: Bearer $CUST_TOKEN"
# Expect: 503

# Geocode low precision (e.g. bare city name, with real key)
curl -s -o /dev/null -w '%{http_code}\n' \
  "$BASE/api/v1/maps/geocode?text=Москва" \
  -H "Authorization: Bearer $CUST_TOKEN"
# Expect (with real key): 422 {"reason":"low_precision"}
#        (with empty key): 503

# Geocode cache hit — call the same exact text twice, second call should be instant
time curl -s "$BASE/api/v1/maps/geocode?text=Москва,%20Тверская,%201" \
  -H "Authorization: Bearer $CUST_TOKEN" > /dev/null
time curl -s "$BASE/api/v1/maps/geocode?text=Москва,%20Тверская,%201" \
  -H "Authorization: Bearer $CUST_TOKEN" > /dev/null
# Expect: second call noticeably faster; only one hit in core-api log upstream to Yandex
```

### 5.2 Delivery addresses CRUD

The `DeliveryAddressCreate` schema requires `label` (min_length=1) AND `address_text` — NOT the `text` field the customer SPA sends (see §6 "Known gaps"). List returns a bare JSON array, not `{"items":[…]}`.

```
# Create
ADDR_ID=$(curl -s -X POST $BASE/api/v1/profile/addresses \
  -H "Authorization: Bearer $CUST_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"label":"Дом (API)","address_text":"ул. Ленина, 1","lat":55.751244,"lon":37.618423}' \
  | jq -r .id)
echo "addr=$ADDR_ID"
# Expect: non-empty UUID. If you get 422 with "Field required address_text" — you
# sent `text` instead of `address_text`.

# List (bare array, not wrapped)
curl -s $BASE/api/v1/profile/addresses \
  -H "Authorization: Bearer $CUST_TOKEN" | jq 'length'
# Expect: ≥ 2 (one from the seed + the one you just created)

# Update
curl -s -X PATCH $BASE/api/v1/profile/addresses/$ADDR_ID \
  -H "Authorization: Bearer $CUST_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"comment":"код 1234"}' | jq .comment
# Expect: "код 1234"

# Make primary — use PATCH with is_default=true, not a nonexistent /set-primary route
curl -s -X PATCH $BASE/api/v1/profile/addresses/$ADDR_ID \
  -H "Authorization: Bearer $CUST_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"is_default":true}' | jq .is_default
# Expect: true; the previously-default address flips to false

# Delete
curl -s -o /dev/null -w '%{http_code}\n' \
  -X DELETE $BASE/api/v1/profile/addresses/$ADDR_ID \
  -H "Authorization: Bearer $CUST_TOKEN"
# Expect: 204
```

### 5.3 Auth on delivery routes

```
# No JWT
curl -s -o /dev/null -w '%{http_code}\n' \
  $BASE/api/v1/profile/addresses
# Expect: 401

curl -s -o /dev/null -w '%{http_code}\n' \
  $BASE/api/v1/courier/assignments/available
# Expect: 401

# Customer on courier route
curl -s -o /dev/null -w '%{http_code}\n' \
  $BASE/api/v1/courier/assignments/available \
  -H "Authorization: Bearer $CUST_TOKEN"
# Expect: 403

# Courier on customer addresses route
curl -s -o /dev/null -w '%{http_code}\n' \
  $BASE/api/v1/profile/addresses \
  -H "Authorization: Bearer $COURIER_TOKEN"
# Expect: 403
```

---

## Section 6 — Known gaps (intentionally out of scope here)

### Still stubs after Phase 4 — don't click through

- **Customer order detail `/orders/{id}`** — no route is registered; `CheckoutPage` navigates there on submit and you land on `NotFoundPage`. Expected until the order-history feature ships.
- **Customer order history `/orders`** — 12-line stub (`web/customer/src/pages/OrdersPage.tsx`).
- **Admin orders `/admin/orders`** — 12-line stub. There is no UI for PAID → PREPARING → READY; use `PATCH /api/v1/orders/{id}/status` per Section 3.
- **Admin users / promos / settings / dashboard** — still 12-line stubs from Phase 3.
- **Barista feed** — the courier panel is the first 5 s realtime feed; the barista equivalent has no UI yet.
- **Staff account management UI** — there is no page to create couriers/baristas; the `phase4_manual_test` seed (pre-flight step 6) is the only creation path.

### Customer SPA ↔ core-api schema drift (confirmed bugs)

These surface in UI-driven flows (Section 1) but not in the §5 curl blocks, which use the correct payloads directly:

- `web/customer/src/api/addresses.ts` POSTs `{"text": "…"}` — server expects `{"address_text": "…", "label": "…"}`. Result: UI returns `422 Field required` and the address silently isn't created. Section 1.3 "happy path" is therefore broken even with a real Yandex key until the frontend is fixed.
- Same file parses the list response as `{"items": [...]}` — server returns a bare array. Result: the addresses page shows empty list even when addresses exist.
- Same file POSTs `/api/v1/profile/addresses/{id}/set-primary` to mark an address default — there is no such route. The correct flow is `PATCH /api/v1/profile/addresses/{id}` with `{"is_default": true}`. Result: Section 1.6 "Make primary" always fails with 404/405 in the browser.

Track these as frontend fixes; they do NOT indicate a backend regression.

---

## Appendix — Logs cheatsheet

```
docker compose logs -f sms-worker         # OTP task delivery only — codes go to Redis (PII)
docker compose logs -f core-api           # HTTP errors, order transitions, RBAC rejects
docker compose logs -f payment-worker     # fake YooKassa auto-drive to PAID
docker compose logs -f payment-webhook    # YooKassa webhook receipt (payment.succeeded)
docker compose logs -f nginx              # routing issues (404s, bad upstream)
```

To pull a live OTP code for a phone:
```
PH=$(echo -n "+79991234567" | sha256sum | cut -d' ' -f1)
docker compose exec -T redis redis-cli GET "otp:$PH" | jq -r .code
```

Common failure signatures:

- **`/api/v1/maps/suggest` or `/geocode` → 503 consistently** → `YANDEX_MAPS_API_KEY` empty or invalid. Either set a real key in `.env` and `docker compose up -d core-api`, or accept Sections 1.2 / 2.4 fallback-path testing only.
- **Courier login returns 401** → seed wasn't applied. Run `docker compose exec core-api python -m database.seeds.phase4_manual_test`.
- **Order stuck in `created` forever** → usually one of:
  1. `payment-worker` logs `ModuleNotFoundError: psycopg2` → rebuild the image (the driver was added recently).
  2. `payment-worker` logs `Received unregistered task of type 'yukassa_fake_callback'` → restart payment-worker (`main.py` now eagerly imports `yukassa_fake`; ensure you are on a fresh image).
  3. Task ended up on the `celery` queue instead of `payments` → check `redis-cli LRANGE celery 0 -1`; a message there means `checkout.enqueue_payment_task` is missing `queue="payments"`.
- **`/send-code` returns 429 "Too many requests"** → SMS rate-limiter (1/min, 5/hour, 10/day). Clear with `redis-cli DEL sms_rate:<phone_hash>:{min,hour,day}` (snippet in pre-flight step 7).
- **"Take" on courier card returns 409 the first time** → somebody (or a leftover second tab) already took it. Refresh Available.
- **Admin orders page shows a blank/stub despite orders existing** → expected, see Section 6.
