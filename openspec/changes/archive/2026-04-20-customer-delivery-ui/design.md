## Affected Modules

- `[web-customer]` — ядро изменений: новые компоненты, страницы, API-клиенты, расширение checkout, i18n-ключи.
- `[core-api]` — **только потребление контракта**. Эндпоинты `/api/v1/maps/{suggest,geocode}` и `/api/v1/profile/addresses` в этом change НЕ создаются (отдельный backend-change Phase 4).

## Context

PDD §4.4 требует customer-facing UI для доставки: Яндекс.Карты автокомплит + управление адресами + checkout с выбором. Сейчас в `web/customer/`:

- `src/pages/CheckoutPage.tsx` — заглушка на 11 строк: `<h1>` + текст из i18n.
- `src/pages/ProfilePage.tsx` — существует, но страницы адресов `/profile/addresses` нет.
- `src/api/` — есть `profile.ts` (GET/PATCH профиль), `cart.ts`, `menu.ts`. `orders.ts`, `addresses.ts`, `yandex_maps.ts` отсутствуют.
- `src/components/` — `Layout`, `LanguageSwitcher`, `ui/` (shadcn), `auth/`. Компонентов адресов нет.
- `src/App.tsx` — роутинг через `react-router-dom`, `Layout` + `ProtectedRoute`, все клиентские пути под авторизацией.

Серверные bits, на которые опирается UI (PDD и backend-схемы подтверждают):

- `CreateOrderRequest` уже поддерживает inline `delivery_address: DeliveryAddress | None` (`services/core-api/src/core_api/schemas/order.py:14-33`). Для `delivery_address_id` контракт на backend-стороне СЛЕДУЕТ расширить отдельным change'ом — этот фронт-change **предполагает** его наличие к моменту интеграции.
- Валидация радиуса (§7.3 шаг 3) и Delivery Fee Chain (§7.4) уже на сервере (Phase 3). Ошибка радиуса возвращается как `409 Conflict` из `POST /api/v1/orders` (см. `orders.py:65`), текст — из validator'а.
- `/api/v1/profile/addresses` и `/api/v1/maps/*` ещё не реализованы в `services/core-api/src/core_api/routers/`. Frontend-change пишется против контракта; интеграция-e2e — после мержа backend-worktree.

Стейкхолдеры: customer (UX доставки), backend-team (контракт), i18n (RU/EN-паритет).

## Goals / Non-Goals

**Goals:**

- MUST отдать клиенту работающий `AddressAutocomplete` с debounce 300ms, dropdown-подсказками, сохранением `{text, lat, lon}` и graceful fallback на 503 от Suggest API (§8.3).
- MUST реализовать страницу `/profile/addresses` с CRUD + set-primary + рендером ошибок радиуса (§7.3).
- MUST превратить checkout из заглушки в минимальную форму: `type = PICKUP | DELIVERY`, XOR-ветки "сохранённый/новый адрес", submit в `POST /api/v1/orders`.
- MUST соблюдать INV-015: ни одного упоминания `YANDEX_MAPS_API_KEY` на клиенте; все вызовы — через Core API.
- MUST поддерживать RU/EN через `react-i18next`, пробрасывая `lang=ru_RU | en_US` в `/api/v1/maps/suggest` (§8.3 "Локализация").
- SHOULD покрыть Vitest'ами логику (autocomplete state, debounce, fallback, XOR саформы). Презентация без тестов (AGENTS.md).

**Non-Goals:**

- Серверные эндпоинты `/api/v1/maps/*` и `/api/v1/profile/addresses` — не реализуются здесь.
- Курьерский UI и Delivery Assignment (§6.3).
- Карта с визуальным radius preview.
- Live-расчёт `delivery_fee` до submit.
- Серверная валидация времени слотов (§7.5) — отдельный change.

## Decisions

### 1. Debounce: ручной `useEffect` + `setTimeout` vs lodash vs useDebouncedCallback

**Выбрано:** ручной debounce на `useEffect` с cleanup. Стандартный шаблон: `useEffect(() => { const id = setTimeout(() => fetch, 300); return () => clearTimeout(id); }, [query])`.
**Почему:** Нулевые новые зависимости (AGENTS.md, см. proposal Impact). Код тривиален для unit-теста через `vi.useFakeTimers()`. Lodash/use-debounce — overkill для одного места.
**Альтернатива:** `use-debounce` пакет — читабельнее, но +dependency.

### 2. Fallback на 503 от `/maps/suggest` (§8.3)

**Выбрано:** при HTTP 503 (или network error) компонент переключается в `degraded`-режим: dropdown скрыт навсегда для текущей сессии страницы, input работает как обычный textbox. На submit координаты запросит сервер через Geocoder (§7.3 шаг 2). Повторные попытки suggest'а на той же странице — **НЕ** делаем (чтобы не ддосить умирающий Яндекс).
**Почему:** §8.3 явно требует "degraded UX, но не блокировка". Координаты (`lat, lon`) в этом режиме на клиенте = `null`; сервер их доберёт сам — `CreateOrderRequest.delivery_address` уже это поддерживает (текст обязателен, lat/lon опциональны на уровне Pydantic, но валидатор проверит precision).
**Альтернатива:** exponential retry на suggest — переусложняет, не даёт значимого UX-выигрыша.
**Trade-off:** клиент, начавший ввод ДО падения API, получит подсказки; клиент, начавший ПОСЛЕ — нет. Это приемлемо по §8.3.

### 3. Выбор "сохранённый vs новый" в checkout — XOR-форма

**Выбрано:** единый form state с дискриминированным union'ом:
```ts
type DeliveryChoice =
  | { kind: 'saved'; address_id: string }
  | { kind: 'new'; text: string; lat: number | null; lon: number | null;
      apartment?: string; entrance?: string; floor?: string; comment?: string;
      save_for_future: boolean };
```
На submit маппим в `CreateOrderRequest`: `kind='saved'` → `{ delivery_address_id }`, `kind='new'` → `{ delivery_address }`. Никогда не отправляем оба поля.
**Почему:** TypeScript-типизация сама ловит невалидные состояния; юнит-тест XOR — одна проверка сериализатора.
**Альтернатива:** два независимых useState'а + runtime assert — хрупко.

### 4. API-клиенты через существующий `authenticatedFetch`

**Выбрано:** `yandex_maps.ts`, `addresses.ts`, `orders.ts` используют `authenticatedFetch` из `@/api/client` (уже есть, см. `src/api/profile.ts` как reference).
**Почему:** единообразие с `profile.ts`, `cart.ts`, `menu.ts`; обработка 401/refresh вынесена в один слой; JWT из store.
**Альтернатива:** отдельный `axios`-инстанс — лишняя зависимость.

### 5. Source of truth для "основного" адреса

**Выбрано:** сервер (`is_primary: boolean` в `AddressResponse`, backend-контракт). Кнопка "Сделать основным" → `POST /api/v1/profile/addresses/{id}/set-primary`. После успеха — рефетч списка.
**Почему:** один источник истины, никакой локальной догадки.

### 6. Рендер ошибок от `POST /orders`

Серверные validator'ы возвращают `409 Conflict` с `detail: str` (см. `orders.py:63-65`). Варианты из §7.3/§7.4:

- "Адрес вне зоны доставки (максимум {radius} км)" → ключ i18n `errors.delivery.outOfRadius`, с placeholder `{{radius}}`.
- "Не удалось определить точный адрес..." → `errors.delivery.geocodePrecision`.
- "Минимальная сумма заказа для доставки — {min}₽" → `errors.delivery.belowMinAmount`.
- "Сервис проверки адреса временно недоступен..." → `errors.delivery.mapsUnavailable`.

**Выбрано:** парсинг `detail` через regex/substring-сниффинг на клиенте для извлечения `{radius}/{min}` **НЕ** делаем. Отображаем `detail` как есть, если он локализован сервером. Если не локализован — fallback i18n-ключ по HTTP-статусу + текстовое поле `detail` как вторая строка.
**Почему:** локализация — ответственность сервера (PDD §4.4: "валидации дублируются на сервере"). Дублировать regex на клиенте — хрупко и не DRY.

### 7. i18n-ключи

**Выбрано:** новая секция `pages.addresses.*` и `pages.checkout.*` в существующих `src/i18n/{ru,en}.json` (или аналог — проверить при implement). Ключи для:
- `pages.addresses.title`, `pages.addresses.addButton`, `pages.addresses.form.{label,apartment,entrance,floor,comment,save,cancel}`, `pages.addresses.makePrimary`, `pages.addresses.edit`, `pages.addresses.delete`, `pages.addresses.empty`.
- `pages.checkout.type.{pickup,delivery}`, `pages.checkout.delivery.{savedAddress,newAddress,saveForFuture,submit}`.
- `components.addressAutocomplete.{placeholder,loading,noResults,degraded}`.
- `errors.delivery.{outOfRadius,geocodePrecision,belowMinAmount,mapsUnavailable,generic}`.

## Risks / Trade-offs

- **[Risk] Backend endpoints ещё не готовы** → Mitigation: change пишется против контракта из proposal'а. Vitest мокает `fetch`. E2E smoke-тест откладывается до мержа backend-worktree. В AGENTS.md задач добавить `TODO: wire to real backend after merge`.
- **[Risk] Контракт `delivery_address_id` может разойтись с тем, что сделает backend** → Mitigation: в design.md зафиксировано имя поля. При расхождении — правка одной строки в `orders.ts` и `CheckoutPage.tsx`.
- **[Risk] Suggest API возвращает дубликаты/мусор для коротких запросов** → Mitigation: минимальная длина query для запуска запроса — 3 символа. До 3 — dropdown пустой. (Стандартный для Яндекс-автокомплита порог.)
- **[Risk] Race condition: пользователь печатает быстрее debounce, старый запрос возвращается позже нового** → Mitigation: храним `requestId` (монотонный счётчик) в ref; при возврате сверяем с текущим — stale игнорируем. Классический pattern для debounce + fetch.
- **[Risk] 503-fallback "залипает" на всю сессию** → Trade-off: приемлемо (см. Decision 2). Альтернатива — "retry on next focus" — усложнение без понятной пользы для MVP.
- **[Trade-off] Нет live-preview `delivery_fee`** → клиент узнаёт стоимость только после submit. Для MVP приемлемо (§7.4 Chain требует subtotal с баллами/промокодом, что уже сложная цепочка; отдельный `POST /api/v1/orders/preview` — отдельный change).
- **[Trade-off] Нет юнит-тестов на чистую презентацию (markup AddressAutocomplete dropdown)** → AGENTS.md явно это разрешает. Regression-риск невысок (простая разметка).

## Open Questions

Все ключевые решения зафиксированы; явных open questions, требующих ответа ДО implement, нет. При обнаружении расхождений с фактическим backend-контрактом (имя поля `delivery_address_id`, коды ошибок радиуса) — остановиться и спросить (Rules CLAUDE.md).
