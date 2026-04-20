# Phase 3 — Manual UI clickthrough

Goal: a fresh operator opens Chrome, clicks through every user-facing flow that exists today, and observes the expected outcome. Backend logic (payments, webhooks, state machine) is covered by the automated suite — see Section 3 for what is intentionally out of scope here.

## Pre-flight

1. Bring the stack up from the repo root:

   ```
   ./scripts/up.sh
   ```

   Wait for the banner line `Migrations: applied ✓`. If it says `FAILED`, stop and run `docker compose logs db-migrate`.

2. Note the two URLs `up.sh` prints. They depend on `.env` (ports are bumped per worktree by `scripts/setup-worktree-env.sh`):

   - Customer SPA: `http://localhost:${NGINX_PORT}/`
   - Admin SPA:    `http://localhost:${NGINX_PORT}/admin/`

   If you lose them: `grep NGINX_PORT .env`. On this worktree the port is usually `8260`.

3. Open a second terminal for logs (keep running throughout the session):

   ```
   docker compose logs -f sms-worker
   ```

   All OTP codes and order notifications appear here as `[SMS:log] to=<phone> msg=<text>`. The dev stack does not send real SMS.

4. Reset between runs (wipes DB, Redis, uploaded images):

   ```
   ./scripts/down.sh && ./scripts/up.sh
   ```

---

## Section 1 — Customer

Open the Customer SPA in Chrome. All steps below are clicks in the browser.

### 1.1 Login — happy path

1. Land on `/` — if unauthenticated, you are redirected to `/login`.
2. Phone input is prefilled with `+7`. Type `9991234567`. The "Продолжить" / "Continue" button enables only once the phone is valid.
3. Click the button. You land on `/login/verify`.
4. Switch to the `sms-worker` log tail. The last line is `[SMS:log] to=+79991234567 msg=... <6-digit code> ...`.
5. Type the 6 digits into the OTP input. The form auto-submits on the sixth digit.
6. Expected: you land on `/` (the menu/home). Refresh the page — you stay logged in (token persisted).

### 1.2 Login — error paths

Each of these starts from step 3 of 1.1 (on `/login/verify`).

- **Wrong code.** Type six wrong digits. Expected: red error "Неверный код" / "Invalid code", inputs reset, focus returns to the first cell.
- **Resend timer.** The "Отправить снова" / "Resend" button shows a countdown (e.g. `0:30`) and is disabled until it reaches zero. Click it once enabled → a new `[SMS:log]` line appears; the old code becomes invalid.
- **Expired code.** Request a code, wait past its TTL (log the time; default ~5 min — skip this one if you don't want to wait), then enter it. Expected: error "Код истёк" / "Code expired".
- **Rate limit.** Submit six wrong codes in a row. Expected: error changes to "Слишком много попыток" / "Too many attempts"; form disabled.
- **No phone in state.** Open `/login/verify` directly in a new tab without going through `/login` first. Expected: redirect back to `/login`.

### 1.3 Browse menu

1. Navigate to `/menu` (via nav or direct URL).
2. Expected: a skeleton grid flashes, then categories render as sections ("Напитки", "Десерты", …). Each section contains item cards with photo, name, and the cheapest size's price.
3. Toggle language to English via the language switcher. Category and item names switch; prices stay the same (formatted with `en` locale separators).
4. Empty category: if a category has `is_visible=true` but no items, its section is rendered with the localized "Нет позиций" / "No items" placeholder.
5. If the network drops (pause the `nginx` container: `docker compose pause nginx`), click "Retry" on the error state. Unpause with `docker compose unpause nginx` and click Retry again — menu loads.

### 1.4 Item detail modal

1. Click any item card on `/menu`. A modal opens with the full description, all sizes, and all linked modifier groups.
2. Sizes render as pill buttons. The unavailable ones (`is_visible=false` or stop-listed) are disabled and visibly muted.
3. Click a different size. The total price in the footer updates to `size.price`.
4. Toggle modifier checkboxes (multi-select per group). The total updates to `size.price + sum(selected modifier prices)`.
5. Click "Добавить в корзину" / "Add to cart". Expected: green toast (`menu.added`), modal auto-closes after ~800 ms.
6. Re-open the same item. The modal resets to defaults — previous selections are not sticky.

### 1.5 Cart

1. Navigate to `/cart`. If empty: muted text + CTA "В меню" / "Go to menu" that links to `/menu`.
2. After adding at least one item from 1.4: each line shows name, chosen size label, joined modifier names, a `−` / `+` stepper, a `✕` remove button, and the line total.
3. Click `+`: quantity increments, line total updates, subtotal at the bottom updates. Continue to 99 — the `+` button disables at 99.
4. Click `−`: quantity decrements. When quantity is 1, clicking `−` removes the line entirely.
5. Click `✕`: line removed immediately.
6. Click "Очистить корзину" / "Clear cart" (top right). All lines gone, empty state returns.
7. **Expired cart.** Leave the cart tab open overnight (or manually delete the cart Redis key: `docker compose exec redis redis-cli DEL "cart:$USER_ID"`). Next `+`/`−`/`✕` click shows the amber "Корзина устарела" / "Cart expired" toast and refreshes to the current server state.

### 1.6 Profile

1. Navigate to `/profile`. The phone number is shown masked (read-only).
2. Change the display name field and click "Сохранить" / "Save". Expected: button briefly disabled, success implicit (name stays filled, Save re-disables because nothing changed since the last save).
3. Try name = `""` → red error "Имя обязательно" / "Name is required". Try name > 100 chars → "Слишком длинное" / "Too long".
4. Click the opposite language pill (Русский ↔ English). The whole SPA text switches instantly; the switch also persists (reload the page, language sticks).
5. Click "Выйти" / "Logout". Expected: redirect to `/login`; opening `/profile` now redirects back to `/login`.

---

## Section 2 — Admin

Open the Admin SPA in Chrome (`/admin/` — note the trailing slash; `/admin` issues a 301).

### 2.1 Login

1. Land on `/admin/`; unauthenticated → redirect to `/admin/login`.
2. Enter `login = admin`, `password = admin123`. Click submit.
3. Expected: redirect to `/admin/` (dashboard stub with just a heading). Token persists in `localStorage` under key `accessToken`.
4. **Wrong password.** Log out (clear `accessToken` via DevTools), re-open `/admin/login`, submit `admin` / `wrong`. Expected: red error "Неверные учётные данные" / "Invalid credentials"; the form stays filled.
5. **Disabled state.** Empty either field → submit button disabled.
6. **Return URL.** Visit `/admin/menu` while logged out. You are redirected to `/admin/login?returnUrl=/menu`. After a successful login you land on `/admin/menu` directly.

### 2.2 Menu → Categories (left column)

Navigate to `/admin/menu`.

1. Enter `name_ru`, `name_en`, pick a type (`drink` / `food` / …), click "Добавить" / "Add". The category appears at the bottom of the list and is selected.
2. Click the pencil icon on an existing row. Inline fields become editable: name_ru, name_en, type, sort_order. Change `sort_order`, click save — list reorders.
3. Click the trash icon. Expected: browser confirm dialog → on confirm, the category disappears. If the category still holds items, the backend returns 409 and a red error toast is shown (category stays).
4. **Validation.** Empty `name_ru` or `name_en` disables "Add". Submit with a too-long name → 422 → toast shows which fields failed.
5. **Session expiry.** Delete `accessToken` from `localStorage` and click "Add". Expected: red toast "Сессия истекла" / "Session expired" and the app does not silently fail.

### 2.3 Menu → Items (center column)

Select a category in the left column; the center table filters to that category.

1. Click "Добавить позицию" / "Add item". The `MenuItemFormDialog` opens.
2. Fill: `name_ru`, `name_en`, `description_ru`, `description_en`, category dropdown (preselected), and — in the "Размеры" / "Sizes" editor — add at least one size row (label, price in the minor currency unit). You cannot save with zero sizes.
3. In the "Модификаторы" / "Modifiers" picker, check one or more existing modifiers. Save.
4. The new row appears in the table with name, cheapest-size price, and availability badge.
5. **Edit.** Click the pencil icon → same dialog pre-filled. Change one size's price, save → the table's price column updates.
6. **Availability toggle.** The row's switch flips `available` ↔ `stop_list`. Flip to stop-list → a yellow "Stop-list" badge appears. Flip to `archived` via the form's dropdown → the row shows a muted "Archived" badge.
7. **Stop-listed items in customer SPA.** Reload `/menu` in the customer tab → the item still renders, but on the item modal its sizes (or the whole item) are disabled per 1.4.
8. **Delete.** Trash icon → browser confirm → item row vanishes.

### 2.4 Menu → Modifiers (bottom section)

Scrolled to the bottom of `/admin/menu`.

1. Add a modifier: `name_ru`, `name_en`, `price_delta` (signed, minor units). Save.
2. Edit an existing modifier's price_delta → save → item totals that reference it update immediately in 1.4 next time the modal is opened.
3. Delete a modifier. If it's linked to any item, expect a 409 and a red toast; otherwise it disappears.

---

## Section 3 — Known UI gaps (intentionally out of scope here)

These flows exist in the backend and are covered by automated tests, but they have no clickable UI yet. Do not try to test them through Chrome — you will hit placeholder pages.

- **Checkout.** `/checkout` in the customer SPA is a 12-line stub (`<h1>` + description only). Placing a real order, paying via ЮKassa, and observing payment status is a backend-only flow today.
- **Customer order history.** `/orders` is a stub. Same for repeat-order and cancel-order actions.
- **Admin orders.** `/admin/orders` is a stub. No barista queue, no order-status transitions, no refund UI.
- **Admin users / promos / settings / dashboard.** All four are 12-line stubs. Loyalty balance, promocode management, and per-role settings cannot be exercised via Chrome.
- **Barista & Courier personas.** There is no dedicated SPA for them. The admin Menu page reads role via `useCurrentRole()` in `web/admin/src/pages/Menu/index.tsx:12`, which is hardcoded to `'admin'` (see the TODO in that file). "Log in as barista" through `/admin/login` works, but the resulting UI is identical to an admin session, so it is not yet a distinct test persona.

If you need to exercise any of the above today, use the automated `pytest` suite (`services/core-api`, `services/payment-worker`) or the pre-existing API runbooks in `docs/` — not this document.

---

## Appendix — Logs cheatsheet

Run in a separate terminal. `-f` follows new lines.

```
docker compose logs -f sms-worker         # OTP codes + order notifications ([SMS:log] lines)
docker compose logs -f core-api           # HTTP errors from the SPA (401, 422, 500)
docker compose logs -f payment-worker     # ЮKassa fake callbacks, webhook delivery
docker compose logs -f nginx              # routing issues (404s, bad upstream)
```

Common failure signatures:

- **Blank page in Chrome, DevTools shows a network error to `/api/...`** → core-api is down. `docker compose ps core-api`; if `Exited`, tail its log.
- **Login succeeds but the next page 401s immediately** → the `accessToken` in `localStorage` is from a previous `./scripts/down.sh` run and the user was wiped. Log out → log in again.
- **OTP never appears in sms-worker log** → check that `SMS_BACKEND=log` in `.env` (it is the dev default). If it is `kannel` or unset, change to `log` and `docker compose up -d sms-worker`.
- **`/admin/` responds with the customer SPA** → Nginx routed to the wrong upstream; `docker compose restart nginx web-admin` and reload.
