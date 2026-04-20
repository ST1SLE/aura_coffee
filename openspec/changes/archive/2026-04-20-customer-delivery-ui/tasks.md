## 1. PREREQ — i18n keys

- [x] 1.1 PREREQ [web-customer] Добавить в `web/customer/src/i18n/ru.json` (или аналог) ключи: `components.addressAutocomplete.{placeholder,loading,noResults,degraded}`, `pages.addresses.{title,addButton,empty,makePrimary,edit,delete,confirmDelete,form.{label,apartment,entrance,floor,comment,save,cancel}}`, `pages.checkout.{title,submit,type.{pickup,delivery},delivery.{savedAddress,newAddress,saveForFuture}}`, `errors.delivery.{outOfRadius,geocodePrecision,belowMinAmount,mapsUnavailable,generic}`.
- [x] 1.2 PREREQ [web-customer] Зеркально добавить те же ключи на английском в `web/customer/src/i18n/en.json` (или аналог).

## 2. API client — maps (RED→GREEN→REFACTOR)

- [x] 2.1 RED [web-customer] Создать `web/customer/src/api/yandex_maps.test.ts` с тестом `suggest builds URL with text and lang` — mockует `authenticatedFetch`, проверяет что при `suggest('Нев', 'ru_RU')` вызван путь `/api/v1/maps/suggest?text=Нев&lang=ru_RU` (spec customer-maps-api-client § "suggest builds proper URL"). Тест должен падать с ImportError.
- [x] 2.2 RED [web-customer] В `yandex_maps.test.ts` добавить тест `suggest signals MapsUnavailable on 503` — mock возвращает `{ ok: false, status: 503 }`, ожидает throw/return соответствующего типа (spec § "Maps client maps 503 to typed failure").
- [x] 2.3 RED [web-customer] В `yandex_maps.test.ts` добавить тест `suggest signals MapsUnavailable on network error` — mock бросает `TypeError`, ожидает тот же MapsUnavailable сигнал.
- [x] 2.4 RED [web-customer] В `yandex_maps.test.ts` добавить тест `geocode defaults to lang=ru_RU` — проверить что без lang-аргумента URL содержит `lang=ru_RU` (PDD §8.3).
- [x] 2.5 GREEN [web-customer] Создать `web/customer/src/api/yandex_maps.ts` с функциями `suggest`, `geocode`, типами `SuggestResult`, `GeocodeResult`, классом/типом `MapsUnavailableError` → проходят 2.1–2.4.
- [x] 2.6 REFACTOR [web-customer] Причесать имена/типы в `yandex_maps.ts` (экспорты, JSDoc только где нужно).

## 3. API client — addresses (RED→GREEN→REFACTOR)

- [x] 3.1 RED [web-customer] Создать `web/customer/src/api/addresses.test.ts` с тестом `listAddresses GETs /api/v1/profile/addresses` (spec customer-addresses-api-client § "listAddresses uses authenticatedFetch").
- [x] 3.2 RED [web-customer] В `addresses.test.ts` добавить тест `createAddress POSTs JSON body` — проверка method, headers, body.
- [x] 3.3 RED [web-customer] В `addresses.test.ts` добавить тест `updateAddress PATCHes with id in URL`.
- [x] 3.4 RED [web-customer] В `addresses.test.ts` добавить тест `deleteAddress DELETEs by id`.
- [x] 3.5 RED [web-customer] В `addresses.test.ts` добавить тест `setPrimaryAddress POSTs to /{id}/set-primary`.
- [x] 3.6 RED [web-customer] В `addresses.test.ts` добавить тест `errors expose status and detail` — mock вернул 409 с body `{detail: '...'}`, проверить что throw содержит `status: 409` и `detail` (spec § "Error contract surfaces status + detail").
- [x] 3.7 GREEN [web-customer] Создать `web/customer/src/api/addresses.ts` с функциями `listAddresses`, `createAddress`, `updateAddress`, `deleteAddress`, `setPrimaryAddress`, типами `AddressResponse`, `AddressCreatePayload`, `AddressUpdatePayload`, классом ошибки → проходят 3.1–3.6.
- [x] 3.8 REFACTOR [web-customer] Причесать `addresses.ts` (общий error-wrapper, если дублируется).

## 4. API client — orders (RED→GREEN→REFACTOR)

- [x] 4.1 RED [web-customer] Создать `web/customer/src/api/orders.test.ts` с тестом `createOrder PICKUP omits delivery fields` (spec customer-checkout-delivery-ui § "PICKUP submit").
- [x] 4.2 RED [web-customer] Добавить тест `createOrder DELIVERY with saved address sends delivery_address_id only` — body содержит `delivery_address_id`, не содержит `delivery_address` (spec § "DELIVERY with saved address").
- [x] 4.3 RED [web-customer] Добавить тест `createOrder DELIVERY with new address sends delivery_address only` — body содержит `delivery_address`, не содержит `delivery_address_id` (spec § "DELIVERY with new address").
- [x] 4.4 RED [web-customer] Добавить тест `createOrder throws with status and detail on 409` — типизированная ошибка.
- [x] 4.5 GREEN [web-customer] Создать `web/customer/src/api/orders.ts` с функцией `createOrder(payload)` и типами `CreateOrderPayload` (дискриминированный union) → проходят 4.1–4.4.
- [x] 4.6 REFACTOR [web-customer] Вынести общие утилиты парсинга ошибок, если дублируются между `addresses.ts`/`orders.ts`/`yandex_maps.ts`.

## 5. AddressAutocomplete component (IMPL→TEST→REFACTOR)

- [x] 5.1 IMPL [web-customer] Создать `web/customer/src/components/AddressAutocomplete/AddressAutocomplete.tsx` с props `{ value: { text, lat, lon }, onChange, lang }` — минимальная скелет-реализация без логики, используя shadcn `Input`.
- [x] 5.2 IMPL [web-customer] В `AddressAutocomplete.tsx` реализовать debounced fetch через `useEffect` + `setTimeout(300)`, порог длины query ≥ 3, race-guard через `useRef` requestId. Dropdown-рендер элементов.
- [x] 5.3 IMPL [web-customer] В `AddressAutocomplete.tsx` обработать `MapsUnavailableError`/503 → переключение в `degraded`-state (локальный useState), показ подсказки `components.addressAutocomplete.degraded`, блокировка дальнейших запросов.
- [x] 5.4 IMPL [web-customer] В `AddressAutocomplete.tsx` реализовать выбор элемента → `onChange({ text, lat, lon })`, закрытие dropdown; blur в degraded-режиме → `onChange({ text, lat: null, lon: null })`.
- [x] 5.5 TEST [web-customer] Создать `web/customer/src/components/AddressAutocomplete/AddressAutocomplete.test.tsx` с тестом `fires suggest after 300ms debounce with lang` через `vi.useFakeTimers()` + мок `yandex_maps.suggest` (spec customer-address-autocomplete-ui § "User types 3+ chars and waits").
- [x] 5.6 TEST [web-customer] Добавить тест `rapid typing cancels prior debounce` — два keystrokes с разрывом < 300 мс, ожидание ровно одного вызова.
- [x] 5.7 TEST [web-customer] Добавить тест `query < 3 chars does NOT call suggest`.
- [x] 5.8 TEST [web-customer] Добавить тест `stale response ignored via requestId guard`.
- [x] 5.9 TEST [web-customer] Добавить тест `selection calls onChange with text lat lon`.
- [x] 5.10 TEST [web-customer] Добавить тест `503 triggers degraded mode and stops further calls`.
- [x] 5.11 TEST [web-customer] Добавить тест `degraded blur emits onChange with lat lon null`.
- [x] 5.12 REFACTOR [web-customer] Вынести хук `useDebouncedSuggest` из компонента, если упрощает читабельность (опционально).

## 6. Addresses page (IMPL→TEST→REFACTOR)

- [x] 6.1 IMPL [web-customer] Создать `web/customer/src/pages/Profile/Addresses/AddressesPage.tsx` — скелет: `useEffect` → `listAddresses()`, рендер списка / empty-state.
- [x] 6.2 IMPL [web-customer] Создать `web/customer/src/pages/Profile/Addresses/AddressForm.tsx` — форма с `AddressAutocomplete` + label/apartment/entrance/floor/comment, submit → `createAddress`/`updateAddress`, рендер ошибки радиуса.
- [x] 6.3 IMPL [web-customer] В `AddressesPage.tsx` подключить карточки адресов с кнопками Edit / Delete (с confirm) / "Сделать основным". Рефетч после каждой успешной операции.
- [x] 6.4 IMPL [web-customer] Добавить route `/profile/addresses` в `web/customer/src/App.tsx` (под `ProtectedRoute` + `Layout`), импорт `AddressesPage`.
- [x] 6.5 TEST [web-customer] Создать `web/customer/src/pages/Profile/Addresses/AddressForm.test.tsx` с тестом `submit calls createAddress with form data` (мок `addresses.createAddress`).
- [x] 6.6 TEST [web-customer] Добавить тест `radius error shown on 409` — mock `createAddress` throws `{status:409, detail:"out of radius"}`, проверить наличие локализованного сообщения в DOM.
- [x] 6.7 REFACTOR [web-customer] Причесать структуру папки `Profile/Addresses/` (index.ts re-export, если используется в codebase-конвенциях).

## 7. Checkout page (IMPL→TEST→REFACTOR)

- [x] 7.1 IMPL [web-customer] Переписать `web/customer/src/pages/CheckoutPage.tsx` из заглушки: добавить state `type: 'PICKUP' | 'DELIVERY'` через radio, submit-кнопку вызывающую `createOrder`. Заглушка текста оставить локализованной.
- [x] 7.2 IMPL [web-customer] В `CheckoutPage.tsx` при `type = DELIVERY` подгрузить `listAddresses()`, показать блок "Сохранённый/Новый" если список не пуст; отрендерить ветку "Новый" с `AddressForm`-подобным контентом (или reuse `AddressForm` в inline-режиме без submit — через shared sub-component).
- [x] 7.3 IMPL [web-customer] В `CheckoutPage.tsx` реализовать сериализацию XOR: дискриминированный union в state, маппинг в `CreateOrderPayload` на submit.
- [x] 7.4 IMPL [web-customer] В `CheckoutPage.tsx` при `saveForFuture = true` и успехе `createOrder` дополнительно вызвать `createAddress` (не блокируя переход). Ошибку логировать через `console.warn`.
- [x] 7.5 IMPL [web-customer] В `CheckoutPage.tsx` рендерить `detail` из 409-ошибки `createOrder` в поле статуса формы (локализованный fallback по HTTP-коду).
- [x] 7.6 TEST [web-customer] Создать `web/customer/src/pages/CheckoutPage.test.tsx` с тестом `default type is PICKUP and submit sends PICKUP payload`.
- [x] 7.7 TEST [web-customer] Добавить тест `switching to DELIVERY with saved addresses shows saved/new radio and preselects primary`.
- [x] 7.8 TEST [web-customer] Добавить тест `submitting saved-address path sends delivery_address_id only (not delivery_address)`.
- [x] 7.9 TEST [web-customer] Добавить тест `submitting new-address path sends delivery_address only (not delivery_address_id)`.
- [x] 7.10 TEST [web-customer] Добавить тест `saveForFuture=true calls createAddress after successful createOrder`.
- [x] 7.11 TEST [web-customer] Добавить тест `saveForFuture=false does NOT call createAddress`.
- [x] 7.12 TEST [web-customer] Добавить тест `409 from createOrder renders detail and keeps form open`.
- [x] 7.13 REFACTOR [web-customer] Если блок "Новый адрес" дублируется между `AddressesPage` и `CheckoutPage` — вынести в общий `AddressFields` компонент. (Пропущено: inline-блок в Checkout использует подмножество полей `AddressForm` без label/submit — извлечение усложнило бы API без выигрыша.)

## 8. VERIFY

- [x] 8.1 VERIFY [web-customer] Запустить `npm run test` в `web/customer/` — все новые тесты из разделов 2–7 зелёные. (147/147 passed)
- [x] 8.2 VERIFY [web-customer] Запустить `npm run typecheck` (tsc) в `web/customer/` — ноль ошибок в новых файлах (3 pre-existing TS6133 в `App.test.tsx`/`VerifyPage.test.tsx` не относятся к этому изменению).
- [x] 8.3 VERIFY [web-customer] `grep -r "YANDEX_MAPS_API_KEY" web/customer/src/` возвращает пусто (INV-015).
- [x] 8.4 VERIFY [web-customer] `grep -r "api-maps.yandex\|geocode-maps.yandex" web/customer/src/` возвращает пусто (все вызовы через `/api/v1/maps/*`).
