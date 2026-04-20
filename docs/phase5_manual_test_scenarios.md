# Phase 5 — Manual UI clickthrough (Loyalty & Promocodes)

Goal: exercise the two customer/admin surfaces that Phase 5 added — admin promocode CRUD and customer loyalty balance/history — plus the hidden backend bits (atomic `current_uses` increment, promocode-validator contract, phase-5.5 role-filtered admin sidebar). Backend invariants (the atomic-race fix itself, state-machine transitions, RBAC matrix) are covered by the automated suite; Section 5 here is only a thin smoke-test over the exposed endpoints.

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
   docker compose logs -f core-api          # HTTP errors, order transitions, promocode 409s
   docker compose logs -f payment-worker    # fake YooKassa auto-drive → PAID
   ```

4. Payment is faked. `.env.example` sets `YUKASSA_BACKEND=fake` and `YUKASSA_FAKE_OUTCOME=success`. Checkout enqueues `payment_worker.tasks.create_payment` on the `payments` queue; the fake client fires `yukassa_fake_callback` with `countdown=1`, which POSTs `payment.succeeded` to `payment-webhook`. End-to-end: `CREATED → PAID` in ~2 s.

5. **Yandex Maps API key** (carried over from Phase 4 — Phase 5 does not touch maps). `.env.example` has `YANDEX_MAPS_API_KEY=` empty by default; delivery flows that need a geocode will 503 until you set a real key. Phase 5 does not regress or depend on this — the loyalty/promocode work is independent of delivery. If you want to drive a full delivery-to-COMPLETED order for Section 3 accrual testing, set a real key, or stick to `pickup`.

6. **Seed manual-QA data** (same phase-4 seed — there is no dedicated phase-5 seed; idempotent, can re-run any time):

   ```
   docker compose exec core-api python -m database.seeds.phase4_manual_test
   # phase4_manual_test seed applied
   ```

   Inserts: `shop_settings`, staff `courier/courier123` + `barista/barista123`, one menu category + "Cappuccino (QA)" drink (600 ₽) + size option, customer `+79991234567` with a `loyalty_accounts` row (balance=0) and one default delivery address. **No promocodes are seeded** — you create them in Section 1 (via UI) or Section 5.1 (via curl).

7. Get the four JWTs. `admin` is pre-seeded by `database/seeds/initial_admin.py`; `courier` and `barista` come from the phase-4 seed; `customer` needs the OTP dance:

   ```
   ADMIN_TOKEN=$(curl -s -X POST $BASE/api/v1/staff/auth/login \
     -H 'Content-Type: application/json' \
     -d '{"login":"admin","password":"admin123"}' | jq -r .access_token)

   COURIER_TOKEN=$(curl -s -X POST $BASE/api/v1/staff/auth/login \
     -H 'Content-Type: application/json' \
     -d '{"login":"courier","password":"courier123"}' | jq -r .access_token)

   BARISTA_TOKEN=$(curl -s -X POST $BASE/api/v1/staff/auth/login \
     -H 'Content-Type: application/json' \
     -d '{"login":"barista","password":"barista123"}' | jq -r .access_token)

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

   *If `/send-code` returns `{"detail":"Too many requests …"}`, clear the rate-limiter:*
   ```
   docker compose exec -T redis redis-cli DEL "sms_rate:$PH:min" "sms_rate:$PH:hour" "sms_rate:$PH:day"
   ```

8. Reset between runs (wipes DB, Redis, volumes — re-run the seed from step 6 after):

   ```
   ./scripts/down.sh && ./scripts/up.sh
   docker compose exec core-api python -m database.seeds.phase4_manual_test
   ```

---

## Section 1 — Admin: Promocodes CRUD (`/admin/promos`)

All in the Admin SPA. Log in as `admin` / `admin123`; you land on `/admin/` (dashboard stub). Sidebar should show six links — Dashboard, Orders, Menu, Users, Promos, Settings (see Section 4 for the role-filter). Click "Promos".

### 1.1 Empty state

1. On first open (no promocodes exist yet), expected: heading, state-filter tabs (All / Active / Inactive / Expired / Exhausted) with All selected, a search input, a "Создать" / "Create" button, empty table with a localized empty-state line.
2. DevTools → Network: `GET /api/v1/admin/promocodes?state=all&page=1&per_page=20` returns `{"items":[], "total_count":0, "page":1, "per_page":20}`.

### 1.2 Create — happy path (percent)

1. Click "Create". A dialog opens with fields: code, discount type (radio: percent / fixed), discount value, min order amount, valid from, valid until, max uses, max uses per user.
2. Fill:
   - code = `qa10` (lowercase on purpose — the server UPPER()s it)
   - discount type = percent
   - discount value = `10`
   - min order amount = leave empty (server defaults to 0)
   - valid until = tomorrow, same time
   - max uses = `5`
   - max uses per user = `1`
3. Click "Create". Expected: dialog closes, table refetches, a new row appears with `code = QA10` (canonical upper-case), a grey/default state chip (INACTIVE — freshly-created promos start inactive per §6.6), `10%`, valid-until timestamp, `0 / 5`.

### 1.3 Create — validation errors

All these keep the dialog open and show a field-level error or a top-of-dialog error (422 from server).

- **Bad pattern.** code = `qa 10` (space) → localized pattern error. Server returns 422 from the pydantic validator before hitting the DB.
- **Percent > 100.** discount type = percent, value = `150` → "percent discount_value must be <= 100".
- **Fixed ≤ 0.** discount type = fixed, value = `0` → 422 from `_check_discount_bounds`.
- **Dates inverted.** valid_from = tomorrow, valid_until = today → "valid_from must be strictly before valid_until".
- **per_user > max_uses.** max_uses = `3`, max_uses_per_user = `5` → "max_uses_per_user must be <= max_uses".
- **Duplicate code.** Submit `QA10` again (matches 1.2). Expected: `HTTP 409 {"detail":"promocode_code_conflict"}`; the UI shows the localized `pages.promos.errors.duplicate_code` line.

### 1.4 Create — fixed amount (rubles ↔ kopecks)

1. Open Create. Fill code = `SAVE100`, type = fixed, discount value = `100` (rubles in UI), min order = `500` (rubles).
2. Submit. Check DevTools → Network request body: `discount_value` and `min_order_amount` are **10000** and **50000** respectively (kopecks). The UI converts on save. The row's "discount" column renders "100 ₽".

### 1.5 State-filter tabs & computed `state`

Computed server-side on every list/detail response (`services/admin_promocodes.py::compute_state`). The UI displays the value in a chip, does not recompute it.

1. Click the "Active" tab → request is `?state=active`. Expected: QA10 and SAVE100 should *not* appear (both still INACTIVE). Table is empty.
2. Click "Inactive" tab → both rows appear with an "INACTIVE" chip.
3. To observe the "Expired" state without waiting for the clock: create a throwaway promo with valid_until = *1 minute from now*, wait, refresh, switch to "Expired" tab. Its chip is red.
4. To observe "Exhausted": create a promo with max_uses = 1, walk one order through with it applied (see Section 3). After the order's `current_uses` goes to 1 (equal to max_uses), the "Exhausted" tab will list it.
5. "All" tab returns everything, sorted `created_at DESC`.

### 1.6 Search by code

1. In the search input, type `qa`. After ~300 ms a request fires: `GET /api/v1/admin/promocodes?state=all&code=qa&page=1&...`.
2. Expected: only rows whose code **starts** with `QA` (case-insensitive) match (so QA10 yes, SAVE100 no).
3. Type-and-delete quickly → only one debounced request goes out.

### 1.7 Edit — `current_uses = 0` (all fields editable)

1. Click a row with `0 / 5` uses. The dialog opens in edit-mode pre-filled. All inputs are enabled.
2. Change max_uses = `10`, click "Save". Request: `PATCH /api/v1/admin/promocodes/{id}` with just `{"max_uses":10}`. Row updates to `0 / 10`.
3. Change discount value = `15`. Save. Row still INACTIVE, new value.

### 1.8 Activate / Deactivate lifecycle

Activate/deactivate are separate buttons in the edit dialog — not part of PATCH.

1. Open QA10 edit dialog (still INACTIVE). Click "Активировать" / "Activate". Request: `POST /api/v1/admin/promocodes/{id}/activate`. Expected: `is_active=true`, state chip flips to green "ACTIVE".
2. Re-open the same row. The button now reads "Деактивировать" / "Deactivate". Click it → state chip flips to grey "INACTIVE".
3. **Activate without `valid_until`.** Create a new promo leaving valid_until empty. Re-open its dialog, click Activate. Expected: `HTTP 422 {"detail":"valid_until required"}`; UI shows `pages.promos.errors.activate_requires_valid_until`. Fix: edit the promo, set valid_until, save, then Activate.
4. **Activate an EXPIRED promo.** Use the throwaway from 1.5 step 3. Click Activate → `HTTP 409 {"detail":"promocode expired"}`; UI: `activate_expired`.
5. **Deactivate an EXPIRED promo.** Same promo — click Deactivate → `HTTP 409 "promocode expired"`. Deactivation of an already-dead code is refused.

### 1.9 Edit — `current_uses > 0` (locked fields)

After a promo has been used at least once (Section 3 walks QA10 to `current_uses=1`), `code`, `discount_type`, `discount_value` are frozen. Other fields remain editable.

1. Open edit for such a promo. Expected: those three inputs are **disabled**, with a tooltip from `pages.promos.locked_hint` ("Поле нельзя изменить после первого использования").
2. Bypass the UI with a raw PATCH:
   ```
   curl -s -X PATCH $BASE/api/v1/admin/promocodes/$PROMO_ID \
     -H "Authorization: Bearer $ADMIN_TOKEN" \
     -H 'Content-Type: application/json' \
     -d '{"discount_value":50}'
   ```
   Expected: `HTTP 422` with a detail body containing `[{"type":"field_locked_after_use","field":"discount_value"}]`. The 422 is the server's independent guard — UI disable is only a UX hint.
3. Confirm `valid_until`, `max_uses`, `max_uses_per_user`, `min_order_amount`, `is_active` still patch successfully on the same used promo.

### 1.10 RBAC isolation (UI)

1. Log out; log in as `barista` / `barista123`. Expected: the sidebar shows only two links (Orders, Menu) — no Promos entry at all. Manually navigate to `/admin/promos`. ProtectedRoute rejects → redirect to `/admin/login` or back to an allowed page.
2. Same for `courier` (they bypass Layout entirely — see Section 4).
3. API-level checks are in Section 5.5.

---

## Section 2 — Customer: Loyalty (`/profile` + `/profile/loyalty`)

All in the Customer SPA. Log in as `+79991234567` (OTP from pre-flight step 7). Fresh state after seed: `loyalty_accounts.balance = 0`, no transactions.

### 2.1 Profile card — zero balance

1. Navigate to `/profile`. Expected: the profile page shows (among phone/language/logout) a new "Мои баллы" / "My points" card with a big `0` and a "История" / "View history" link.
2. DevTools → Network: `GET /api/v1/profile/loyalty` returns `{"balance":0, "lifetime_accrued":0}`.

### 2.2 Loyalty page — empty state

1. Click the "История" link (or navigate to `/profile/loyalty`). Expected: header `0` balance, `Всего начислено: 0`, and an empty-state line ("История пока пуста. Баллы начисляются после получения заказа.").
2. `GET /api/v1/profile/loyalty/transactions` returns `{"items":[], "page":1, "per_page":20, "total":0}`.

### 2.3 Accrual after order completion

This requires walking an order to COMPLETED. Pick path A or B depending on whether you have a real Yandex key.

**Path A — pickup** (no maps dependency, fastest):

1. Add the "Cappuccino (QA)" to the cart via UI (or API, see Section 3 prereq below). Subtotal 600 ₽.
2. Navigate to `/checkout`, select Pickup, submit. Note the returned order id. Wait ~2 s for fake YuKassa to flip the order to `paid` (watch `payment-worker` logs).
3. From another terminal, drive the order through the states via admin:
   ```
   ORDER_ID=<from step 2>
   for S in preparing ready completed; do
     curl -s -X PATCH $BASE/api/v1/orders/$ORDER_ID/status \
       -H "Authorization: Bearer $ADMIN_TOKEN" \
       -H 'Content-Type: application/json' \
       -d "{\"new_status\":\"$S\"}" | jq .status
   done
   ```
   Expected final line: `"completed"`.
4. Back in Chrome, refresh `/profile/loyalty`. Expected: balance is > 0 (the Phase-3 accrual rule applies — percent of subtotal), `lifetime_accrued` matches `balance`, and the transactions list shows one row: type `accrual`, amount positive, `balance_after` matches balance, `order_id` links to `/orders/<short_id>`, timestamp ~now.

**Path B — delivery** (only if Yandex key is set; drive through COMPLETED via the courier panel as in phase-4 Section 3.4).

### 2.4 Pagination — "Load more"

The loyalty page uses a click-to-load button, not infinite scroll (see `LoyaltyPage.tsx:109`).

1. Create ≥ 21 transactions for this user. Fastest way: repeat 2.3 many times, or bulk-insert via psql (test-only):
   ```
   docker compose exec -T db psql -U aura -d aura -c \
     "INSERT INTO loyalty_transactions (id, user_id, type, amount, balance_after, description, created_at)
      SELECT gen_random_uuid(), (SELECT id FROM users WHERE phone='+79991234567'),
             'accrual', 10, 10 * i, 'QA fixture', now() - (i || ' minutes')::interval
      FROM generate_series(1, 25) AS i;"
   ```
   (Note: this leaves the `loyalty_accounts.balance` out of sync with transactions. For a faithful UI test it's fine because the two are independent reads; for real scenarios walk orders through.)
2. Refresh `/profile/loyalty`. Expected: 20 rows rendered, a "Load more" / "Показать ещё" button at the bottom.
3. Click it → second request `GET /api/v1/profile/loyalty/transactions?page=2` fires; the next batch appends; if `items + prev_rendered >= total`, the button hides.

### 2.5 Transaction row rendering

Confirm visually per `TransactionRow.tsx`:

- Accrual: amount prefixed `+`, green.
- Redemption: amount prefixed `−` (already negative in DB), red.
- Reversal / admin_adjustment: sign follows the server-provided amount; colour matches sign.
- `balance_after` text on the right, smaller font, "после: N".
- `order_id != null` → date/description area has a `Заказ #<first 8 chars of UUID>` link to `/orders/<uuid>`.
- `order_id == null` (admin_adjustment) → no link.

### 2.6 Reversal after order cancel (spot check)

1. Complete an order (balance goes up by X), then have admin `POST $BASE/api/v1/orders/$ORDER_ID/cancel` with a JSON body (`{"reason":"admin_decision"}`) — but note cancel only works in pre-`completed` states. To exercise reversal, cancel *before* completion on a different order: create new order, let it reach `paid`, then cancel. The accrual would not yet have been credited — this won't produce a reversal.
2. Simpler: Reversal rows show up only for the REDEMPTION path (promocode points spent and refunded). Since the customer SPA does not expose a points-redemption input yet (Phase 6), full reversal clickthrough is out of scope here. The backend path is covered by `test_order_cancel*.py`.

---

## Section 3 — End-to-end: promocode applied on a real order

There is **no UI** for entering a promocode on the customer SPA yet (cart page has no input — `/web/customer/src/pages/Cart/CartPage.tsx` does not render one). The code is passed as `promocode_code` on `POST /api/v1/orders`. Exercise via curl.

### 3.1 Prerequisites

1. Create and activate a promocode `QA10` per Section 1.2 + 1.8. Or use the curl fast-path from Section 5.1 below.
2. Non-empty cart (from phase-4 seed):
   ```
   curl -s -X POST $BASE/api/v1/cart/items \
     -H "Authorization: Bearer $CUST_TOKEN" \
     -H 'Content-Type: application/json' \
     -d '{"menu_item_id":1,"size_option_id":1,"quantity":1}' | jq '.items | length'
   # Expect: ≥ 1
   ```

### 3.2 Apply at checkout

```
ORDER=$(curl -s -X POST $BASE/api/v1/orders \
  -H "Authorization: Bearer $CUST_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"type":"pickup","promocode_code":"qa10"}')
echo "$ORDER" | jq '{id, status, promocode_id, pricing_breakdown}'
ORDER_ID=$(echo "$ORDER" | jq -r .id)
```

Expected: `status="created"`, `promocode_id` populated, pricing breakdown shows a discount line of 10% of subtotal. Server accepts lowercase `qa10` — validator UPPER()s before lookup.

### 3.3 Verify `current_uses` incremented atomically

```
curl -s $BASE/api/v1/admin/promocodes \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  | jq '.items[] | select(.code=="QA10") | {current_uses, max_uses, state}'
# Expect: current_uses: 1, state: "active" (or "exhausted" if max_uses=1)
```

The increment uses a **conditional UPDATE** (`services/checkout.py:407-419`) that refuses to go past `max_uses`. Racing the increment from the shell is hard — the true race is exercised by `tests/test_promocode_atomic_increment.py`. What you *can* easily exercise here is the duplicate-use rejection:

```
# second order with same code, max_uses already at cap → validator rejects
curl -s -o /dev/null -w '%{http_code} %{stderr}\n' -X POST $BASE/api/v1/orders \
  -H "Authorization: Bearer $CUST_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"type":"pickup","promocode_code":"QA10"}'
# Expect: 409; body detail contains "Global quota exhausted" (if max_uses reached)
#                               or  "Per-user quota exhausted" (if per-user cap was 1 and already used by this customer)
```

### 3.4 Walk order to COMPLETED → accrual

Same drill as Section 2.3 path A: `paid → preparing → ready → completed`. After `completed`, the customer loyalty page shows a new `accrual` row.

### 3.5 Cancel before completion → promocode decrement

Create a second order (3.2), but before driving it past `paid`, cancel via admin:

```
ORDER2=$(curl -s -X POST $BASE/api/v1/orders \
  -H "Authorization: Bearer $CUST_TOKEN" -H 'Content-Type: application/json' \
  -d '{"type":"pickup","promocode_code":"QA10"}' | jq -r .id)
# wait for paid
sleep 3
curl -s -X POST $BASE/api/v1/orders/$ORDER2/cancel \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H 'Content-Type: application/json' \
  -d '{"reason":"admin_decision"}' | jq .status
# Expect: "cancelled"

# Promocode current_uses decremented symmetrically
curl -s $BASE/api/v1/admin/promocodes \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  | jq '.items[] | select(.code=="QA10") | .current_uses'
# Expect: decremented by 1; cannot go below 0 even on repeat-cancel (order_cancel.py:63-70 guard)
```

Double-cancel is a no-op on `current_uses` (the conditional `WHERE current_uses > 0` zero-floors it). You can't easily trigger double-cancel via HTTP (second call returns a state-machine 409), but again the unit test covers the raw DB path.

### 3.6 Invalid promocode — validator error matrix

Each of these should return `HTTP 409 CONFLICT` from `POST /api/v1/orders` with a detail string as noted (`services/validators/promocode.py`). Exercise via curl.

| Condition | Detail string |
|---|---|
| Unknown code | `"Unknown promocode: <CODE>"` |
| Code exists but `is_active=false` | `"Promocode is inactive"` |
| `valid_from` in the future | `"Promocode is not yet valid"` |
| `valid_until` in the past | `"Promocode has expired"` |
| Global quota reached | `"Global quota exhausted"` |
| Per-user quota reached | `"Per-user quota exhausted"` |
| Subtotal below `min_order_amount` | `"subtotal <X> below min_order_amount <Y>"` |

Tip: to force `min_order_amount` failure, create a promo with min_order = 10_000 ₽ via Section 5.1, then checkout a 600 ₽ cart with it.

---

## Section 4 — Phase 5.5: Admin Layout role-filtered sidebar

The Layout component renders a sidebar keyed off `useCurrentRole()` and a `NAV_BY_ROLE` map (`components/Layout.tsx:18-24`). Route-level guards (`ProtectedRoute`) are the server-side-backed source of truth; the sidebar filter is a UX layer that hides links users can't use.

### 4.1 Admin — 6 links

1. Log in as `admin` / `admin123`. Expected sidebar: Dashboard, Orders, Menu, Users, Promos, Settings (in that order).
2. DOM check (DevTools → Elements): each `<a>` has `data-testid="nav-{dashboard|orders|menu|users|promos|settings}"`.

### 4.2 Barista — 2 links

1. Log out, log in as `barista` / `barista123`. You land on a dashboard-ish page (Orders, conceptually — but the current Orders UI is still a phase-4 stub).
2. Sidebar: **Orders, Menu**. No Dashboard, Users, Promos, Settings.
3. Manually navigate to `/admin/promos`. ProtectedRoute rejects → redirect back.
4. DOM check: only `nav-orders` and `nav-menu` testids present.

### 4.3 Courier — no Layout sidebar at all

1. Log out, log in as `courier` / `courier123`. You land directly on `/admin/courier` — the CourierShell, not the general Layout. There is no sidebar.
2. If you manually type `/admin/` (dashboard) the ProtectedRoute bounces you because courier is not in its `allowedRoles`. The `NAV_BY_ROLE.courier = []` is a defensive default for the edge case where Layout does render for a courier — you should never observe it in practice.

### 4.4 `useCurrentRole` persistence

1. Logged in as admin, DevTools → Application → Local Storage: `staffRole` key = `"admin"`.
2. Hard refresh. Sidebar still shows 6 links (no flicker to 0 links first — the hook reads synchronously in a `useMemo`).
3. Delete the `staffRole` key, refresh. ProtectedRoute bounces to `/admin/login`; if you somehow observe Layout mid-logout, it shows 0 links.

---

## Section 5 — API-only checks

### 5.1 Promocode CRUD (fast-path via curl)

```
# Create
PROMO_ID=$(curl -s -X POST $BASE/api/v1/admin/promocodes \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"code":"qatest","discount_type":"percent","discount_value":15,
       "valid_until":"2030-01-01T00:00:00Z","max_uses":100,"max_uses_per_user":3}' \
  | jq -r .id)
echo "promo=$PROMO_ID"
# Expect: non-empty UUID. Response "code" is "QATEST" (server-upper).

# List (wrapped — NOT a bare array)
curl -s "$BASE/api/v1/admin/promocodes?state=inactive&per_page=50" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '{total_count, first: .items[0] | {code, state, current_uses, max_uses}}'
# Expect: total_count ≥ 1; first.state = "inactive"

# Detail
curl -s $BASE/api/v1/admin/promocodes/$PROMO_ID \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '{code, state, is_active, current_uses}'
# Expect: code="QATEST", state="inactive", is_active=false, current_uses=0

# Patch — non-locked field on uses=0
curl -s -X PATCH $BASE/api/v1/admin/promocodes/$PROMO_ID \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H 'Content-Type: application/json' \
  -d '{"max_uses":200}' | jq .max_uses
# Expect: 200

# Activate
curl -s -X POST $BASE/api/v1/admin/promocodes/$PROMO_ID/activate \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '{state, is_active}'
# Expect: state="active", is_active=true

# Deactivate
curl -s -X POST $BASE/api/v1/admin/promocodes/$PROMO_ID/deactivate \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq .is_active
# Expect: false

# Duplicate code
curl -s -o /dev/null -w '%{http_code}\n' -X POST $BASE/api/v1/admin/promocodes \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H 'Content-Type: application/json' \
  -d '{"code":"QATEST","discount_type":"percent","discount_value":5,
       "valid_until":"2030-01-01T00:00:00Z"}'
# Expect: 409
```

### 5.2 Loyalty API

```
# Balance
curl -s $BASE/api/v1/profile/loyalty \
  -H "Authorization: Bearer $CUST_TOKEN" | jq '{balance, lifetime_accrued}'
# Expect: both integers (points, not kopecks).

# Transactions — wrapped, not bare
curl -s "$BASE/api/v1/profile/loyalty/transactions?page=1&per_page=5" \
  -H "Authorization: Bearer $CUST_TOKEN" | jq '{total, page, per_page, count: (.items|length)}'
# Expect: count ≤ 5, total ≥ count.

# Item shape
curl -s "$BASE/api/v1/profile/loyalty/transactions?per_page=1" \
  -H "Authorization: Bearer $CUST_TOKEN" | jq '.items[0] | keys'
# Expect: ["amount","balance_after","created_at","description","id","order_id","type"]
```

### 5.3 User isolation (INV-002, INV-010)

Create a second customer (different phone), authenticate, and confirm they don't see user A's transactions:

```
PHONE_B=+79995550000
PH_B=$(echo -n "$PHONE_B" | sha256sum | cut -d' ' -f1)
curl -s -X POST $BASE/api/v1/auth/send-code \
  -H 'Content-Type: application/json' -d "{\"phone\":\"$PHONE_B\"}"
sleep 1
OTP_B=$(docker compose exec -T redis redis-cli GET "otp:$PH_B" | jq -r .code)
CUST_B_TOKEN=$(curl -s -X POST $BASE/api/v1/auth/verify-code \
  -H 'Content-Type: application/json' \
  -d "{\"phone\":\"$PHONE_B\",\"code\":\"$OTP_B\"}" | jq -r .access_token)

curl -s $BASE/api/v1/profile/loyalty \
  -H "Authorization: Bearer $CUST_B_TOKEN" | jq '{balance, lifetime_accrued}'
# Expect: both 0 — user B sees their own empty account, not user A's.

curl -s $BASE/api/v1/profile/loyalty/transactions \
  -H "Authorization: Bearer $CUST_B_TOKEN" | jq '.total'
# Expect: 0
```

### 5.4 RBAC matrix

```
# Promocode routes — only ADMIN allowed.
for T in "$BARISTA_TOKEN" "$COURIER_TOKEN" "$CUST_TOKEN"; do
  curl -s -o /dev/null -w '%{http_code}\n' $BASE/api/v1/admin/promocodes \
    -H "Authorization: Bearer $T"
done
# Expect: 403 403 403

curl -s -o /dev/null -w '%{http_code}\n' $BASE/api/v1/admin/promocodes
# Expect: 401 (no token)

# Loyalty routes — only CUSTOMER allowed.
for T in "$ADMIN_TOKEN" "$BARISTA_TOKEN" "$COURIER_TOKEN"; do
  curl -s -o /dev/null -w '%{http_code}\n' $BASE/api/v1/profile/loyalty \
    -H "Authorization: Bearer $T"
done
# Expect: 403 403 403

curl -s -o /dev/null -w '%{http_code}\n' $BASE/api/v1/profile/loyalty
# Expect: 401
```

### 5.5 Field-locked PATCH (see Section 1.9)

Only reproducible after the promo has been used on at least one order — run Section 3 first, then:

```
curl -s -X PATCH $BASE/api/v1/admin/promocodes/$USED_PROMO_ID \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H 'Content-Type: application/json' \
  -d '{"code":"RENAMED"}' | jq .detail
# Expect detail: [{"type":"field_locked_after_use", "field":"code"}]
# HTTP status: 422
```

---

## Section 6 — Known gaps (intentionally out of scope here)

### Still stubs after Phase 5

- **Admin dashboard `/admin/`, orders `/admin/orders`, users `/admin/users`, settings `/admin/settings`** — each is a 12-line stub page rendering only a localized heading. No functionality behind them.
- **Customer orders list `/orders` and detail `/orders/{id}`** — still the Phase-3 stub routes; the `Заказ #<short_id>` link from a loyalty-transactions row lands on those stubs. Expected until the customer order-history ships.
- **Barista feed** — no realtime UI.
- **Customer promocode input** — cart/checkout has no field to enter a code. The `promocode_code` is accepted on the order-create API (Section 3), but the SPA does not expose it. Ships in Phase 6.

### ADMIN_ADJUSTMENT loyalty (Phase 6)

- There is no admin UI for crediting/debiting loyalty points by hand. The `ADMIN_ADJUSTMENT` enum value is wired through the transactions API, but no code path produces such a row yet. Section 2.5's "admin_adjustment" row will not appear naturally during Phase 5 testing.

### Phase-4 customer-SPA addresses drift (not regressed here; re-noted for continuity)

The three bugs in `web/customer/src/api/addresses.ts` documented in `phase4_manual_test_scenarios.md` §6 ("Known gaps → schema drift") are still present — Phase 5 did not touch that file. If you also sweep the addresses flow as part of this session, expect the same `422` on save, empty-list parsing, and broken "make primary" as before. Not a Phase-5 regression.

### Race demonstration via UI

- The atomic `current_uses` increment fix is genuinely race-proof (conditional UPDATE with `WHERE current_uses < max_uses`), but the race window is micro-seconds — you cannot reproduce it by clicking two browser tabs. Section 3.3 only exercises the already-exhausted rejection path. The race proper is covered by `services/core-api/tests/test_promocode_atomic_increment.py`.

---

## Appendix — Logs & one-liners

```
docker compose logs -f sms-worker         # OTP task delivery only — codes go to Redis (PII)
docker compose logs -f core-api           # HTTP errors, order transitions, promocode 409s, RBAC rejects
docker compose logs -f payment-worker     # fake YooKassa auto-drive to PAID
docker compose logs -f payment-webhook    # YooKassa webhook receipt (payment.succeeded)
docker compose logs -f nginx              # routing issues (404s, bad upstream)
```

Pull a live OTP for a phone:
```
PH=$(echo -n "+79991234567" | sha256sum | cut -d' ' -f1)
docker compose exec -T redis redis-cli GET "otp:$PH" | jq -r .code
```

Quick promo state snapshot:
```
curl -s "$BASE/api/v1/admin/promocodes?per_page=50" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  | jq '.items[] | {code, state, is_active, current_uses, max_uses}'
```

Common failure signatures:

- **`POST /api/v1/admin/promocodes` returns 422 with `pattern`** → code contains chars outside `^[A-Z0-9_-]+$`. The server upper-cases input, but spaces, dots, cyrillic, etc. still reject.
- **`POST /api/v1/admin/promocodes` returns 409 `promocode_code_conflict`** → the canonical (upper-cased) code already exists. Change the code or delete-by-deactivate the old one and re-use its code via a new row (physical DELETE is forbidden by §6.6).
- **`POST /api/v1/admin/promocodes/{id}/activate` returns 422 `valid_until required`** → the row has `valid_until IS NULL`. Edit it first, then activate.
- **`POST /api/v1/orders` with `promocode_code` returns 409 "Global quota exhausted"** → legit — `current_uses` reached `max_uses`. Check the Exhausted tab in the admin UI.
- **`POST /api/v1/orders` with `promocode_code` returns 409 "Per-user quota exhausted"** → this specific customer already used the code `max_uses_per_user` times.
- **`GET /api/v1/profile/loyalty` returns 500** → the `loyalty_accounts` row is missing for this user. Should be auto-created at customer registration (Phase 1); if missing, re-run the seed or check `database/seeds/phase4_manual_test.py` didn't fail mid-way.
- **Loyalty page shows balance but empty transactions** → likely a timing race with the order pipeline; the accrual row is inserted in the `COMPLETED` transition. Confirm the order is actually `completed` via `GET /api/v1/orders/{id}` before expecting the row.
- **Sidebar shows all 6 links for a barista** → the Phase-5.5 fix didn't land on this branch. Check `components/Layout.tsx` for the `NAV_BY_ROLE` import; verify `useCurrentRole` is imported from `@/lib/auth`, not a local stub.
