## ADDED Requirements

Reference: PDD §8.3 (Яндекс.Карты), §7.3 (Address Validation Chain), INV-015 (secrets out of code).

### Requirement: yandex_maps.ts exposes suggest and geocode helpers

Модуль `web/customer/src/api/yandex_maps.ts` SHALL экспортировать функции:
- `suggest(query: string, lang: 'ru_RU' | 'en_US'): Promise<SuggestResult[]>`, вызывающую `GET /api/v1/maps/suggest?text={query}&lang={lang}`.
- `geocode(text: string, lang?: 'ru_RU' | 'en_US'): Promise<GeocodeResult | null>`, вызывающую `GET /api/v1/maps/geocode?text={text}&lang={lang}`.
Обе функции SHALL использовать `authenticatedFetch` (или эквивалент из `src/api/client.ts`) для отправки запроса.

#### Scenario: suggest builds proper URL
- **WHEN** вызвано `suggest('Нев', 'ru_RU')`
- **THEN** SHALL быть отправлен GET на путь `/api/v1/maps/suggest` с query-параметрами `text=Нев` и `lang=ru_RU`

#### Scenario: geocode with default lang
- **WHEN** вызвано `geocode('Невский 1')` без явного lang
- **THEN** SHALL использоваться `lang=ru_RU` (§8.3 "Geocoder — всегда ru_RU")

### Requirement: Maps client maps 503 to typed failure

`suggest` SHALL при HTTP 503 (или network error) от Core API бросить/вернуть значение, по которому вызывающий компонент может распознать degraded-режим (напр. throw `MapsUnavailableError` или return `{ unavailable: true }`). Выбор формы (exception vs discriminated result) фиксируется в реализации, но SHALL быть консистентным и документированным типом.

#### Scenario: 503 response
- **WHEN** `/api/v1/maps/suggest` возвращает 503
- **THEN** `suggest` SHALL сигнализировать `MapsUnavailable`-состояние

#### Scenario: Network error
- **WHEN** `fetch` бросает `TypeError` (network failure)
- **THEN** `suggest` SHALL сигнализировать `MapsUnavailable`-состояние (не пропускать наверх сырой `TypeError`)

### Requirement: Maps client does NOT contain API key

Модуль `yandex_maps.ts` SHALL НЕ содержать переменных `YANDEX_MAPS_API_KEY`, прямых URL `*.yandex.ru`, или import.meta.env переменных связанных с Яндекс.Картами (INV-015). Все запросы идут через относительные пути `/api/v1/maps/*`.

#### Scenario: grep audit
- **WHEN** `grep -r "YANDEX_MAPS_API_KEY\|api-maps.yandex\|geocode-maps.yandex" web/customer/`
- **THEN** результат SHALL быть пуст
