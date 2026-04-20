## Why

PDD §4.4 требует клиентский UI для оформления доставки: автокомплит адреса через Яндекс.Карты Suggest API, управление сохранёнными адресами в профиле и выбор адреса в checkout. В текущем состоянии `CheckoutPage.tsx` — это заглушка, страницы адресов в профиле нет, а серверная валидация радиуса (§7.3 шаг 3) уже есть (Phase 3), но фронт не умеет её вызвать с реальным адресом. Это блокирует Phase 4 (§7.1) — оформление заказов с `type = DELIVERY`.

## What Changes

- Добавить компонент `AddressAutocomplete` в `web/customer/src/components/AddressAutocomplete/`: input с выпадающим списком подсказок из `GET /api/v1/maps/suggest`, debounce 300ms, на выбор варианта — `{text, lat, lon}` в form state, bilingual (`lang=ru_RU` | `lang=en_US` из i18n).
- Fallback (§8.3): при HTTP 503 от `/maps/suggest` компонент деградирует в обычный текстовый input без подсказок; координаты получит сервер через Geocoder на submit.
- Добавить страницу `/profile/addresses` (`web/customer/src/pages/Profile/Addresses/`): список сохранённых адресов (`GET /api/v1/profile/addresses`), форма добавления с `AddressAutocomplete` + поля `apartment/entrance/floor/comment/label`, кнопки edit/delete, "Сделать основным".
- Рендерить серверную ошибку радиуса из §7.3 как локализованный текст "Адрес вне зоны доставки (макс. {radius} км)".
- Расширить `CheckoutPage` (из заглушки в минимальную рабочую форму: выбор `type` — PICKUP/DELIVERY — и submit в `POST /api/v1/orders`). При `type = DELIVERY`:
  - Если есть сохранённые адреса — radio-список "Сохранённый адрес", отправлять `delivery_address_id`.
  - Выбор "Новый адрес" — `AddressAutocomplete` + доп. поля, отправлять inline `delivery_address`; чекбокс "Сохранить для следующего заказа".
  - XOR: либо `delivery_address_id`, либо inline `delivery_address`, не оба сразу.
- Добавить API-клиенты: `web/customer/src/api/yandex_maps.ts` (suggest, geocode), `web/customer/src/api/addresses.ts` (list, create, update, delete, set-primary), `web/customer/src/api/orders.ts` (createOrder).
- i18n: добавить ключи в `web/customer/src/i18n/` для RU + EN (form labels, errors, autocomplete placeholder).
- Подключить route `/profile/addresses` в `App.tsx`.

## Non-Goals

- Серверные эндпоинты `/api/v1/maps/*` и `/api/v1/profile/addresses` — реализуются отдельным backend-worktree'ом Phase 4 (§7.1 Phase 4 шаги 1–2). Этот change потребляет их контракт, но не создаёт.
- Курьерский UI (список заказов, взятие, статусы — §6.3). Это Phase 4 шаги 3–4, отдельный change (web-admin).
- Валидация времени доставки (§7.5) — уже есть серверная, клиентская — вне scope (TBD отдельным change'ом).
- Карта с визуальным показом зоны доставки. Только текстовое сообщение об ошибке радиуса.
- Отображение стоимости доставки в реальном времени (Delivery Fee Chain §7.4 — клиент видит итог только после `POST /orders`). Live-preview цены — вне scope.

## MVP Phase

Phase 4 — Delivery (§7.1 Phase 4, шаги 1 frontend consumer и 2).

## Capabilities

### New Capabilities

- `customer-address-autocomplete-ui`: React-компонент `AddressAutocomplete` — debounced-input с dropdown-подсказками, fallback на 503, интеграция с i18n, XOR-сохранение `{text, lat, lon}` в form state.
- `customer-addresses-ui`: Страница `/profile/addresses` — CRUD сохранённых адресов клиента, установка основного, рендер серверных ошибок (радиус, precision).
- `customer-checkout-delivery-ui`: Checkout-форма с выбором `type = PICKUP | DELIVERY` и XOR-ветками "сохранённый адрес" / "новый адрес" (inline + чекбокс "сохранить"), submit в `POST /api/v1/orders`.
- `customer-maps-api-client`: Frontend-клиент `yandex_maps.ts` — обёртки `suggest(query, lang)` и `geocode(text, lang)` над проксирующим `/api/v1/maps/*` (INV-015: никаких ключей на клиенте).
- `customer-addresses-api-client`: Frontend-клиент `addresses.ts` — типизированные обёртки для CRUD и set-primary.

### Modified Capabilities

Нет. Существующие specs (`order-checkout`, `customer-cart-ui`, `user-profile-screen`) остаются без изменений на уровне требований — checkout-страница сейчас заглушка, профиль расширяется отдельной страницей, новые endpoints не конфликтуют с текущими.

## Impact

- **Код:** новые файлы в `web/customer/src/components/AddressAutocomplete/`, `web/customer/src/pages/Profile/Addresses/`, `web/customer/src/api/{yandex_maps,addresses,orders}.ts`; правки `web/customer/src/pages/CheckoutPage.tsx` (расширение), `web/customer/src/App.tsx` (добавить route), `web/customer/src/i18n/` (ключи RU/EN).
- **API-контракт (зависимости):** клиент опирается на `GET /api/v1/maps/suggest?text=...&lang=...`, `GET /api/v1/maps/geocode?text=...` (опционально), `GET|POST|PATCH|DELETE /api/v1/profile/addresses`, `POST /api/v1/profile/addresses/{id}/set-primary`, `POST /api/v1/orders` с поддержкой `delivery_address_id` ИЛИ inline `delivery_address`. Фронтовый change не реализует эти эндпоинты — ожидается их наличие из backend-worktree.
- **INV-015:** `YANDEX_MAPS_API_KEY` никогда не попадает на клиент — все запросы идут через Core API.
- **Тесты:** Vitest на логику (autocomplete state/debounce/fallback, XOR формы checkout). Чистая презентация без тестов (AGENTS.md).
- **Зависимости:** существующие — `react-i18next`, `react-router-dom`, `@/api/client`. Новых пакетов не добавляется.
