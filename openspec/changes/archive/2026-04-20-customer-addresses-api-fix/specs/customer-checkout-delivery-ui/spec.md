## MODIFIED Requirements

### Requirement: Delivery block offers saved-vs-new XOR choice

Relates to PDD §5.2 (delivery address selection). Syncs SPA на backend-поле `is_default`.

**Previously:**
- Preselect saved address with `is_primary: true`.

**Now:**
При `type = DELIVERY` и наличии хотя бы одного сохранённого адреса у пользователя блок адреса SHALL предложить radio-выбор между "Сохранённый" и "Новый". При выборе "Сохранённый" — radio-список всех сохранённых адресов (предвыбран адрес с `is_default: true` если есть; иначе первый элемент списка). При выборе "Новый" — `AddressAutocomplete` + поля `apartment/entrance/floor/comment` + чекбокс "Сохранить для следующего заказа". Если у пользователя нет сохранённых адресов, ветка "Сохранённый" SHALL быть скрыта, а форма нового адреса SHALL быть активна сразу.

#### Scenario: Saved addresses exist — default preselected
- **WHEN** `GET /api/v1/profile/addresses` возвращает 2 адреса, где один имеет `is_default: true`, пользователь выбрал DELIVERY
- **THEN** SHALL быть показан radio-выбор "Сохранённый / Новый"
- **AND** по умолчанию SHALL быть выбран "Сохранённый"
- **AND** адрес с `is_default: true` SHALL быть предвыбран в списке сохранённых

#### Scenario: No default flag — fallback to first
- **WHEN** сервер возвращает 2 адреса, оба с `is_default: false`
- **THEN** предвыбран SHALL быть первый адрес списка

#### Scenario: No saved addresses — new form only
- **WHEN** `GET /api/v1/profile/addresses` возвращает пустой список
- **THEN** radio-выбор "Сохранённый/Новый" SHALL НЕ отображаться
- **AND** форма нового адреса SHALL быть доступна сразу
