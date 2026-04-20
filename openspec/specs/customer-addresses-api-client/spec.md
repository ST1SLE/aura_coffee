# customer-addresses-api-client Specification

## Purpose
TBD - created by archiving change customer-delivery-ui. Update Purpose after archive.
## Requirements
### Requirement: addresses.ts exposes CRUD and set-primary

Модуль `web/customer/src/api/addresses.ts` SHALL экспортировать типизированные функции:
- `listAddresses(): Promise<AddressResponse[]>` → `GET /api/v1/profile/addresses`.
- `createAddress(data: AddressCreatePayload): Promise<AddressResponse>` → `POST /api/v1/profile/addresses`.
- `updateAddress(id: string, data: AddressUpdatePayload): Promise<AddressResponse>` → `PATCH /api/v1/profile/addresses/{id}`.
- `deleteAddress(id: string): Promise<void>` → `DELETE /api/v1/profile/addresses/{id}`.
- `setPrimaryAddress(id: string): Promise<AddressResponse>` → `POST /api/v1/profile/addresses/{id}/set-primary`.

Тип `AddressResponse` SHALL содержать минимум: `id: string`, `text: string`, `lat: number | null`, `lon: number | null`, `label: string | null`, `apartment: string | null`, `entrance: string | null`, `floor: string | null`, `comment: string | null`, `is_primary: boolean`.

#### Scenario: listAddresses uses authenticatedFetch
- **WHEN** вызвано `listAddresses()`
- **THEN** SHALL быть отправлен GET на `/api/v1/profile/addresses` с заголовками авторизации

#### Scenario: createAddress sends JSON body
- **WHEN** вызвано `createAddress({ text: 'X', lat: 1, lon: 2, label: 'Дом' })`
- **THEN** SHALL быть отправлен POST на `/api/v1/profile/addresses` с `Content-Type: application/json` и соответствующим body

### Requirement: Error contract surfaces status + detail

Все функции клиента SHALL при не-2xx ответе бросать ошибку, из которой вызывающий код может получить `status: number` и `detail?: string` (или `message`). Это необходимо, чтобы UI мог различать 409 (радиус, precision) от 401/404/500.

#### Scenario: 409 error includes status
- **WHEN** сервер вернул `409` c body `{ "detail": "Адрес вне зоны..." }`
- **THEN** вызывающий код SHALL получить ошибку с `status === 409` и `detail === "Адрес вне зоны..."`

