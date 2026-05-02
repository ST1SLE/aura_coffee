# Phase 6 — Comprehensive manual-test clickthrough (per-flow)

A self-contained end-to-end manual QA pass covering **all four roles** (admin, barista, courier, customer) and **every surface** shipped through phases 1–6. Organised **by flow**, not by role — a single order walks the same path across multiple actors, and that's how regressions actually surface.

Scope: supersedes `phase{2..5}_manual_test_scenarios.md` as the integration-wide clickthrough. Phase-specific docs remain useful as deep-dives for individual subsystems (promocodes in phase 5, addresses in phase 4, etc.) — this one is the horizontal walk.

Target duration: ~105 minutes end-to-end, with all mocks green. Keep a four-pane terminal layout (logs) + a browser window for each SPA + a fifth terminal for curl.

---

## §0 Pre-flight

### 0.1 Host ports & URLs

All host ports are worktree-local; read them from `.env`:

```bash
export BASE=http://localhost:$(grep '^NGINX_PORT=' .env | cut -d= -f2)
export CUSTOMER_URL=http://localhost:$(grep '^WEB_CUSTOMER_PORT=' .env | cut -d= -f2)/
export ADMIN_URL=http://localhost:$(grep '^WEB_ADMIN_PORT=' .env | cut -d= -f2)/
echo "BASE=$BASE"
echo "CUSTOMER=$CUSTOMER_URL"
echo "ADMIN=$ADMIN_URL"
```

Canonical local entry point: **`$BASE/`** (nginx). Customer SPA at `$BASE/`, admin SPA at `$BASE/admin/`. Direct SPA URLs (`$CUSTOMER_URL`, `$ADMIN_URL`) are for debugging only. **Ignore** the `http://localhost:5173/` / `5174/` lines printed by the Vite containers — those are container-internal ports.

### 0.2 Bring the stack up

```bash
./scripts/up.sh
```

Expect the banner to finish with `Migrations: applied ✓`. If it says `FAILED`, stop and run `docker compose logs db-migrate`. The banner also prints the four URLs above.

Containers you should see `Up (healthy)` or `Up`:

```
postgres, redis, core-api, payment-worker, payment-webhook, sms-worker,
web-customer, web-admin, nginx
```

`db-migrate` and `db-seed` are one-shot — they exit 0 on success and are expected to be `Exited (0)`.

### 0.3 Seed manual-QA data

The phase-4 seed is the source of truth for QA accounts and menu content. It is **idempotent** — re-run any time:

```bash
docker compose exec -T core-api python -m database.seeds.phase4_manual_test
# → phase4_manual_test seed applied
```

Inserts / upserts:

| Entity | Value |
|--------|-------|
| Admin staff | `admin` / `admin123` (from `initial_admin.py`, distinct seed) |
| Barista staff | `barista` / `barista123` |
| Courier staff | `courier` / `courier123`, plus `courier2` / `courier2123` for assignment-conflict checks |
| Customers | Active `+79991234567`, blocked `+79990000001`, pending `+79990000002` |
| Addresses | Active customer has "Дом (QA)" default, "Офис (QA)", and "Вне зоны (QA)" |
| Loyalty | Active customer has at least 1200 points and seeded transaction history |
| Menu | Drinks/food/merch/hidden QA categories; available, unavailable, archived items; sizes, modifiers, and media URL fields |
| Promocodes | `QA10`, `QA100`, `QAPAUSED`, `QAEXPIRED`, `QAUSED` |
| Orders | Representative pickup/delivery orders across created/paid/preparing/ready/in_delivery/completed/cancelled |
| Courier assignments | Preparing hidden handoff, ready-awaiting, assigned, picked-up, delivered, and cancelled QA assignments |
| Shop settings | default working hours, delivery fee, loyalty percent |

### 0.3-B Prepare optional local media fixtures

The seed stores **paths only** in the database for `Капучино (QA)`:
`/media/menu/cappuccino-qa/hero.mp4` and
`/media/menu/cappuccino-qa/poster.webp`. It does not upload or commit binaries
from the admin UI. For a visual smoke test, place one small
Aura-owned/generated video and one poster image under the Vite public tree:

```bash
mkdir -p web/customer/public/media/menu/cappuccino-qa
cp /path/to/qa-hero.mp4 web/customer/public/media/menu/cappuccino-qa/hero.mp4
cp /path/to/qa-poster.webp web/customer/public/media/menu/cappuccino-qa/poster.webp
```

Required public paths:

```text
/media/menu/cappuccino-qa/hero.mp4
/media/menu/cappuccino-qa/poster.webp
```

If the stack is already running, Vite usually serves new `public/` files without
a restart. Confirm through nginx:

```bash
curl -I "$BASE/media/menu/cappuccino-qa/poster.webp"
curl -I "$BASE/media/menu/cappuccino-qa/hero.mp4"
# Expect: 200. 404 means the file is missing from web/customer/public or the
# frontend container needs a restart.
```

Do **not** commit ad hoc QA media unless those files are approved product assets.
If you do not have media files, still run §2.1-A through the API/admin form and
expect the customer UI to fall back to the poster/no-media state rather than
blocking cart or checkout.

### 0.4 Grab tokens (all four roles)

Open a dedicated terminal and leave these tokens in the environment:

```bash
# staff — direct login/password
export ADMIN_TOKEN=$(curl -s -X POST $BASE/api/v1/staff/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"login":"admin","password":"admin123"}' | jq -r .access_token)

export BARISTA_TOKEN=$(curl -s -X POST $BASE/api/v1/staff/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"login":"barista","password":"barista123"}' | jq -r .access_token)

export COURIER_TOKEN=$(curl -s -X POST $BASE/api/v1/staff/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"login":"courier","password":"courier123"}' | jq -r .access_token)

# customer — OTP dance via mocked SMS
export PHONE=+79991234567
export PH=$(echo -n "$PHONE" | sha256sum | cut -d' ' -f1)
docker compose exec -T redis redis-cli DEL \
  "sms_rate:$PH:min" "sms_rate:$PH:hour" "sms_rate:$PH:day" > /dev/null

SEND_CODE_RESPONSE=$(curl -s -X POST $BASE/api/v1/auth/send-code \
  -H 'Content-Type: application/json' -d "{\"phone\":\"$PHONE\"}")
echo "$SEND_CODE_RESPONSE" | jq -e '.message == "OTP sent" and (has("phone_hash") | not)' > /dev/null

for i in {1..10}; do
  OTP_DATA=$(docker compose exec -T redis redis-cli GET "otp:$PH")
  OTP_STATUS=$(echo "$OTP_DATA" | jq -r '.status // empty')
  [ "$OTP_STATUS" = "sent" ] && break
  sleep 1
done

[ "$OTP_STATUS" = "sent" ] || {
  echo "OTP was not delivered; latest Redis payload:"
  echo "$OTP_DATA" | jq .
  docker compose logs --tail 50 sms-worker
  return 1 2>/dev/null || exit 1
}

OTP=$(docker compose exec -T redis redis-cli GET "otp:$PH" | jq -r .code)
VERIFY_RESPONSE=$(curl -s -X POST $BASE/api/v1/auth/verify-code \
  -H 'Content-Type: application/json' \
  -d "{\"phone\":\"$PHONE\",\"code\":\"$OTP\"}")
export CUST_TOKEN=$(echo "$VERIFY_RESPONSE" | jq -r .access_token)

[ "$CUST_TOKEN" != "null" ] && [ -n "$CUST_TOKEN" ] || {
  echo "Customer verify-code failed:"
  echo "$VERIFY_RESPONSE" | jq .
  return 1 2>/dev/null || exit 1
}

for v in ADMIN_TOKEN BARISTA_TOKEN COURIER_TOKEN CUST_TOKEN; do
  eval "t=\$$v"; echo "$v: ${t:0:25}… (len=${#t})"
done
# Expect: four non-empty JWTs, each ~150–220 chars.
```

### 0.4-B Export seeded QA IDs

Do not assume menu IDs are `1` in a reused database. Export the seeded item,
size, and known-good address IDs once and reuse them in later curl probes:

```bash
export CAPPUCCINO_ITEM_ID=$(curl -s "$BASE/api/v1/menu" \
  | jq -r '.categories[].items[] | select(.name_ru=="Капучино (QA)") | .id' \
  | head -n1)

export CAPPUCCINO_SIZE_M_ID=$(curl -s "$BASE/api/v1/menu" \
  | jq -r '.categories[].items[] | select(.name_ru=="Капучино (QA)") |
           .size_options[] | select(.label=="M") | .id' \
  | head -n1)

export QA_HOME_ADDR_ID=$(curl -s "$BASE/api/v1/profile/addresses" \
  -H "Authorization: Bearer $CUST_TOKEN" \
  | jq -r '.[] | select(.label=="Дом (QA)") | .id' \
  | head -n1)

export QA_CUSTOMER_ID=$(curl -s "$BASE/api/v1/profile" \
  -H "Authorization: Bearer $CUST_TOKEN" | jq -r .id)

printf 'CAPPUCCINO_ITEM_ID=%s\nCAPPUCCINO_SIZE_M_ID=%s\nQA_HOME_ADDR_ID=%s\nQA_CUSTOMER_ID=%s\n' \
  "$CAPPUCCINO_ITEM_ID" "$CAPPUCCINO_SIZE_M_ID" "$QA_HOME_ADDR_ID" "$QA_CUSTOMER_ID"

[ -n "$CAPPUCCINO_ITEM_ID" ] && [ -n "$CAPPUCCINO_SIZE_M_ID" ] && [ -n "$QA_HOME_ADDR_ID" ] && [ -n "$QA_CUSTOMER_ID" ] || {
  echo "Seed IDs missing; re-run §0.3 and check §0.4 auth."
  return 1 2>/dev/null || exit 1
}
```

### 0.5 Mock-mode sanity checks

Before trusting anything downstream, confirm the three externals are in their mocked modes.

**SMS — `SMS_BACKEND=log`.** The code lives in Redis under `otp:<sha256(phone)>`.
Worker logs are intentionally redacted and do **not** print raw phone numbers,
OTP codes, or SMS bodies:

```bash
docker compose logs --tail 5 sms-worker | grep -E '\[SMS:log\]'
# Expect: a line like
#   [SMS:log] recipient_ref=8d2... kind=otp message_len=...
```

If you don't see `[SMS:log]`, `.env` either has `SMS_BACKEND=smsru` or the worker hasn't picked up a task yet — re-run step 0.4. Pull the actual OTP only from Redis as shown in §0.4 / §1.1.

**YuKassa — `YUKASSA_BACKEND=fake`.** Confirm via the health endpoint:

```bash
curl -s http://localhost:$(grep '^CORE_API_PORT=' .env | cut -d= -f2)/health | jq .
# Expect: {"status":"ok","yukassa_backend":"fake"}
```

With `YUKASSA_FAKE_OUTCOME=success` (the `.env.example` default), every checkout auto-drives `payment.succeeded` via a Celery task with `countdown=1`, so `CREATED → PAID` takes ~2 s.

Flip the outcome for negative tests:

```bash
# cancel path
sed -i 's/^YUKASSA_FAKE_OUTCOME=.*/YUKASSA_FAKE_OUTCOME=canceled/' .env
docker compose up -d --force-recreate --no-deps core-api payment-worker payment-webhook

# simulated network error — next checkout attempt will hit celery retry/compensation
sed -i 's/^YUKASSA_FAKE_OUTCOME=.*/YUKASSA_FAKE_OUTCOME=http_error/' .env
docker compose up -d --force-recreate --no-deps core-api payment-worker payment-webhook

# restore
sed -i 's/^YUKASSA_FAKE_OUTCOME=.*/YUKASSA_FAKE_OUTCOME=success/' .env
docker compose up -d --force-recreate --no-deps core-api payment-worker payment-webhook
```

**Important**: `docker compose restart` does **NOT** re-read `env_file`. Always use `docker compose up -d --force-recreate` after editing `.env`, otherwise the old values stay in the container.

**Yandex Maps — real API only, no fake backend.** Behaviour depends on whether `YANDEX_MAPS_API_KEY` is set and valid:

| Key state | `/suggest` | `/geocode` |
|-----------|-----------|-----------|
| Empty | 503 `maps_unavailable` or 500 `yandex_upstream_error` | 503 `maps_unavailable` |
| Set but invalid / not-activated | 500 `yandex_upstream_error` (Yandex 403 upstream) | 500 `yandex_upstream_error` |
| Valid, both `HTTP Geocoder` + `Suggest API` activated | list of suggestions | `{lat, lon, precision, canonical_text}` |

Quick probe (from inside the core-api container so the real env var is seen):

```bash
docker compose exec -T core-api python3 -c "
import httpx, os
k = os.getenv('YANDEX_MAPS_API_KEY','')
print('key-present:', bool(k), 'len:', len(k))
r = httpx.get('https://geocode-maps.yandex.ru/1.x/',
              params={'geocode':'Москва','apikey':k,'format':'json'}, timeout=5)
print('HTTP', r.status_code, '—', r.text[:120])
"
# Expect: key-present: True; HTTP 200 and a JSON body. 403 = key not valid / not activated.
```

If Yandex returns 403, flows that depend on it (customer address autocomplete, fresh delivery-order creation via the UI) will fail. Fall back to the SQL-seed path documented in §1.4 — all remaining flows work unchanged.

### 0.6 Four log tails (one terminal each)

```bash
docker compose logs -f core-api           # HTTP, RBAC 403s, state transitions
docker compose logs -f sms-worker         # OTP send events
docker compose logs -f payment-worker     # fake YuKassa callbacks
docker compose logs -f payment-webhook    # canonical webhook receipts
```

Optional fifth: `docker compose logs -f nginx` if you suspect routing issues.

### 0.7 Reset cheat-sheet

```bash
# DESTRUCTIVE: wipe DB, Redis, and all Compose volumes, then rebuild.
# Confirm you really want to lose local QA data before running this block.
docker compose down -v
./scripts/up.sh
docker compose exec -T core-api python -m database.seeds.phase4_manual_test

# softer — just reset the OTP rate-limiter for the QA phone
PH=$(echo -n "+79991234567" | sha256sum | cut -d' ' -f1)
docker compose exec -T redis redis-cli DEL \
  "sms_rate:$PH:min" "sms_rate:$PH:hour" "sms_rate:$PH:day" "otp:$PH"

# softer still — clear a single customer's cart
curl -s -X DELETE $BASE/api/v1/cart -H "Authorization: Bearer $CUST_TOKEN"
```

---

## §1 FLOW: Customer registration & profile

### 1.1 OTP — happy path

**UI.** Open `$BASE/` → "Войти" / "Login" → enter `+79991234567` → "Получить код". The page advances to a 4-input OTP box. Pull the code:

```bash
docker compose exec -T redis redis-cli GET "otp:$PH" | jq -r .code
```

Type it in → "Подтвердить". Expect redirect to `/` (customer home) with an avatar in the header.

**Network check (DevTools).** `POST /api/v1/auth/send-code` returned 200 `{"message":"OTP sent"}` and did not expose `phone_hash`. `POST /api/v1/auth/verify-code` returned 200 with `{access_token, refresh_token, token_type}`. `access_token` lands in `localStorage` / memory per the auth-state spec.

### 1.2 OTP — negative paths

- **Wrong code.** Enter `000000` (assuming that's not the real one) → expect toast with "Неверный код" / localized error; attempts counter in Redis (`otp:$PH` → `.attempts`) increments; after 5 wrong attempts the record is wiped and the UI forces a re-send.
- **Expired code.** Wait > 5 min (OTP TTL from `core-api` settings) or `redis-cli DEL "otp:$PH"` → re-submit → "Код истёк".
- **Rate limit.** Spam `/api/v1/auth/send-code` for the same phone 6× in one minute → 429 `Too many requests`. Keys: `sms_rate:$PH:min`, `:hour`, `:day` (1/min, 5/hour, 10/day). Reset via step 0.7.

### 1.3 Profile read & patch

**UI.** `/profile`. Shows phone (read-only), name input, language selector (RU / EN), logout. Change name to "QA Tester", save → toast → page re-renders with new value.

**API cross-check.**

```bash
curl -s $BASE/api/v1/profile -H "Authorization: Bearer $CUST_TOKEN" | jq .
# Expect: { id, phone, name, language, ... }. phone is the plaintext +7…,
# only because the viewer is the owner (INV-013 PII isolation — others see hashes).

curl -s -X PATCH $BASE/api/v1/profile \
  -H "Authorization: Bearer $CUST_TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"QA Tester","language":"ru"}' | jq '{name, language}'
```

Log out via UI → header reverts to "Войти". `localStorage` cleared. `POST /api/v1/auth/logout` returns 200.

### 1.4 Delivery address add — **real Yandex path**

*Skip to 1.5 if Yandex returns 403 in §0.5.*

**UI.** `/profile/addresses` → "Добавить адрес". The dialog renders an `AddressAutocomplete` input.

1. Type "Москва Красная" — after ~300 ms a dropdown of suggestions appears (`GET /api/v1/maps/suggest?text=…` — 200 with an array).
2. Pick "Москва, Красная площадь" → form autofills `address_text`, `lat`, `lon`; a `GET /api/v1/maps/geocode?text=…` fires to canonicalize.
3. Fill label "Работа", apartment "12", entrance "3", floor "4", comment "домофон 12B".
4. Submit → `POST /api/v1/profile/addresses` → 201 with the new address; dialog closes; the new row appears alongside the seeded "Дом (QA)", "Офис (QA)", and "Вне зоны (QA)" rows.

**If Yandex returns 422 `low_precision`**: you picked a suggestion whose precision is below `street`. Pick a more specific suggestion.

### 1.4-B Delivery address add — **API fallback** (Yandex unavailable)

```bash
# Save a known in-radius address without autocomplete/geocoding.
curl -s -X POST $BASE/api/v1/profile/addresses \
  -H "Authorization: Bearer $CUST_TOKEN" -H 'Content-Type: application/json' \
  -d '{"label":"Работа API (QA)",
       "address_text":"Москва, ул. Льва Толстого, 16",
       "lat":55.733,
       "lon":37.588,
       "apartment":"12",
       "entrance":"3",
       "floor":"4",
       "comment":"Yandex unavailable fallback",
       "is_default":false}' \
  | jq '{id, label, is_default, lat, lon}'

# Confirm via the customer API
curl -s $BASE/api/v1/profile/addresses -H "Authorization: Bearer $CUST_TOKEN" \
  | jq '. | map({label, is_default, lat, lon})'
# Expect: seeded rows plus "Работа API (QA)"; "Дом (QA)" is_default=true unless you changed it.
```

### 1.5 Address make-default, delete

**UI.** Click the ☆ / "Сделать основным" on "Работа" → refresh → "Работа" now flagged as default, "Дом (QA)" demoted. Delete "Работа" → row disappears.

**API.**

```bash
ADDR_ID=$(curl -s $BASE/api/v1/profile/addresses \
  -H "Authorization: Bearer $CUST_TOKEN" \
  | jq -r '.[] | select(.label=="Работа" or .label=="Работа API (QA)") | .id' \
  | head -n1)
# make-default
curl -s -X PATCH $BASE/api/v1/profile/addresses/$ADDR_ID \
  -H "Authorization: Bearer $CUST_TOKEN" -H 'Content-Type: application/json' \
  -d '{"is_default":true}' | jq .is_default
# delete
curl -s -o /dev/null -w '%{http_code}\n' -X DELETE \
  $BASE/api/v1/profile/addresses/$ADDR_ID -H "Authorization: Bearer $CUST_TOKEN"
# Expect: 204
```

**Constraint check.** The unique partial index `ix_delivery_addresses_user_default WHERE is_default = true` guarantees at most one default per user. PATCH updates intentionally do not accept `lat` / `lon`; if an edit returns 422, check DevTools and confirm the client is sending only editable fields (`label`, `address_text`, `apartment`, `entrance`, `floor`, `comment`, `is_default`).

---

## §2 FLOW: Customer places a pickup order (mocked payment)

This is the fastest end-to-end path — no Yandex, no courier, one actor. Use it to assert that mocks are wired up before attempting §3.

### 2.1 Browse the public menu

**UI.** `/menu` (customer SPA home). The customer shell is dark and mobile-first:
bottom nav on phone widths, horizontal category tabs, and media-led item cards.
The seeded "Капучино (QA)" has media URL fields; if the optional public files
from §0.3-B are absent, the card/detail should degrade without blocking cart or
checkout. Click the card → the bottom-sheet detail opens with size options
(S/M/L), modifiers, and a fixed add-to-cart bar that remains visible at the
bottom.

**API.**

```bash
curl -s $BASE/api/v1/menu | jq '.categories | map({id, name_ru, items: (.items|length)})'
# Expect visible QA categories for drinks, food, merch; hidden/archived rows stay out of public menu.

curl -s $BASE/api/v1/menu \
  | jq '.categories[].items[] | select(.name_ru=="Капучино (QA)") |
        {image_url, media_type, media_url, media_poster_url, available, base_price}'
# Expect media_type="video" and the seeded public media paths.
```

### 2.1-A Admin sets menu media for the QA item

This is the manual smoke for the new media contract. Use the admin SPA first;
keep the curl path below as an exact fallback/check.

**UI.** Log in as `admin` / `admin123` → `$BASE/admin/menu` → edit
"Капучино (QA)".

Fill:

| Field | Value |
|-------|-------|
| Legacy image URL | leave empty, unless testing legacy fallback |
| Media type | `video` |
| Video path | `/media/menu/cappuccino-qa/hero.mp4` |
| Poster path | `/media/menu/cappuccino-qa/poster.webp` |

Save. DevTools Network should show `PUT /api/v1/admin/menu/items/<id>` with
`media_type`, `media_url`, and `media_poster_url`. The response should echo the
same values. There is no binary upload request.

**API fallback/check.**

```bash
ITEM_ID=$(curl -s $BASE/api/v1/admin/menu/items \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  | jq -r 'map(select(.name_ru=="Капучино (QA)"))[0].id')

curl -s -X PUT $BASE/api/v1/admin/menu/items/$ITEM_ID \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H 'Content-Type: application/json' \
  -d '{"media_type":"video",
       "media_url":"/media/menu/cappuccino-qa/hero.mp4",
       "media_poster_url":"/media/menu/cappuccino-qa/poster.webp"}' \
  | jq '{id, media_type, media_url, media_poster_url, image_url}'
# Expect: media_type "video"; paths exactly as submitted; image_url unchanged/null.

curl -s $BASE/api/v1/menu \
  | jq '.categories[].items[] | select(.id=='"$ITEM_ID"') |
        {media_type, media_url, media_poster_url, image_url}'
# Expect: public menu exposes the same media fields. No signed URLs, query
# strings, or external storage credentials.
```

**Admin validation matrix.** Each should keep the form open or return 422, and
the previous valid media fields should remain unchanged:

| Input | Expected result |
|-------|-----------------|
| `media_type=video`, video path set, poster empty | poster required |
| `media_type=video`, path `/media/menu/cappuccino-qa/poster.webp` | video path must end `.mp4`/`.webm` |
| `media_type=image`, path `/media/menu/cappuccino-qa/hero.mp4` | image path must end `.avif`/`.jpg`/`.jpeg`/`.png`/`.webp` |
| `media_url=https://storage.example/hero.mp4?token=abc` | external/signed URLs rejected |
| `media_url=/media/menu/../secret.mp4` | parent directory segments rejected |
| `media_url=/assets/hero.mp4` | path must live under `/media/menu/` |

Reset to no media if you need to re-run the fallback state:

```bash
curl -s -X PUT $BASE/api/v1/admin/menu/items/$ITEM_ID \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H 'Content-Type: application/json' \
  -d '{"media_type":null,"media_url":null,"media_poster_url":null}' \
  | jq '{media_type, media_url, media_poster_url}'
```

### 2.1-B Customer media and mobile visual check

With §2.1-A applied, reload `$BASE/menu` through nginx.

Expected:

- The card is media-led and still fits at 375 px, 390 px, and 430 px widths.
- The card does **not** show native video controls; tapping the card opens the
  detail sheet.
- The detail sheet shows the media hero with controls, a close icon, size
  selector, and a bottom add-to-cart bar. Text and buttons do not overlap in RU
  or EN.
- If `prefers-reduced-motion: reduce` is emulated in DevTools, the poster image
  renders instead of auto-playing video.
- If the video path 404s but the poster exists, the detail/card remains usable
  and checkout still works. Broken media must not block cart mutations.

Quick API invariant while doing the visual pass:

```bash
curl -s -X DELETE $BASE/api/v1/cart -H "Authorization: Bearer $CUST_TOKEN" > /dev/null
curl -s -X POST $BASE/api/v1/cart/items \
  -H "Authorization: Bearer $CUST_TOKEN" -H 'Content-Type: application/json' \
  -d "{\"menu_item_id\":$CAPPUCCINO_ITEM_ID,\"size_option_id\":$CAPPUCCINO_SIZE_M_ID,\"quantity\":1}" \
  | jq '{items: (.items | map({menu_item_id, size_option_id, quantity, line_total})), subtotal}'
# Expect: same cart payload shape as before media: no media fields in cart lines
# and no price change caused by media.
```

### 2.2 Add to cart, modify, remove

**UI.** In the drink drawer: select size M → "Добавить в корзину". Cart icon in header gains a badge. Open `/cart`. Increment qty to 2 via `+` button, decrement once, remove the line. Add it back with qty 2.

**API probe at each step.**

```bash
# empty first
curl -s -X DELETE $BASE/api/v1/cart -H "Authorization: Bearer $CUST_TOKEN" > /dev/null

# add 1
curl -s -X POST $BASE/api/v1/cart/items \
  -H "Authorization: Bearer $CUST_TOKEN" -H 'Content-Type: application/json' \
  -d "{\"menu_item_id\":$CAPPUCCINO_ITEM_ID,\"size_option_id\":$CAPPUCCINO_SIZE_M_ID,\"quantity\":1}" \
  | jq '{items: (.items | map({menu_item_id, quantity, line_total})), subtotal}'
# Expect: 1 line, line_total 60000 (kopecks), subtotal 60000

# bump qty to 2
LINE_ID=$(curl -s $BASE/api/v1/cart -H "Authorization: Bearer $CUST_TOKEN" \
  | jq -r '.items[0].id')
curl -s -X PATCH $BASE/api/v1/cart/items/$LINE_ID \
  -H "Authorization: Bearer $CUST_TOKEN" -H 'Content-Type: application/json' \
  -d '{"quantity":2}' | jq '{items: (.items | map({quantity, line_total})), subtotal}'
# Expect: quantity 2, line_total 120000, subtotal 120000
```

Top-level fields: `{currency, expires_at, items, subtotal}`. Note `expires_at` — the cart is Redis-backed with TTL from `CART_TTL_SECONDS` (default 24 h).

### 2.3 Checkout pickup → fake YuKassa → paid

**UI.** `/cart` → "Оформить" → `/checkout`. Pickup tab selected by default (only option unless §3). "Оплатить" → loading spinner → SPA redirects to `/orders/<short_id>`. In fake YuKassa mode the page must NOT navigate to `/dev/yukassa-sandbox/fake_…`; it keeps polling the order. Watch `payment-worker` logs: within 1–2 s you'll see `Task yukassa_fake_callback[…] succeeded`, and the order page flips from "Новый" / "Created" to "Оплачен" / "Paid".

**API.**

```bash
ORDER=$(curl -s -X POST $BASE/api/v1/orders \
  -H "Authorization: Bearer $CUST_TOKEN" -H 'Content-Type: application/json' \
  -d '{"type":"pickup"}')
echo "$ORDER" | jq '{id, status, subtotal, total}'
ORDER_ID=$(echo "$ORDER" | jq -r .id)

sleep 3   # let the fake-callback task fire
curl -s $BASE/api/v1/orders/$ORDER_ID -H "Authorization: Bearer $CUST_TOKEN" \
  | jq '{id, status, type, payment: .payment, items: (.items|length)}'
# Expect: status "paid", payment.status "succeeded", items 1
```

### 2.4 View order detail, customer cancels before prep

**UI.** Create another pickup order (repeat 2.3). On the detail page while status is "paid" and before barista touches it, click "Отменить". Confirm dialog → order flips to "Cancelled". Refund fires automatically; payment-worker logs show `refund.succeeded`.

**API.**

```bash
ORDER_ID=<fresh order>
sleep 3
curl -s -X POST $BASE/api/v1/orders/$ORDER_ID/cancel \
  -H "Authorization: Bearer $CUST_TOKEN" -H 'Content-Type: application/json' \
  -d '{"reason":"customer_decision"}' | jq .status
# Expect: "cancelled"
```

Post-cancel state machine: once barista moves the order to `preparing`, customer cancel is rejected — that's §6.1 of PDD (the state-machine) and is the correct behaviour. Exercise it:

```bash
# bring a new order to PREPARING first via the barista token (see §4)
curl -s -X PATCH $BASE/api/v1/orders/$ORDER_ID/status \
  -H "Authorization: Bearer $BARISTA_TOKEN" -H 'Content-Type: application/json' \
  -d '{"new_status":"preparing"}'

# now customer cancel must fail
curl -s -o /dev/null -w '%{http_code}\n' -X POST \
  $BASE/api/v1/orders/$ORDER_ID/cancel \
  -H "Authorization: Bearer $CUST_TOKEN" -H 'Content-Type: application/json' \
  -d '{"reason":"customer_decision"}'
# Expect: 409 (invalid transition)
```

### 2.5 Promocode applied

The customer SPA does **not** expose a promocode input yet (cart page has no field). Apply via the order-create API; UI clickthrough is in §5.

```bash
# create a promo first — see §5.1 for UI; curl fast-path:
PROMO_ID=$(curl -s -X POST $BASE/api/v1/admin/promocodes \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H 'Content-Type: application/json' \
  -d '{"code":"qa10","discount_type":"percent","discount_value":10,
       "valid_until":"2030-01-01T00:00:00Z","max_uses":5,"max_uses_per_user":3}' \
  | jq -r .id)
curl -s -X POST $BASE/api/v1/admin/promocodes/$PROMO_ID/activate \
  -H "Authorization: Bearer $ADMIN_TOKEN" > /dev/null

# populate cart then checkout with code
curl -s -X DELETE $BASE/api/v1/cart -H "Authorization: Bearer $CUST_TOKEN" > /dev/null
curl -s -X POST $BASE/api/v1/cart/items \
  -H "Authorization: Bearer $CUST_TOKEN" -H 'Content-Type: application/json' \
  -d "{\"menu_item_id\":$CAPPUCCINO_ITEM_ID,\"size_option_id\":$CAPPUCCINO_SIZE_M_ID,\"quantity\":1}" > /dev/null

curl -s -X POST $BASE/api/v1/orders \
  -H "Authorization: Bearer $CUST_TOKEN" -H 'Content-Type: application/json' \
  -d '{"type":"pickup","promocode_code":"qa10"}' \
  | jq '{status, promocode_id, subtotal, discount_amount, total}'
# Expect: discount_amount ≈ 10% of subtotal (6000 kopecks on 60000),
#         promocode_id populated, total = subtotal - discount_amount
```

Server UPPER()s the code → the promocode row with `code="QA10"` matches. See §5.6 for the full promocode walk.

---

## §3 FLOW: Customer places a delivery order

Depends on **at least one delivery address** for the customer (§1.4 or 1.4-B) and **shop_settings** delivery config (seeded by phase-4; adjustable in §7.4).

### 3.1 Address selection at checkout

**UI.** `$BASE/` → cart → `/checkout`. Tab "Доставка" / "Delivery". The form shows a dropdown of saved addresses (from §1). Selecting one shows `lat/lon` beneath for tester visibility.

Alternatively, type a fresh address in the autocomplete — this triggers `/api/v1/maps/suggest` + `/geocode`. If Yandex returned 403 (§0.5), the dropdown is empty and you must pick a pre-saved address.

### 3.2 Delivery fee + min-amount validation

Rules from `shop_settings` (check current values):

```bash
curl -s $BASE/api/v1/admin/settings -H "Authorization: Bearer $ADMIN_TOKEN" \
  | jq '{min_delivery_amount, delivery_fee, free_delivery_threshold, delivery_radius_km, shop_lat, shop_lon}'
```

- Subtotal < `min_delivery_amount` → checkout rejects with 422 before creating the order.
- Subtotal ≥ `free_delivery_threshold` → `delivery_fee` is set to 0 in the response.
- Address lat/lon farther than `delivery_radius_km` from `shop_lat/lon` → 422.

**API test — at boundary:**

```bash
# Put a small order first — less than min
curl -s -X DELETE $BASE/api/v1/cart -H "Authorization: Bearer $CUST_TOKEN" > /dev/null
curl -s -X POST $BASE/api/v1/cart/items \
  -H "Authorization: Bearer $CUST_TOKEN" -H 'Content-Type: application/json' \
  -d "{\"menu_item_id\":$CAPPUCCINO_ITEM_ID,\"size_option_id\":$CAPPUCCINO_SIZE_M_ID,\"quantity\":1}" > /dev/null

ADDR_ID=${QA_HOME_ADDR_ID:-$(curl -s $BASE/api/v1/profile/addresses \
  -H "Authorization: Bearer $CUST_TOKEN" \
  | jq -r '.[] | select(.label=="Дом (QA)") | .id' | head -n1)}

# Expect 422 if subtotal < min_delivery_amount
curl -s -o /tmp/resp -w '%{http_code}\n' -X POST $BASE/api/v1/orders \
  -H "Authorization: Bearer $CUST_TOKEN" -H 'Content-Type: application/json' \
  -d "{\"type\":\"delivery\",\"delivery_address_id\":\"$ADDR_ID\"}"
cat /tmp/resp | jq .detail
```

### 3.3 Create a passing delivery order

Scale up the cart to comfortably exceed `min_delivery_amount`:

```bash
curl -s -X POST $BASE/api/v1/cart/items \
  -H "Authorization: Bearer $CUST_TOKEN" -H 'Content-Type: application/json' \
  -d "{\"menu_item_id\":$CAPPUCCINO_ITEM_ID,\"size_option_id\":$CAPPUCCINO_SIZE_M_ID,\"quantity\":5}" > /dev/null

DEL_ORDER=$(curl -s -X POST $BASE/api/v1/orders \
  -H "Authorization: Bearer $CUST_TOKEN" -H 'Content-Type: application/json' \
  -d "{\"type\":\"delivery\",\"delivery_address_id\":\"$ADDR_ID\"}")
echo "$DEL_ORDER" | jq '{id, status, type, delivery_fee, total}'
export DEL_ORDER_ID=$(echo "$DEL_ORDER" | jq -r .id)

sleep 3
curl -s $BASE/api/v1/orders/$DEL_ORDER_ID -H "Authorization: Bearer $CUST_TOKEN" \
  | jq '{status, type, delivery_address_id}'
# Expect: status "paid", type "delivery"
```

Hand this `DEL_ORDER_ID` off to §4 (barista) then §6 (courier).

---

## §4 FLOW: Barista fulfils

### 4.1 Sidebar renders for barista with exactly 2 links

**UI.** Open `$BASE/admin/` in a **fresh private-window** (to avoid admin-token bleed). Log in as `barista` / `barista123`. Layout shows sidebar with **only** "Orders" and "Menu" — no Dashboard, Users, Promos, Settings.

DOM check: `document.querySelectorAll('[data-testid^="nav-"]')` returns exactly `nav-orders` and `nav-menu`. Manually typing `$BASE/admin/promos` must redirect (ProtectedRoute — phase 5.5).

### 4.2 Orders feed

**UI.** `/admin/orders`. Table lists all orders, newest first. Filters: status (all / created / paid / preparing / ready / …), type (pickup / delivery / all), date-range. Selecting a row opens a detail panel with items, customer-ish identifiers (user_id is an opaque UUID — INV-013), and state-transition buttons.

**API shape** — important: top-level key is `.orders` (not `.items`):

```bash
curl -s "$BASE/api/v1/admin/orders?per_page=5" \
  -H "Authorization: Bearer $BARISTA_TOKEN" \
  | jq '{total_count, orders: (.orders | map({id, status, type, total, created_at}))}'
```

### 4.3 Pickup order: paid → preparing → ready → completed

**UI.** Pick the pickup order from §2.3 (must be in `paid`). Click "В работе" → status becomes `preparing`. Click "Готов" → `ready`. Click "Выдан" → `completed`. Loyalty accrues on the customer side (§7.3 cross-check).

**API.**

```bash
for S in preparing ready completed; do
  curl -s -X PATCH $BASE/api/v1/orders/$ORDER_ID/status \
    -H "Authorization: Bearer $BARISTA_TOKEN" -H 'Content-Type: application/json' \
    -d "{\"new_status\":\"$S\"}" | jq -r .status
done
# Expect lines: preparing, ready, completed.
```

Invalid-transition sanity: try `paid → completed` directly → expect 409 `invalid_transition`.

### 4.4 Delivery order: paid → preparing → ready → **hand off to courier**

Same three transitions (`paid` → `preparing` → `ready`) via the barista token on `DEL_ORDER_ID`. **Do NOT** go `completed`; delivery is completed by the courier.

What happens during this flow: `paid → preparing` creates a `delivery_assignment`
in `awaiting_courier`; the courier available feed hides it until the order also
reaches `ready`.

Cross-check:

```bash
export ASG_ID=$(curl -s "$BASE/api/v1/courier/assignments/available" \
  -H "Authorization: Bearer $COURIER_TOKEN" \
  | jq -r --arg oid "$DEL_ORDER_ID" 'map(select(.order_id==$oid))[0].id')
curl -s "$BASE/api/v1/courier/assignments/available" \
  -H "Authorization: Bearer $COURIER_TOKEN" \
  | jq --arg oid "$DEL_ORDER_ID" 'map(select(.order_id==$oid)) | .[0] | {id, order_id, status}'
# Expect: the DEL_ORDER_ID row exists and status is "awaiting_courier".
```

### 4.5 Toggle item availability

**UI.** `/admin/menu` (both admin and barista can do this — phase 5 menu RBAC) → click the availability toggle on "Капучино (QA)". Customer SPA menu should show the drink as unavailable/disabled within a few seconds. The default public read path includes stop-listed items; `GET /api/v1/menu?available=true` is the filtered path.

**API.**

```bash
curl -s -X PATCH $BASE/api/v1/admin/menu/items/$CAPPUCCINO_ITEM_ID/availability \
  -H "Authorization: Bearer $BARISTA_TOKEN" -H 'Content-Type: application/json' \
  -d '{"available":false}' | jq '{available, availability}'
# Expect: {"available":false,"availability":"stop_list"}

curl -s "$BASE/api/v1/menu" \
  | jq --argjson id "$CAPPUCCINO_ITEM_ID" '.categories[].items[] | select(.id==$id) | {available}'
# Expect: {"available":false}; item is present but disabled in the SPA.

curl -s "$BASE/api/v1/menu?available=true" \
  | jq --argjson id "$CAPPUCCINO_ITEM_ID" '[.categories[].items[] | select(.id==$id)] | length'
# Expect: 0

# Flip back:
curl -s -X PATCH $BASE/api/v1/admin/menu/items/$CAPPUCCINO_ITEM_ID/availability \
  -H "Authorization: Bearer $BARISTA_TOKEN" -H 'Content-Type: application/json' \
  -d '{"available":true}' | jq '{available, availability}'
# Expect: {"available":true,"availability":"available"}
```

Unavailable items must NOT be addable to cart (422 from `/cart/items`).

### 4.6 RBAC confirmations for barista

```bash
curl -s -o /dev/null -w "%{http_code}\n" $BASE/api/v1/admin/stats \
  -H "Authorization: Bearer $BARISTA_TOKEN"            # 403
curl -s -o /dev/null -w "%{http_code}\n" $BASE/api/v1/admin/promocodes \
  -H "Authorization: Bearer $BARISTA_TOKEN"            # 403
curl -s -o /dev/null -w "%{http_code}\n" $BASE/api/v1/admin/users \
  -H "Authorization: Bearer $BARISTA_TOKEN"            # 403
curl -s -o /dev/null -w "%{http_code}\n" $BASE/api/v1/admin/settings \
  -H "Authorization: Bearer $BARISTA_TOKEN"            # 403
# Barista is read-only on menu categories/items, write is admin-only:
curl -s -o /dev/null -w "%{http_code}\n" -X POST $BASE/api/v1/admin/menu/items \
  -H "Authorization: Bearer $BARISTA_TOKEN" -H 'Content-Type: application/json' \
  -d '{"category_id":1,"name_ru":"x","name_en":"x"}'    # 403
```

---

## §5 FLOW: Admin promocode lifecycle

This is the deepest admin-only flow — full clickthrough with validation and state machine.

### 5.1 Create — percent (happy path)

**UI.** Admin login → sidebar "Promos" → `/admin/promos`. Empty state first time; "Создать" / "Create" opens a dialog.

Fill:
- code `QA15` (server upper-cases anyway)
- type = percent, value = 15
- valid_from (leave empty — defaults to now)
- valid_until = tomorrow
- max_uses = 5, max_uses_per_user = 2

Submit → dialog closes, table row appears with chip "INACTIVE" (promos start inactive).

### 5.2 Create — fixed (rubles ↔ kopecks)

Create `SAVE100`, type fixed, value 100, min_order 500. DevTools → Network: request body's `discount_value=10000` and `min_order_amount=50000` — the UI converts. Table column renders "100 ₽".

### 5.3 Validation matrix (expect 422 on all)

Each of these keeps the dialog open:

| Input | Expected error |
|-------|---------------|
| code = `qa 10` (space) | pattern violation |
| code = `кир` (cyrillic) | pattern violation |
| percent value = 150 | "percent ≤ 100" |
| fixed value = 0 | "> 0 required" |
| valid_from > valid_until | "must be strictly before" |
| max_uses_per_user > max_uses | "per_user ≤ max_uses" |
| duplicate code `QA15` | **409** `promocode_code_conflict` |

### 5.4 State filter tabs

Tabs: All / Active / Inactive / Expired / Exhausted. Each sets `?state=<value>` on the list call. `state` is **server-computed** on every response — don't rely on cached client state.

To see "Expired": create a promo with `valid_until = now + 60 s`, wait, refresh, click Expired tab. To see "Exhausted": create with `max_uses = 1`, use it once via §5.7, refresh.

### 5.5 Activate / Deactivate

- Activate without `valid_until` → 422 `valid_until required`. Fix, retry.
- Activate an EXPIRED promo → 409 `promocode expired`.
- Deactivate an EXPIRED promo → 409 `promocode expired` (refusal is symmetric).
- Activate a live promo → chip flips green "ACTIVE".

### 5.6 Locked fields after first use

Once a promo has `current_uses > 0`, fields `code`, `discount_type`, `discount_value` freeze. UI disables them; server returns 422 `field_locked_after_use` on raw PATCH:

```bash
curl -s -X PATCH $BASE/api/v1/admin/promocodes/$PROMO_ID \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H 'Content-Type: application/json' \
  -d '{"discount_value":50}' | jq .detail
# Expect: [{"type":"field_locked_after_use","field":"discount_value"}]
```

Unfrozen fields (`max_uses`, `max_uses_per_user`, `valid_until`, `min_order_amount`, `is_active`) keep patching fine.

### 5.7 Apply at checkout — atomic current_uses

See §2.5 for the customer side. After each successful order:

```bash
curl -s "$BASE/api/v1/admin/promocodes" -H "Authorization: Bearer $ADMIN_TOKEN" \
  | jq '.items[] | select(.code=="QA15") | {current_uses, max_uses, state}'
```

`current_uses` increments by exactly 1 per order. The atomic guarantee is the conditional UPDATE in `services/checkout.py` — racing two browsers can't overshoot `max_uses`. The race proper is covered by `test_promocode_atomic_increment.py`; what you **can** exercise manually is the rejection:

- Create a code with `max_uses=1` and `max_uses_per_user=1`.
- Use it once (works).
- Retry same customer → 409 `Per-user quota exhausted`.
- Second customer retry → 409 `Global quota exhausted` (because max_uses=1).

### 5.8 Promocode decrement on cancel

Create an order with `qa15`, wait for `paid`, then admin-cancel (`/admin/orders` → detail → "Отменить"). `current_uses` decrements by 1, floored at 0 (`WHERE current_uses > 0` guard). Double-cancel is impossible through the state machine (second call returns 409 invalid transition) — DB-level decrement is already idempotent.

---

## §6 FLOW: Courier delivers an order

Needs §4.4 complete — a delivery order in status `ready` with a corresponding `delivery_assignment` in `awaiting_courier`. Use the `ASG_ID` exported in §4.4, or derive it again from `DEL_ORDER_ID` below.

### 6.1 Courier login — no sidebar

**UI.** Open a **third** private-window. Log in as `courier` / `courier123`. SPA lands on `/admin/courier` — the **CourierShell**, not the general Layout. No sidebar. Header shows phone/logout only.

Manually typing `/admin/` (dashboard) bounces back — `ProtectedRoute` rejects the courier role from the admin Layout route.

### 6.2 Available assignments list

**UI.** `/admin/courier` shows an "Available" list. The delivery order from §4.4 appears with timing/total metadata. Full address details are redacted until the courier takes the assignment; after take, they appear in the courier's "Mine" view.

**API.**

```bash
curl -s $BASE/api/v1/courier/assignments/available \
  -H "Authorization: Bearer $COURIER_TOKEN" \
  | jq --arg oid "$DEL_ORDER_ID" 'map(select(.order_id==$oid)) | .[0] | {id, order_id, status, total}'
# Expect: the DEL_ORDER_ID row exists and status is "awaiting_courier".
```

### 6.3 Take → Pickup → Deliver

**UI buttons** match the assignment state:

```
awaiting_courier  → [Взять] → COURIER_ASSIGNED
COURIER_ASSIGNED  → [Забрал] → PICKED_UP         (order.status becomes "in_delivery")
PICKED_UP         → [Доставил] → DELIVERED       (order.status becomes "completed")
```

**API.**

```bash
ASG_ID=${ASG_ID:-$(curl -s $BASE/api/v1/courier/assignments/available \
  -H "Authorization: Bearer $COURIER_TOKEN" \
  | jq -r --arg oid "$DEL_ORDER_ID" 'map(select(.order_id==$oid))[0].id')}

curl -s -X POST $BASE/api/v1/courier/assignments/$ASG_ID/take \
  -H "Authorization: Bearer $COURIER_TOKEN" | jq .status
# → "courier_assigned"

curl -s -X POST $BASE/api/v1/courier/assignments/$ASG_ID/pickup \
  -H "Authorization: Bearer $COURIER_TOKEN" | jq .status
# → "picked_up"

curl -s -X POST $BASE/api/v1/courier/assignments/$ASG_ID/deliver \
  -H "Authorization: Bearer $COURIER_TOKEN" | jq .status
# → "delivered"

# Order now reflects the final state
curl -s $BASE/api/v1/orders/$DEL_ORDER_ID -H "Authorization: Bearer $CUST_TOKEN" \
  | jq .status
# → "completed"
```

### 6.4 Mine-list & conflict cases

- `GET /api/v1/courier/assignments/mine` — shows assignments where *this* courier is assigned.
- **Double-take.** Call `/take` on an already-taken assignment → 409. The seed already includes `courier2` / `courier2123` if you want to log in as a second courier; do not insert ad hoc staff rows.
- **Out-of-order.** `/deliver` before `/pickup` → 409 invalid transition.
- **Cancel while assigned but not picked up.** Admin-cancels a `ready` order with a `courier_assigned` assignment → assignment becomes `cancelled` and drops off `mine`.
- **Cancel after pickup.** Once the courier has picked up the order (`in_delivery`), admin cancellation is rejected by the order state machine.

### 6.5 RBAC for courier

```bash
# courier can only see their own endpoints
for path in admin/stats admin/orders admin/users admin/promocodes admin/menu/items \
            admin/settings profile cart; do
  code=$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $COURIER_TOKEN" \
         "$BASE/api/v1/$path")
  echo "$path → $code"
done
# Expect: everything 403 (or 401/403 per role matrix) — none 200.
```

---

## §7 FLOW: Admin dashboard, users, settings, loyalty adjust

Single admin actor — all reads live on the admin SPA under the six sidebar tabs.

### 7.1 Dashboard stats

**UI.** `/admin/` (dashboard). Shows: today's revenue, order count, popular items list, a date-range selector.

**API.**

```bash
curl -s $BASE/api/v1/admin/stats -H "Authorization: Bearer $ADMIN_TOKEN" | jq .
# Keys: orders_count, revenue_kopecks, popular_items, range, range_start, range_end
```

Switch the range selector to "7 days" / "30 days" — request is refetched with `?range=…`. Confirm `revenue_kopecks` counts only orders in `completed` / `paid` states (cancelled orders excluded).

### 7.2 Users list & detail

**UI.** `/admin/users`. Paginated list of customers (NOT staff). Each row shows masked phone (`+7999***4567`), name, block status, loyalty balance. Clicking a row opens detail: order history count, last order date, loyalty balance, block/unblock button, loyalty-adjust button.

**API.**

```bash
curl -s "$BASE/api/v1/admin/users?per_page=10" -H "Authorization: Bearer $ADMIN_TOKEN" \
  | jq '{total_count, items: (.items | map({id, phone_masked, name, is_blocked, loyalty_balance}))}'
# Note key is .items (unlike /admin/orders which uses .orders)

USER_ID=${QA_CUSTOMER_ID:-$(curl -s $BASE/api/v1/admin/users -H "Authorization: Bearer $ADMIN_TOKEN" \
  | jq -r '.items[] | select(.name=="QA Customer" or .name=="QA Tester") | .id' \
  | head -n1)}
curl -s $BASE/api/v1/admin/users/$USER_ID -H "Authorization: Bearer $ADMIN_TOKEN" | jq .
```

### 7.3 Block / unblock

**UI.** Detail → "Заблокировать". Toast, row gains a red badge. Blocking also revokes the customer's refresh sessions. While blocked, `send-code` / token refresh are refused and existing access tokens are treated as invalid on protected endpoints.

**API.**

```bash
curl -s -X POST $BASE/api/v1/admin/users/$USER_ID/block \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq .status
# "blocked"

# Existing customer access token is refused on protected endpoints
curl -s -o /dev/null -w '%{http_code}\n' $BASE/api/v1/profile \
  -H "Authorization: Bearer $CUST_TOKEN"
# Expect: 401 (blocked subjects are treated as invalid/expired JWT subjects)

# New OTP requests are refused while blocked
curl -s -o /dev/null -w '%{http_code}\n' -X POST $BASE/api/v1/auth/send-code \
  -H 'Content-Type: application/json' -d "{\"phone\":\"$PHONE\"}"
# Expect: 403

curl -s -X POST $BASE/api/v1/admin/users/$USER_ID/unblock \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq .status
# "active"
```

After unblock, re-run §0.4 to get a fresh `CUST_TOKEN`; the old session was intentionally revoked.

### 7.4 Shop settings edit

**UI.** `/admin/settings`. Single form:

| Field | Typical value |
|-------|--------------|
| Working hours | Mon–Sun 08:00–22:00 |
| Default prep time (min) | 10 |
| Auto-close minutes (unclaimed pickup) | 30 |
| Delivery fee (₽) | 150 |
| Free delivery threshold (₽) | 1500 |
| Min delivery amount (₽) | 500 |
| Delivery radius (km) | 10 |
| Estimated delivery time (min) | 45 |
| Loyalty accrual (%) | 5 |
| Shop lat / lon | 55.75 / 37.62 |

Save → PUT returns the full updated row → subsequent customer checkouts pick up new values (e.g., raise `min_delivery_amount` to 10000 ₽ and watch `/checkout` with a small cart reject — exercise from customer UI).

**API.**

```bash
curl -s -X PUT $BASE/api/v1/admin/settings \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H 'Content-Type: application/json' \
  -d '{"delivery_fee":20000,"min_delivery_amount":100000,"loyalty_percent":7}' \
  | jq '{delivery_fee, min_delivery_amount, loyalty_percent}'
```

### 7.5 Manual loyalty adjust (admin-credit / admin-debit)

**UI.** User detail → "Начислить баллы" / "Списать баллы" dialog. Enter amount (positive = credit, negative = debit), description, submit. The user's `loyalty_accounts.balance` changes; a row with `type=admin_adjustment` appears in their `loyalty_transactions` (visible on the customer's `/profile/loyalty` page).

**API.**

```bash
curl -s -X POST $BASE/api/v1/admin/users/$USER_ID/loyalty/adjust \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H 'Content-Type: application/json' \
  -d '{"amount":50,"description":"QA manual credit"}' \
  | jq '{new_balance, transaction_id}'

# Cross-check from customer view
curl -s $BASE/api/v1/profile/loyalty/transactions \
  -H "Authorization: Bearer $CUST_TOKEN" \
  | jq '.items[] | select(.type=="admin_adjustment")'
```

Negative amount works symmetrically. Debiting below 0 → 422 `insufficient_balance`.

### 7.6 Customer loyalty cross-check (all at once)

After completing §2 + §3 + §7.5, the customer's `/profile/loyalty` page should show:

- Big balance number = sum of all transactions.
- `lifetime_accrued` = sum of positive non-reversal rows.
- History: at least one `accrual` (from completed order), possibly one `admin_adjustment`.
- Click `Загрузить ещё` if count > 20 — appends page 2.

---

## §8 FLOW: Cancellation & refund paths

Focused negative-path flow. Pre-state: at least one `paid` pickup order, one `paid` delivery order with assignment.

### 8.1 Customer cancels paid pickup → refund

```bash
# create + wait for paid
curl -s -X DELETE $BASE/api/v1/cart -H "Authorization: Bearer $CUST_TOKEN" > /dev/null
curl -s -X POST $BASE/api/v1/cart/items \
  -H "Authorization: Bearer $CUST_TOKEN" -H 'Content-Type: application/json' \
  -d "{\"menu_item_id\":$CAPPUCCINO_ITEM_ID,\"size_option_id\":$CAPPUCCINO_SIZE_M_ID,\"quantity\":1}" > /dev/null
OID=$(curl -s -X POST $BASE/api/v1/orders \
  -H "Authorization: Bearer $CUST_TOKEN" -H 'Content-Type: application/json' \
  -d '{"type":"pickup"}' | jq -r .id)
sleep 3  # paid by fake-yukassa

curl -s -X POST $BASE/api/v1/orders/$OID/cancel \
  -H "Authorization: Bearer $CUST_TOKEN" -H 'Content-Type: application/json' \
  -d '{"reason":"customer_decision"}' | jq .status
# Expect: "cancelled"
```

`payment-worker` logs:

```
INFO Task create_refund[...] received
INFO Task yukassa_fake_callback[...]  # refund.succeeded
INFO refund succeeded for order <id>
```

`GET /api/v1/orders/$OID` shows `status=cancelled`, `payment.status=refunded`.

### 8.2 Admin cancels delivery mid-stream

Need a delivery order (§3). Drive it to `paid` (sleep 3). Admin cancellation is allowed before pickup (`paid`, `preparing`, or `ready`):

```bash
curl -s -X POST $BASE/api/v1/orders/$DEL_ORDER_ID/cancel \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H 'Content-Type: application/json' \
  -d '{"reason":"admin_decision"}' | jq '{status, payment: .payment.status}'
```

If the barista already moved it to `preparing`, the delivery assignment exists. If it is still `awaiting_courier` or `courier_assigned`, cancellation marks that assignment `cancelled` and removes it from courier feeds:

```bash
curl -s $BASE/api/v1/courier/assignments/available \
  -H "Authorization: Bearer $COURIER_TOKEN" \
  | jq --arg oid "$DEL_ORDER_ID" 'map(select(.order_id==$oid)) | length'
# Expect: 0
```

If the courier already picked up the order (`in_delivery`), admin cancellation is rejected; the courier must complete the delivery flow.

### 8.3 Promocode symmetric refund

From §5.8. Order with promocode `qa15`, `current_uses` at N → cancel → `current_uses` at N−1. Re-issue same promo on a new order → accepted (quota restored).

### 8.4 Loyalty reversal

If an order accrued loyalty (reached `completed`) and is then refunded via a compensating flow (rare — typically only happens for the order-repeat + cancel edge), a `reversal` row appears with a negative amount equal to the prior accrual. Phase 6 seldom produces this interactively; covered by `test_order_cancel*.py`.

### 8.5 YuKassa negative outcomes

Set `YUKASSA_FAKE_OUTCOME=canceled` → force-recreate core-api + payment-worker (see §0.5 for the exact command). Create a new order. Watch: order flips to `payment_failed` or `cancelled` (depending on version), not `paid`. Flip back to `success` before continuing other flows.

Set `YUKASSA_FAKE_OUTCOME=http_error`. New order → `payment-worker` logs show retry/backoff, eventually compensating by cancelling the order. The customer SPA surfaces a "Payment failed, please retry" toast (or equivalent). Restore `success` when done.

---

## §9 Cross-role RBAC smoke (API-only)

Single-pass table. Run after §0.4. Expected status is the **first** listed code; the others are documentation of what's legitimately accessible for other roles.

```bash
# Encode each expected-access row once
declare -A EXPECT=(
  # customer-only
  ["GET /api/v1/profile"]="customer=200 admin=403 barista=403 courier=403 noauth=401"
  ["GET /api/v1/profile/loyalty"]="customer=200 admin=403 barista=403 courier=403 noauth=401"
  ["GET /api/v1/profile/addresses"]="customer=200 admin=403 barista=403 courier=403 noauth=401"
  ["GET /api/v1/cart"]="customer=200 admin=403 barista=403 courier=403 noauth=401"
  ["POST /api/v1/orders"]="customer=4xx admin=403 barista=403 courier=403 noauth=401"
  ["GET /api/v1/maps/suggest?text=foo"]="customer=YANDEX admin=403 barista=403 courier=403 noauth=401"
  # admin-only
  ["GET /api/v1/admin/stats"]="admin=200 barista=403 courier=403 customer=403 noauth=401"
  ["GET /api/v1/admin/users"]="admin=200 barista=403 courier=403 customer=403 noauth=401"
  ["GET /api/v1/admin/promocodes"]="admin=200 barista=403 courier=403 customer=403 noauth=401"
  ["GET /api/v1/admin/settings"]="admin=200 barista=403 courier=403 customer=403 noauth=401"
  # admin + barista
  ["GET /api/v1/admin/orders"]="admin=200 barista=200 courier=403 customer=403 noauth=401"
  ["GET /api/v1/admin/menu/items"]="admin=200 barista=200 courier=403 customer=403 noauth=401"
  # courier-only
  ["GET /api/v1/courier/assignments/available"]="courier=200 admin=403 barista=403 customer=403 noauth=401"
  ["GET /api/v1/courier/assignments/mine"]="courier=200 admin=403 barista=403 customer=403 noauth=401"
  # public
  ["GET /api/v1/menu"]="customer=200 admin=200 barista=200 courier=200 noauth=200"
  ["GET /health"]="customer=200 admin=200 barista=200 courier=200 noauth=200"
)

probe() {
  local method="$1"; local path="$2"; local role="$3"
  local token
  case "$role" in
    admin)   token="$ADMIN_TOKEN";;
    barista) token="$BARISTA_TOKEN";;
    courier) token="$COURIER_TOKEN";;
    customer)token="$CUST_TOKEN";;
    noauth)  token="";;
  esac
  if [ -n "$token" ]; then
    curl -s -o /dev/null -w '%{http_code}' -X "$method" "$BASE$path" \
      -H "Authorization: Bearer $token"
  else
    curl -s -o /dev/null -w '%{http_code}' -X "$method" "$BASE$path"
  fi
}

for row in "${!EXPECT[@]}"; do
  method="${row%% *}"; path="${row#* }"
  echo "── $row"
  for r in admin barista courier customer noauth; do
    c=$(probe "$method" "$path" "$r")
    printf "    %-9s → %s\n" "$r" "$c"
  done
done
```

Scan the output against the `EXPECT` map. Any row where the first-expected role's code differs from the observed code is a regression.

---

## §10 Known gaps / out-of-scope

- **Customer promocode input in cart/checkout** — no UI field yet. `promocode_code` is accepted on the order-create API (§2.5) but the SPA does not expose it. Planned for a later phase.
- **Menu media binary workflow** — the admin form edits `media_type`, `media_url`, `media_poster_url`, and legacy `image_url` only. It does not upload files or verify that a referenced static asset exists. Preparing/committing product media remains a content/deploy step.
- **Seeded media paths are references only** — the seed points `Капучино (QA)` at `/media/menu/cappuccino-qa/*`, but missing local binaries should degrade gracefully. Do not commit ad hoc QA media unless those files are approved product assets.
- **Barista realtime feed** — orders table refreshes on poll / manual click, not push. New-order sound / badge is out of scope.
- **`ADMIN_ADJUSTMENT` UI on customer page** — the row appears in `/profile/loyalty` history but has no link (no owning order). Intentional.
- **YuKassa real backend** — `YUKASSA_BACKEND=live` requires production credentials; `services/payment-worker/src/payment_worker/main.py` refuses to start if `YUKASSA_BASE_URL` contains "test" / "sandbox" / "localhost" when `live` is set. Do not attempt to flip it during manual QA.
- **Yandex activation delay** — new free-tier keys can take up to ~15 min to propagate. If §0.5 shows 403 but you just issued the key, retry later. If persistent, check that both "Геокодер HTTP API" and "Геосаджест API" are activated in the developer cabinet — they are separate subscriptions.
- **Address edit coordinates** — saved-address PATCH intentionally does not accept `lat` / `lon`; changing coordinates is a delete/create flow until the product adds an explicit re-geocode edit path.

---

## §Appendix A — Common failure signatures

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `/api/v1/auth/verify-code` returns 409 `OTP not yet delivered` immediately after send | SMS worker has not flipped Redis status to `sent` yet | wait/poll as in §0.4; check `sms-worker` logs |
| `/api/v1/auth/verify-code` returns 401 wrong code / too many attempts | OTP already consumed or wrong code submitted | §0.7 reset and re-run §0.4 |
| `/api/v1/auth/send-code` returns 429 | `sms_rate:*` counters full | `redis-cli DEL` those keys |
| Customer checkout hangs on "creating order" | `payment-worker` unhealthy or `YUKASSA_FAKE_OUTCOME=http_error` left active | check logs; reset env var |
| `/api/v1/admin/stats` returns 500 | no orders in DB and the aggregate query hit a NULL path | create at least one `paid` order |
| Admin sidebar shows all 6 links for barista | phase 5.5 fix didn't land; `Layout.tsx NAV_BY_ROLE` missing | compare against current `web/admin/src/components/Layout.tsx` |
| Delivery assignment row exists but is absent from courier available feed | order is still `preparing` | PATCH `/orders/$ID/status` with `ready` |
| `/api/v1/maps/suggest` → 500 `yandex_upstream_error` with key set | key not activated / wrong product | §0.5; verify both APIs enabled in Yandex cabinet |
| `/api/v1/maps/suggest` → 503 `maps_unavailable` | key empty, timeout, or 5xx from Yandex | check `.env` + network |
| Admin menu media save returns 422 | Path outside `/media/menu/`, missing poster for video, wrong extension, or signed/external URL | use the §2.1-A validation matrix |
| Customer menu media area is blank | No media fields and no legacy `image_url`, or both video and poster assets 404 | set media in §2.1-A and verify `curl -I` from §0.3-B |
| Video does not autoplay | Browser reduced-motion setting, video not in viewport yet, or unsupported/invalid video file | check DevTools media emulation and use a small `.mp4`/`.webm` |
| Tokens suddenly 401 after some time | JWT TTL expired, or §7.3 blocked/revoked the customer session | re-run §0.4 token block after unblocking |
| `docker compose ps` shows `db-migrate` / `db-seed` as `Exited` | expected — one-shot jobs | nothing to do |

---

## §Appendix B — Useful one-liners

```bash
# pull live OTP
PH=$(echo -n "+79991234567" | sha256sum | cut -d' ' -f1)
docker compose exec -T redis redis-cli GET "otp:$PH" | jq -r .code

# order snapshot (all of them)
curl -s "$BASE/api/v1/admin/orders?per_page=100" -H "Authorization: Bearer $ADMIN_TOKEN" \
  | jq '.orders[] | {id: .id[:8], status, type, total, created_at}'

# promo snapshot
curl -s "$BASE/api/v1/admin/promocodes?per_page=100" -H "Authorization: Bearer $ADMIN_TOKEN" \
  | jq '.items[] | {code, state, is_active, current_uses, max_uses}'

# current QA menu media contract
curl -s "$BASE/api/v1/menu" \
  | jq '.categories[].items[] | select(.name_ru=="Капучино (QA)") |
        {id, media_type, media_url, media_poster_url, image_url, available}'

# reset QA menu media fields to the legacy/no-media state
ITEM_ID=$(curl -s "$BASE/api/v1/admin/menu/items" -H "Authorization: Bearer $ADMIN_TOKEN" \
  | jq -r 'map(select(.name_ru=="Капучино (QA)"))[0].id')
curl -s -X PUT "$BASE/api/v1/admin/menu/items/$ITEM_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H 'Content-Type: application/json' \
  -d '{"media_type":null,"media_url":null,"media_poster_url":null}' \
  | jq '{media_type, media_url, media_poster_url}'

# courier inbox (both lists)
for kind in available mine; do
  echo "── $kind"
  curl -s $BASE/api/v1/courier/assignments/$kind -H "Authorization: Bearer $COURIER_TOKEN" \
    | jq 'length // (.|tostring[:80])'
done

# full user state for one customer
curl -s $BASE/api/v1/profile -H "Authorization: Bearer $CUST_TOKEN" | jq .
curl -s $BASE/api/v1/profile/loyalty -H "Authorization: Bearer $CUST_TOKEN" | jq .
curl -s $BASE/api/v1/profile/addresses -H "Authorization: Bearer $CUST_TOKEN" | jq 'length'

# force a paid pickup order end-to-end in one shot
curl -s -X DELETE $BASE/api/v1/cart -H "Authorization: Bearer $CUST_TOKEN" > /dev/null
curl -s -X POST $BASE/api/v1/cart/items -H "Authorization: Bearer $CUST_TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"menu_item_id\":$CAPPUCCINO_ITEM_ID,\"size_option_id\":$CAPPUCCINO_SIZE_M_ID,\"quantity\":1}" > /dev/null
OID=$(curl -s -X POST $BASE/api/v1/orders -H "Authorization: Bearer $CUST_TOKEN" \
  -H 'Content-Type: application/json' -d '{"type":"pickup"}' | jq -r .id)
echo "order=$OID"; sleep 3
curl -s $BASE/api/v1/orders/$OID -H "Authorization: Bearer $CUST_TOKEN" | jq .status
```
