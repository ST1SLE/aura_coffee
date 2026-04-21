**Affected modules:** `[web-customer]`

## Context

После мёржа `feat/customer-addresses-api-fix` (commit `eb4182b`) маршрут `/profile/addresses` и страница `AddressesPage` полностью функциональны: CRUD, set-default, delete — всё работает против реальной `/api/v1/profile/addresses`. Однако `ProfilePage.tsx` (маршрут `/profile`, охранён `ProtectedRoute`) не содержит ссылки на этот маршрут. Существующая карточка `LoyaltyCard` — единственный пример discoverability из `/profile` в подстраницу, она ссылается на `/profile/loyalty`.

Spec `user-profile-screen` перечисляет требования к содержимому `/profile` (телефон, имя, язык, logout, layout), но discoverability адресов не упоминает. Значит, корректный фикс — не молчаливый UI-твик, а добавление нового требования к этой capability.

## Goals / Non-Goals

**Goals:**
- `/profile` SHALL рендерить навигационную ссылку на `/profile/addresses`, видимую всем авторизованным пользователям.
- Паттерн — мини-карточка по образу `LoyaltyCard`, но без динамических данных (список адресов за один клик, не inline-превью).
- Тест SHALL проверять наличие ссылки и её `href`, mirror `LoyaltyCard.test.tsx:42-55`.
- i18n: RU + EN, ключ `pages.profile.addressesLink.{title,subtitle}`.

**Non-Goals:**
- Не превью списка адресов на ProfilePage (как LoyaltyCard показывает balance). Адреса — короткий список, но требует GET; усложнение без выгоды.
- Не изменять `customer-addresses-ui` spec.
- Не трогать глобальную навигацию (`Layout.tsx`).

## Decisions

### D1. Форма entry-point: карточка-ссылка, не голая кнопка

**Выбор:** `<Link to="/profile/addresses">` обёрнутый в стилизованный `<div>`-карточку с иконкой/текстом, по паттерну `LoyaltyCard`.

**Альтернативы:**
- (a) Простая `<Button>` с `onClick={() => navigate('/profile/addresses')}`. Отвергнуто: визуально не ложится в уже установленный паттерн карточек на ProfilePage (LoyaltyCard — карточка).
- (b) Повторить `LoyaltyCard` целиком — сделать `AddressesCard` с превью количества адресов. Отвергнуто: требует отдельного `GET /api/v1/profile/addresses` из `ProfilePage`, что дублирует запрос, делаемый `AddressesPage` после перехода. Превью не несёт достаточно информации, чтобы оправдать этот запрос.

### D2. i18n-ключи: собственные, а не переиспользование `pages.addresses.title`

**Выбор:** новые ключи `pages.profile.addressesLink.title` (напр. "Адреса доставки" / "Delivery addresses") и `pages.profile.addressesLink.subtitle` (напр. "Управление сохранёнными адресами" / "Manage saved addresses").

**Альтернатива:** переиспользовать `pages.addresses.title` из `customer-addresses-ui`. Отвергнуто: копирайт карточки-тизера и заголовок страницы концептуально разные тексты; связывать их — создавать будущую боль при редактировании копии.

### D3. Позиция на странице

**Выбор:** сразу после блока "Язык", перед `<LoyaltyCard />`. Адреса — настройка доставки, LoyaltyCard — отчёт по балансу; настройки группируются сверху, отчёты снизу.

**Альтернатива:** в самом низу рядом с кнопкой Logout. Отвергнуто: Logout — финальное деструктивное действие, ссылка рядом с ним визуально отвлекает.

### D4. Тест

**Выбор:** новый `web/customer/src/pages/ProfilePage.test.tsx`. Минимум один тест, mirror `LoyaltyCard.test.tsx:42-55`: рендер `ProfilePage` с замоканным `getProfile`, ожидание `<a href="/profile/addresses">` в DOM.

Не расширяем существующие тесты (их нет для `ProfilePage` — только для `LoyaltyCard`). Новый файл, изолированный вход.

## Risks / Trade-offs

- **[Risk]** Добавление новой карточки увеличивает высоту профильного экрана на мобилке → возможен скролл на мелких экранах.
  **Mitigation:** mobile-first уже в `user-profile-screen` Requirement "Responsive mobile-first layout" — Tailwind-утилиты сами решат. Карточка компактна (title + subtitle, без иконки или превью), добавит ~60px.

- **[Risk]** Разработчик позже добавит превью (счётчик адресов, default-адрес в subtitle) → появится сетевой запрос из ProfilePage и связь между экранами усилится.
  **Mitigation:** D1 явно отвергает этот путь. Если потребуется — отдельная change.

- **[Trade-off]** Собственные i18n-ключи (D2) дублируют слово "адреса" в двух местах. Цена — минимальная; выгода — независимая эволюция копирайта.

## Migration Plan

Не применимо. UI-изменение без схемы/API. Rollback = revert одного коммита.

## Open Questions

Нет. Scope уплотнён до одной ссылки; все решения приняты выше.
