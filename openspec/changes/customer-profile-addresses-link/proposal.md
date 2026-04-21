## Why

Маршрут `/profile/addresses` и `AddressesPage` зарегистрированы и после мёржа `feat/customer-addresses-api-fix` полностью работоспособны, но с `ProfilePage` (`/profile`) на них нет ни одной ссылки. Пользователь, который не знает URL наизусть, не может управлять адресами доставки из UI. Это ломает §1.4–1.5 сценария phase-6 manual-QA, где ожидается переход «Профиль → Адреса».

Требование "discoverability of saved addresses from the profile screen" нигде в spec-ах не сформулировано — ни `user-profile-screen` (описывает телефон/имя/язык), ни `customer-addresses-ui` (описывает саму страницу адресов), так что фикс обязан прийти как новое требование, а не как баг-фикс без спеки.

## What Changes

- `ProfilePage.tsx` получает видимый entry-point на `/profile/addresses` — карточка/кнопка по паттерну существующего `LoyaltyCard` (ссылка на `/profile/loyalty`). Форма связи — `<Link to="/profile/addresses">` внутри карточки.
- Локализация: новый ключ `pages.profile.addressesLink.*` в `web/customer/src/i18n/locales/{ru,en}/common.json` (заголовок + подпись-тизер). Ключ `pages.addresses.title` не переиспользуем, чтобы не связывать копирайт двух экранов жёстко.
- Unit-тест: проверка, что `ProfilePage` рендерит `<Link>` с `href="/profile/addresses"`, по образцу `LoyaltyCard.test.tsx:42-55`.

## Capabilities

### New Capabilities
(нет)

### Modified Capabilities
- `user-profile-screen`: добавляется требование "Addresses navigation entry" — страница профиля SHALL содержать навигационную ссылку на `/profile/addresses`.

## Impact

- Код: `web/customer/src/pages/ProfilePage.tsx`, `web/customer/src/i18n/locales/ru/common.json`, `web/customer/src/i18n/locales/en/common.json`, новый `web/customer/src/pages/ProfilePage.test.tsx` (или расширение существующего).
- Backend / API: не затрагиваются.
- MVP-фаза: относится к phase-4 (Delivery) как отложенный follow-up merge `feat/customer-addresses-api-fix` (2026-04-20); разблокирует phase-6 manual-QA §1.4–1.5.
- PDD §3 (Delivery), §5.2 (Saved delivery addresses) — UI-часть становится end-to-end достижимой из `/profile`, как предполагалось архитектурно.
- Инвариантов не затрагивает: без RBAC/PII/state-machine изменений. `ProtectedRoute` уже охраняет `/profile/addresses`.

## Non-Goals

- **Не трогаем AddressesPage и AddressForm.** Их поведение и контракт с backend уже зафиксированы `customer-addresses-ui` и только что смёрженным фиксом.
- **Не меняем backend / схему `delivery_addresses`.** Фронтовая discoverability — чисто UI-изменение.
- **Не добавляем нижнюю/боковую навигацию уровня `Layout`.** Entry-point живёт внутри `ProfilePage` по паттерну `LoyaltyCard`, а не в глобальном chrome.
- **Не создаём отдельный hub-экран "Мои настройки".** Scope ограничен одной ссылкой.
- **Не правим `/checkout`-пресет адресов.** Это уже сделано мёрж-коммитом `eb4182b` (CheckoutPage saved-vs-new preselect fix).
