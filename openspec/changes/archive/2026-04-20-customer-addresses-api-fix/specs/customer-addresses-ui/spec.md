## MODIFIED Requirements

### Requirement: Addresses page lists saved addresses

Relates to PDD §5.2 (Delivery addresses CRUD). Syncs SPA с backend source of truth `is_default`.

**Previously:**
- Page rendered fields `label`, `text`, `apartment`, `entrance`, `floor`, `comment`, `is_primary`.
- Empty-state scenario referenced `{ items: [] }` response shape.

**Now:**
Страница `/profile/addresses` (`web/customer/src/pages/Profile/Addresses/`) SHALL при монтировании вызывать `GET /api/v1/profile/addresses` и рендерить список сохранённых адресов с полями: `label`, `address_text`, `apartment`, `entrance`, `floor`, `comment`, `is_default`. Если список пуст — SHALL отображать локализованное сообщение (i18n-ключ `pages.addresses.empty`) и кнопку "Добавить адрес".

#### Scenario: Non-empty list
- **WHEN** пользователь открывает `/profile/addresses` и сервер возвращает массив из 2 адресов
- **THEN** страница SHALL отобразить обе карточки
- **AND** адрес с `is_default: true` SHALL визуально быть помечен как основной (badge `pages.addresses.primaryBadge`)

#### Scenario: Empty list
- **WHEN** сервер возвращает `[]` (bare array)
- **THEN** страница SHALL отобразить текст из `pages.addresses.empty`
- **AND** SHALL показать кнопку "Добавить адрес"

### Requirement: User can add a new address

Relates to PDD §5.2 (schema requires `label` min_length=1 + `address_text`).

**Previously:**
- Submit posted `{ text, lat, lon, label?, apartment?, ... }` with optional label.

**Now:**
Форма добавления адреса SHALL содержать `AddressAutocomplete` для основного поля + поле `label` (обязательное) + опциональные поля `apartment`, `entrance`, `floor`, `comment`. Кнопка Save SHALL быть disabled, пока одновременно не выполнено: `label.trim().length > 0` И `address_text.trim().length > 0`. На submit SHALL вызвать `POST /api/v1/profile/addresses` с `{ label, address_text, lat, lon, apartment, entrance, floor, comment }`. При успехе (2xx) SHALL рефетчить список и закрыть форму. При ошибке 409 с `detail` про радиус SHALL отобразить локализованный текст ключа `errors.delivery.outOfRadius`.

#### Scenario: Successful add
- **WHEN** пользователь заполнил `label: 'Дом'`, выбрал адрес в автокомплите, заполнил "квартира: 42", нажал Save
- **THEN** клиент SHALL вызвать `POST /api/v1/profile/addresses` с body, содержащим `label: 'Дом'`, `address_text: '<canonical>'`, `apartment: '42'`, `lat`, `lon`
- **AND** body SHALL НЕ содержать поле `text`
- **AND** при `201` SHALL обновить список и закрыть форму

#### Scenario: Label required
- **WHEN** пользователь выбрал адрес в автокомплите но оставил label пустым
- **THEN** кнопка Save SHALL быть disabled
- **AND** `createAddress` SHALL НЕ быть вызван

#### Scenario: Radius error from server
- **WHEN** сервер возвращает `409 Conflict` с `detail` содержащим маркер out-of-radius
- **THEN** форма SHALL отобразить локализованное сообщение о выходе из зоны доставки
- **AND** форма SHALL остаться открытой

### Requirement: User can edit, delete, and set primary

Relates to PDD §5.2 (PATCH-based default flag).

**Previously:**
- "Сделать основным" вызывало `POST /api/v1/profile/addresses/{id}/set-primary`.
- Card hid the "Make primary" button based on `is_primary: true`.

**Now:**
Каждая карточка адреса SHALL иметь кнопки Edit, Delete, "Сделать основным" (последняя скрыта, если `is_default: true`).
- Edit → открыть ту же форму с предзаполненными полями; submit → `PATCH /api/v1/profile/addresses/{id}` с `Partial<AddressCreatePayload>` (поле `label` на edit остаётся обязательным non-empty, как и на create).
- Delete → подтверждение → `DELETE /api/v1/profile/addresses/{id}`.
- "Сделать основным" → вызов `setDefaultAddress(id)`, который шлёт `PATCH /api/v1/profile/addresses/{id}` body `{ "is_default": true }`.
После каждой успешной операции SHALL рефетчить список.

#### Scenario: Edit address
- **WHEN** пользователь кликает Edit, меняет comment, Save
- **THEN** SHALL быть вызван `PATCH /api/v1/profile/addresses/{id}` с новым body
- **AND** список SHALL быть перезагружен

#### Scenario: Delete address
- **WHEN** пользователь кликает Delete и подтверждает
- **THEN** SHALL быть вызван `DELETE /api/v1/profile/addresses/{id}`
- **AND** карточка SHALL исчезнуть из списка после успеха

#### Scenario: Set default flips flag
- **WHEN** пользователь кликает "Сделать основным" на не-default адресе `a2`
- **THEN** SHALL быть вызван `PATCH /api/v1/profile/addresses/a2` с body `{ "is_default": true }`
- **AND** после рефетча — именно этот адрес SHALL иметь `is_default: true`
- **AND** все остальные SHALL иметь `is_default: false`
