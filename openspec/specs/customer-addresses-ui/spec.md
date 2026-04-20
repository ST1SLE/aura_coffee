# customer-addresses-ui Specification

## Purpose
TBD - created by archiving change customer-delivery-ui. Update Purpose after archive.
## Requirements
### Requirement: Addresses page lists saved addresses

Страница `/profile/addresses` (`web/customer/src/pages/Profile/Addresses/`) SHALL при монтировании вызывать `GET /api/v1/profile/addresses` и рендерить список сохранённых адресов с полями: `label`, `text`, `apartment`, `entrance`, `floor`, `comment`, `is_primary`. Если список пуст — SHALL отображать локализованное сообщение (i18n-ключ `pages.addresses.empty`) и кнопку "Добавить адрес".

#### Scenario: Non-empty list
- **WHEN** пользователь открывает `/profile/addresses` и сервер возвращает 2 адреса
- **THEN** страница SHALL отобразить обе карточки
- **AND** адрес с `is_primary: true` SHALL визуально быть помечен как основной

#### Scenario: Empty list
- **WHEN** сервер возвращает `{ items: [] }`
- **THEN** страница SHALL отобразить текст из `pages.addresses.empty`
- **AND** SHALL показать кнопку "Добавить адрес"

### Requirement: User can add a new address

Форма добавления адреса SHALL содержать `AddressAutocomplete` для основного поля + опциональные поля `label`, `apartment`, `entrance`, `floor`, `comment`. На submit SHALL вызвать `POST /api/v1/profile/addresses` с `{ text, lat, lon, label?, apartment?, entrance?, floor?, comment? }`. При успехе (2xx) SHALL рефетчить список и закрыть форму. При ошибке 409 с `detail` про радиус SHALL отобразить локализованный текст "Адрес вне зоны доставки (макс. {radius} км)" (ключ `errors.delivery.outOfRadius`).

#### Scenario: Successful add
- **WHEN** пользователь выбрал адрес из автокомплита, заполнил "квартира: 42", нажал Save
- **THEN** клиент SHALL вызвать `POST /api/v1/profile/addresses` с body `{ text, lat, lon, apartment: '42', ... }`
- **AND** при `201` SHALL обновить список и закрыть форму

#### Scenario: Radius error from server
- **WHEN** сервер возвращает `409 Conflict` с `detail` содержащим маркер out-of-radius
- **THEN** форма SHALL отобразить локализованное сообщение о выходе из зоны доставки
- **AND** форма SHALL остаться открытой (пользователь может исправить)

### Requirement: User can edit, delete, and set primary

Каждая карточка адреса SHALL иметь кнопки Edit, Delete, "Сделать основным" (последняя скрыта, если `is_primary: true`).
- Edit → открыть ту же форму с предзаполненными полями; submit → `PATCH /api/v1/profile/addresses/{id}`.
- Delete → подтверждение → `DELETE /api/v1/profile/addresses/{id}`.
- "Сделать основным" → `POST /api/v1/profile/addresses/{id}/set-primary`.
После каждой успешной операции SHALL рефетчить список.

#### Scenario: Edit address
- **WHEN** пользователь кликает Edit, меняет comment, Save
- **THEN** SHALL быть вызван `PATCH /api/v1/profile/addresses/{id}` с новым body
- **AND** список SHALL быть перезагружен

#### Scenario: Delete address
- **WHEN** пользователь кликает Delete и подтверждает
- **THEN** SHALL быть вызван `DELETE /api/v1/profile/addresses/{id}`
- **AND** карточка SHALL исчезнуть из списка после успеха

#### Scenario: Set primary flips flag
- **WHEN** пользователь кликает "Сделать основным" на не-primary адресе
- **THEN** SHALL быть вызван `POST /api/v1/profile/addresses/{id}/set-primary`
- **AND** после рефетча — именно этот адрес SHALL иметь `is_primary: true`
- **AND** все остальные SHALL иметь `is_primary: false`

### Requirement: Addresses page is routed under auth

Путь `/profile/addresses` SHALL быть зарегистрирован в `App.tsx` внутри `<ProtectedRoute>`. Неавторизованный пользователь SHALL быть редиректнут на `/login` (поведение существующего `ProtectedRoute`).

#### Scenario: Unauthenticated redirect
- **WHEN** неавторизованный пользователь открывает `/profile/addresses`
- **THEN** SHALL быть редирект на `/login`

#### Scenario: Authenticated access
- **WHEN** авторизованный пользователь открывает `/profile/addresses`
- **THEN** страница SHALL отрендериться в пределах `Layout`

