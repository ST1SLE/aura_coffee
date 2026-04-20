# customer-checkout-delivery-ui Specification

## Purpose
TBD - created by archiving change customer-delivery-ui. Update Purpose after archive.
## Requirements
### Requirement: Checkout page renders minimal type picker

`CheckoutPage` (`web/customer/src/pages/CheckoutPage.tsx`) SHALL позволить клиенту выбрать `type: 'PICKUP' | 'DELIVERY'` через radio-группу или эквивалентный UI. При `type = PICKUP` — никаких дополнительных полей адреса. При `type = DELIVERY` — SHALL показать блок выбора адреса (см. следующие требования).

#### Scenario: Default to PICKUP
- **WHEN** страница только что смонтирована
- **THEN** SHALL быть выбран `type = 'PICKUP'`
- **AND** блок адреса SHALL быть скрыт

#### Scenario: Switch to DELIVERY reveals address block
- **WHEN** пользователь выбрал DELIVERY
- **THEN** блок адреса SHALL стать видимым

### Requirement: Delivery block offers saved-vs-new XOR choice

При `type = DELIVERY` и наличии хотя бы одного сохранённого адреса у пользователя блок адреса SHALL предложить radio-выбор между "Сохранённый" и "Новый". При выборе "Сохранённый" — radio-список всех сохранённых адресов (предвыбран `is_primary` если есть). При выборе "Новый" — `AddressAutocomplete` + поля `apartment/entrance/floor/comment` + чекбокс "Сохранить для следующего заказа". Если у пользователя нет сохранённых адресов, ветка "Сохранённый" SHALL быть скрыта, а форма нового адреса SHALL быть активна сразу.

#### Scenario: Saved addresses exist — radio choice shown
- **WHEN** `GET /api/v1/profile/addresses` возвращает 2 адреса, пользователь выбрал DELIVERY
- **THEN** SHALL быть показан radio-выбор "Сохранённый / Новый"
- **AND** по умолчанию SHALL быть выбран "Сохранённый"
- **AND** primary-адрес SHALL быть предвыбран в списке сохранённых

#### Scenario: No saved addresses — new form only
- **WHEN** `GET /api/v1/profile/addresses` возвращает пустой список
- **THEN** radio-выбор "Сохранённый/Новый" SHALL НЕ отображаться
- **AND** форма нового адреса SHALL быть доступна сразу

### Requirement: Submit serializes XOR delivery address

При submit формы клиент SHALL отправить `POST /api/v1/orders` с body согласно выбранной ветке:
- `type = 'PICKUP'`: `{ type: 'PICKUP' }` (без `delivery_address` или `delivery_address_id`).
- `type = 'DELIVERY'`, выбран сохранённый адрес: `{ type: 'DELIVERY', delivery_address_id: '<uuid>' }` (БЕЗ `delivery_address`).
- `type = 'DELIVERY'`, новый адрес: `{ type: 'DELIVERY', delivery_address: { text, lat, lon, apartment?, entrance?, floor?, comment? } }` (БЕЗ `delivery_address_id`).
Клиент SHALL НЕ отправлять одновременно `delivery_address_id` и inline `delivery_address`.

#### Scenario: PICKUP submit
- **WHEN** пользователь выбрал PICKUP и нажал Submit
- **THEN** SHALL быть отправлен `POST /api/v1/orders` с body не содержащим ни `delivery_address`, ни `delivery_address_id`

#### Scenario: DELIVERY with saved address
- **WHEN** пользователь выбрал DELIVERY + "Сохранённый", выбрал адрес с `id = 'a1'`, Submit
- **THEN** body SHALL содержать `delivery_address_id: 'a1'`
- **AND** body SHALL НЕ содержать поля `delivery_address`

#### Scenario: DELIVERY with new address
- **WHEN** пользователь выбрал DELIVERY + "Новый", автокомплит дал `{ text: 'X', lat: 1, lon: 2 }`, заполнил `apartment: '5'`, Submit
- **THEN** body SHALL содержать `delivery_address: { text: 'X', lat: 1, lon: 2, apartment: '5' }`
- **AND** body SHALL НЕ содержать поля `delivery_address_id`

### Requirement: Save-for-future creates persistent address

При выборе ветки "Новый адрес" + чекбокс "Сохранить для следующего заказа" = true клиент SHALL после успешного `POST /api/v1/orders` дополнительно вызвать `POST /api/v1/profile/addresses` с теми же полями адреса. Неудача сохранения SHALL НЕ откатывать успешно созданный order (order уже создан — приоритет). Ошибку сохранения адреса SHALL логировать (console.warn / toast) без блокировки перехода на страницу статуса заказа.

#### Scenario: Save-for-future on successful order
- **WHEN** новый адрес, checkbox включён, `POST /orders` вернул 201
- **THEN** клиент SHALL вызвать `POST /api/v1/profile/addresses` с полями адреса
- **AND** даже если `POST /addresses` вернёт 409/500 — переход на страницу статуса заказа SHALL произойти

#### Scenario: Save-for-future off
- **WHEN** checkbox выключен
- **THEN** SHALL НЕ вызываться `POST /api/v1/profile/addresses`

### Requirement: Checkout renders delivery validation errors

При ответе `409 Conflict` от `POST /api/v1/orders` клиент SHALL отобразить `detail` как локализованное сообщение об ошибке доставки. Форма SHALL оставаться открытой; пользователь SHALL иметь возможность изменить адрес и повторить submit без перезагрузки страницы.

#### Scenario: Out-of-radius 409
- **WHEN** сервер вернул 409 с `detail` соответствующим out-of-radius
- **THEN** SHALL быть отображено локализованное сообщение (`errors.delivery.outOfRadius` или `detail` как есть, если уже локализован сервером)
- **AND** форма SHALL остаться видимой и интерактивной

