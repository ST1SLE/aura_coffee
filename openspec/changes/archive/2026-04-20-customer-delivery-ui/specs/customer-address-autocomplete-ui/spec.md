## ADDED Requirements

Reference: PDD §4.4 (Customer Frontend), §7.3 (Address Validation Chain шаги 1–2), §8.3 (Яндекс.Карты), INV-015 (secrets out of code).

### Requirement: AddressAutocomplete renders debounced suggestions from Suggest API

Компонент `AddressAutocomplete` в `web/customer/src/components/AddressAutocomplete/` SHALL показывать dropdown с подсказками адреса, полученными из `GET /api/v1/maps/suggest?text={query}&lang={lang}`, где `lang` соответствует активному i18n-языку (`ru_RU` для RU, `en_US` для EN). Запросы SHALL делаться с debounce 300 мс: таймер сбрасывается при каждом нажатии клавиши. Компонент SHALL не отправлять запрос, пока длина query < 3 символов.

#### Scenario: User types 3+ chars and waits — request fires after 300ms
- **WHEN** пользователь вводит "Нев" в input и в течение 300 мс не печатает дальше
- **THEN** компонент SHALL отправить ровно один GET-запрос на `/api/v1/maps/suggest?text=Нев&lang=ru_RU` по истечении 300 мс
- **AND** SHALL отобразить полученные элементы `items: { text, lat, lon }[]` в dropdown

#### Scenario: Rapid typing cancels prior debounce
- **WHEN** пользователь печатает "Нев", через 100 мс добавляет "ский"
- **THEN** первый запрос SHALL НЕ быть отправлен
- **AND** спустя 300 мс после последнего нажатия SHALL быть отправлен один запрос с `text=Невский`

#### Scenario: Query shorter than 3 chars
- **WHEN** пользователь ввёл "Не"
- **THEN** запрос к `/api/v1/maps/suggest` SHALL НЕ быть отправлен
- **AND** dropdown SHALL быть пуст / скрыт

#### Scenario: Stale response ignored
- **WHEN** отправлен запрос A (`text=Нев`), затем до его возврата отправлен запрос B (`text=Невский`), ответ A приходит позже ответа B
- **THEN** результат A SHALL быть проигнорирован
- **AND** dropdown SHALL содержать только результат B

### Requirement: AddressAutocomplete selection stores {text, lat, lon}

При выборе варианта из dropdown компонент SHALL вызвать `onChange({ text, lat, lon })` и закрыть dropdown. Значение input SHALL стать равным `text` выбранного варианта.

#### Scenario: User picks suggestion
- **WHEN** dropdown показывает 3 варианта, пользователь кликает на 2-й
- **THEN** `onChange` SHALL быть вызван с `{ text: '...', lat: <число>, lon: <число> }` соответствующих 2-му варианту
- **AND** input SHALL отобразить текст выбранного варианта
- **AND** dropdown SHALL закрыться

### Requirement: AddressAutocomplete degrades on 503 from Suggest API

При HTTP 503 (или network error / timeout ≥ 3s) от `/api/v1/maps/suggest` компонент SHALL переключиться в `degraded`-режим: dropdown SHALL быть скрыт, последующие запросы suggest SHALL НЕ отправляться в этой же сессии монтирования компонента, input SHALL продолжать работать как обычный textbox. `onChange` SHALL вызываться с `{ text, lat: null, lon: null }` при потере фокуса или submit'е формы. (Сервер получит координаты через Geocoder — см. §7.3 шаг 2.)

Reference: PDD §8.3 "Fallback при недоступности: ... Suggest API недоступен — показать обычное текстовое поле ввода адреса (degraded UX, но не блокировка)."

#### Scenario: 503 triggers degraded mode
- **WHEN** пользователь ввёл "Нев", debounce сработал, запрос вернулся с `status: 503`
- **THEN** компонент SHALL войти в `degraded`-режим
- **AND** dropdown SHALL НЕ отобразиться
- **AND** пользователь SHALL видеть локализованную подсказку (i18n-ключ `components.addressAutocomplete.degraded`), не блокирующую ввод

#### Scenario: Degraded mode sticks for the session
- **WHEN** компонент в `degraded`-режиме, пользователь продолжает печатать
- **THEN** SHALL НЕ быть отправлено ни одного запроса к `/api/v1/maps/suggest`

#### Scenario: Degraded mode emits onChange without coords
- **WHEN** компонент в `degraded`-режиме, пользователь ввёл "Улица Ленина 1" и вышел из input (blur)
- **THEN** `onChange` SHALL быть вызван с `{ text: 'Улица Ленина 1', lat: null, lon: null }`

### Requirement: AddressAutocomplete does NOT expose Yandex API key

Компонент SHALL взаимодействовать с Яндекс.Картами ИСКЛЮЧИТЕЛЬНО через эндпоинт Core API `/api/v1/maps/suggest`. Импорты, env-переменные и ссылки на `YANDEX_MAPS_API_KEY` в клиентском коде `web/customer/` — ЗАПРЕЩЕНЫ (INV-015).

#### Scenario: No API key in component source
- **WHEN** кто-либо грепнет `YANDEX_MAPS_API_KEY` по каталогу `web/customer/src/`
- **THEN** результат SHALL быть пуст

#### Scenario: No direct call to api-maps.yandex.ru
- **WHEN** grep по `web/customer/src/` на `api-maps.yandex` или `geocode-maps.yandex`
- **THEN** результат SHALL быть пуст (все вызовы проксируются через `/api/v1/maps/*`)
