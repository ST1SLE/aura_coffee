## ADDED Requirements

### Requirement: Profile page route
The web-customer SPA SHALL have a `/profile` route accessible only to authenticated customers. Unauthenticated users navigating to `/profile` SHALL be redirected to the login screen.

#### Scenario: Authenticated customer accesses profile
- **WHEN** authenticated customer navigates to `/profile`
- **THEN** the profile page renders with the customer's profile data

#### Scenario: Unauthenticated user accesses profile
- **WHEN** unauthenticated user navigates to `/profile`
- **THEN** the app redirects to the login screen

### Requirement: Profile data display
The profile page SHALL display: masked phone number (read-only), display name (editable), and preferred language (editable via switcher). The page SHALL fetch profile data from `GET /api/v1/profile` on mount.

#### Scenario: Profile data loaded and displayed
- **WHEN** profile page mounts
- **THEN** it calls `GET /api/v1/profile` and renders phone (masked, read-only), display name, and current language

#### Scenario: Loading state
- **WHEN** profile data is being fetched
- **THEN** the page shows a loading indicator

#### Scenario: API error on load
- **WHEN** `GET /api/v1/profile` returns an error
- **THEN** the page displays an error message with a retry option

### Requirement: Edit display name
The profile page SHALL allow the customer to edit their display name and save it via `PATCH /api/v1/profile`. Validation: 1–100 characters, non-empty.

#### Scenario: Successful name update
- **WHEN** customer edits display name to "Михаил" and clicks save
- **THEN** the app sends `PATCH /api/v1/profile` with `{display_name: "Михаил"}` and shows updated name on success

#### Scenario: Validation error — empty name
- **WHEN** customer clears the display name field and attempts to save
- **THEN** the app shows a client-side validation error without making an API call

### Requirement: Language switcher
The profile page SHALL provide a language switcher (RU / EN). Changing language SHALL update `preferred_language` via `PATCH /api/v1/profile` and switch the UI language via `i18next.changeLanguage()`.

#### Scenario: Switch language to English
- **WHEN** customer selects "EN" in the language switcher
- **THEN** the app sends `PATCH /api/v1/profile` with `{preferred_language: "en"}`, and on success calls `i18next.changeLanguage("en")`

#### Scenario: Language switch API failure
- **WHEN** the PATCH request for language change fails
- **THEN** the UI language remains unchanged and an error message is shown

### Requirement: Responsive mobile-first layout
The profile page SHALL follow mobile-first responsive design consistent with the rest of web-customer. It SHALL use shadcn/ui components and Tailwind CSS utility classes.

#### Scenario: Mobile viewport
- **WHEN** profile page is viewed on a mobile device (viewport < 768px)
- **THEN** the layout renders in a single column with appropriately sized touch targets

#### Scenario: Desktop viewport
- **WHEN** profile page is viewed on desktop (viewport ≥ 768px)
- **THEN** the layout uses available space appropriately (centered content, max-width constraint)

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
