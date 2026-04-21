## ADDED Requirements

### Requirement: Addresses navigation entry

Относится к PDD §3 (Delivery) и §5.2 (Saved delivery addresses). Страница `/profile` (`web/customer/src/pages/ProfilePage.tsx`) SHALL рендерить навигационную ссылку на `/profile/addresses`, видимую всем авторизованным пользователям без дополнительных условий. Ссылка SHALL быть оформлена как карточка-тизер (паттерн `LoyaltyCard`) с локализованными заголовком и подзаголовком из ключей `pages.profile.addressesLink.title` и `pages.profile.addressesLink.subtitle`. Карточка SHALL НЕ инициировать сетевой запрос на `GET /api/v1/profile/addresses` из `ProfilePage` — превью списка не входит в scope.

#### Scenario: Link rendered on profile page
- **WHEN** авторизованный пользователь открывает `/profile`
- **THEN** в DOM SHALL присутствовать элемент с `href="/profile/addresses"`
- **AND** элемент SHALL содержать локализованный заголовок из ключа `pages.profile.addressesLink.title`

#### Scenario: Click navigates to addresses
- **WHEN** пользователь кликает по карточке-ссылке
- **THEN** роутер SHALL перейти на `/profile/addresses`
- **AND** рендерится `AddressesPage` (поведение определено `customer-addresses-ui`)

#### Scenario: No prefetch from ProfilePage
- **WHEN** `ProfilePage` монтируется
- **THEN** клиент SHALL НЕ вызывать `GET /api/v1/profile/addresses` как часть рендера профиля
- **AND** запрос SHALL быть сделан только после перехода на `/profile/addresses` (существующее поведение `AddressesPage`)
