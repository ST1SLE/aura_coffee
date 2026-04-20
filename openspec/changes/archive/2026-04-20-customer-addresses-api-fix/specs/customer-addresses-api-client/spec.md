## MODIFIED Requirements

### Requirement: addresses.ts exposes CRUD and set-primary

Relates to PDD §5.2 (Delivery addresses CRUD). Fixes schema drift documented in `docs/phase4_manual_test_scenarios.md §6`.

**Previously:**
- Exported `listAddresses`, `createAddress`, `updateAddress`, `deleteAddress`, `setPrimaryAddress`.
- `listAddresses` parsed `{ items: [...] }`.
- `createAddress` sent `{ text, lat, lon, label?, apartment?, ... }`.
- `setPrimaryAddress` POSTed `/api/v1/profile/addresses/{id}/set-primary`.
- `AddressResponse` contained `is_primary: boolean`.

**Now:**
Модуль `web/customer/src/api/addresses.ts` SHALL экспортировать типизированные функции:
- `listAddresses(): Promise<AddressResponse[]>` → `GET /api/v1/profile/addresses`. Тело ответа SHALL парситься как bare JSON array (`AddressResponse[]`). При не-array body клиент SHALL возвращать `[]` (fail-soft).
- `createAddress(data: AddressCreatePayload): Promise<AddressResponse>` → `POST /api/v1/profile/addresses`. Тело запроса SHALL содержать поля `{ label: string, address_text: string, lat: number | null, lon: number | null, apartment: string | null, entrance: string | null, floor: string | null, comment: string | null }`. Поле `label` — обязательное, тип `string` (не nullable, не optional). Поле `address_text` — обязательное (переименовано из `text`).
- `updateAddress(id: string, data: AddressUpdatePayload): Promise<AddressResponse>` → `PATCH /api/v1/profile/addresses/{id}`. `AddressUpdatePayload` SHALL быть `Partial<AddressCreatePayload> & { is_default?: boolean }`.
- `deleteAddress(id: string): Promise<void>` → `DELETE /api/v1/profile/addresses/{id}`.
- `setDefaultAddress(id: string): Promise<AddressResponse>` → `PATCH /api/v1/profile/addresses/{id}` с body `{ "is_default": true }`. Функция `setPrimaryAddress` SHALL быть удалена; единственный путь сделать адрес default — через `setDefaultAddress`.

Тип `AddressResponse` SHALL содержать: `id: string`, `address_text: string`, `lat: number | null`, `lon: number | null`, `label: string | null`, `apartment: string | null`, `entrance: string | null`, `floor: string | null`, `comment: string | null`, `is_default: boolean`. Поле `is_primary` SHALL быть удалено из типа; `text` SHALL быть удалено из типа.

#### Scenario: listAddresses parses bare array
- **WHEN** вызвано `listAddresses()` и сервер вернул `[{id:'a1', ...}, {id:'a2', ...}]`
- **THEN** функция SHALL вернуть массив из 2 элементов
- **AND** SHALL быть отправлен `GET /api/v1/profile/addresses` с заголовками авторизации

#### Scenario: listAddresses fails soft on non-array body
- **WHEN** сервер вернул `{ items: [...] }` (регрессия envelope)
- **THEN** функция SHALL вернуть `[]`
- **AND** SHALL НЕ выбросить ошибку

#### Scenario: createAddress sends address_text and label
- **WHEN** вызвано `createAddress({ label: 'Дом', address_text: 'ул. Ленина 1', lat: 1, lon: 2, apartment: '5', entrance: null, floor: null, comment: null })`
- **THEN** SHALL быть отправлен `POST /api/v1/profile/addresses` с `Content-Type: application/json`
- **AND** body SHALL содержать поле `address_text: 'ул. Ленина 1'` (не `text`)
- **AND** body SHALL содержать поле `label: 'Дом'`

#### Scenario: setDefaultAddress uses PATCH with is_default
- **WHEN** вызвано `setDefaultAddress('a1')`
- **THEN** SHALL быть отправлен `PATCH /api/v1/profile/addresses/a1`
- **AND** body SHALL быть `{ "is_default": true }`
- **AND** функция SHALL вернуть обновлённый `AddressResponse` с `is_default: true`

#### Scenario: AddressResponse exposes is_default (not is_primary)
- **WHEN** сервер вернул `{ ..., "is_default": true }`
- **THEN** типизированный результат SHALL содержать `is_default: true`
- **AND** тип `AddressResponse` SHALL НЕ содержать поле `is_primary`

### Requirement: Error contract surfaces status + detail

Relates to INV-002 (server-side auth) and PDD §5.2 (radius error on 409).

Все функции клиента SHALL при не-2xx ответе бросать `AddressApiError`, из которого вызывающий код может получить `status: number` и `detail?: string`. Это необходимо, чтобы UI мог различать 409 (радиус, precision) от 401/404/500.

#### Scenario: 409 error includes status and detail
- **WHEN** сервер вернул `409` с body `{ "detail": "Адрес вне зоны..." }`
- **THEN** вызывающий код SHALL получить `AddressApiError` с `status === 409` и `detail === "Адрес вне зоны..."`

## REMOVED Requirements

### Requirement: setPrimaryAddress POSTs /set-primary route

**Reason:** Маршрут `POST /api/v1/profile/addresses/{id}/set-primary` не существует на сервере (404/405). Подтверждено в `docs/phase4_manual_test_scenarios.md §6`.

**Migration:** Использовать `setDefaultAddress(id)`, который шлёт `PATCH /api/v1/profile/addresses/{id}` с body `{ "is_default": true }`. Все callers (на момент фикса — `AddressesPage.tsx`) переключены.
