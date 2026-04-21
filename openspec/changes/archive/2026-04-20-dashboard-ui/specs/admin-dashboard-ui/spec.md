# admin-dashboard-ui

Ссылки на источники: PDD §4.5 Admin Panel (аналитика), PDD §7.1 Phase 6 item 1, INV-010.

## ADDED Requirements

### Requirement: Dashboard API client

Админ-панель SHALL предоставлять модуль `web/admin/src/api/admin-stats.ts`, экспортирующий
типизированную функцию `getAdminStats(range)`, которая выполняет `GET /api/v1/admin/stats`
с query-параметром `range` ∈ {`today`, `week`, `month`} и возвращает `AdminStatsResponse`
({ `range`, `range_start`, `range_end`, `revenue_kopecks: number`, `orders_count: number`,
`popular_items: { name_ru, name_en, quantity }[]` }). Запрос MUST использовать
`authenticatedFetch` из `@/api/client`. Ошибки MUST пробрасываться как `ApiError`.
(Источник: PDD §4.5, §7.1 Phase 6 item 1.)

#### Scenario: Successful fetch with default range

- **WHEN** вызывается `getAdminStats('month')`
- **THEN** выполняется HTTP GET на `/api/v1/admin/stats?range=month` с `Authorization: Bearer <token>`
- **AND** возвращается разобранный JSON-ответ в виде `AdminStatsResponse`

#### Scenario: Propagates non-ok response as ApiError

- **WHEN** сервер возвращает 403 с JSON `{"detail":"forbidden"}`
- **THEN** `getAdminStats('today')` отклоняется с `ApiError` где `status === 403`
- **AND** `body` содержит `{detail: 'forbidden'}`

#### Scenario: Rejects unknown range at type level

- **WHEN** функция вызывается со значением, не входящим в литеральный тип
- **THEN** TypeScript-компиляция падает (type-level guard)
- **AND** runtime behavior не определяется (тест опускаем, проверяем компиляцией).

### Requirement: DashboardPage renders stats for the selected range

Админ-панель SHALL содержать страницу `web/admin/src/pages/Dashboard/DashboardPage.tsx`,
которая при mount'е запрашивает статистику за `range='month'` и отображает результат.
(Источник: PDD §7.1 Phase 6 item 1.)

#### Scenario: Mount with default range

- **WHEN** `DashboardPage` монтируется
- **THEN** вызывается `getAdminStats('month')` ровно один раз
- **AND** в пока запрос идёт — показывается индикатор загрузки (`common.loading`)
- **AND** после ответа показываются карточки и список популярных позиций

#### Scenario: Switch range triggers refetch

- **WHEN** пользователь выбирает `today` в `RangeSelector`
- **THEN** `getAdminStats('today')` вызывается
- **AND** предыдущие данные заменяются значениями из нового ответа

#### Scenario: API error shows error notice

- **WHEN** `getAdminStats` отклоняется с `ApiError(status=500)`
- **THEN** страница показывает сообщение об ошибке (toast / inline alert с текстом из `common.error`)
- **AND** страница не крашится (ErrorBoundary не срабатывает)

### Requirement: RangeSelector component

Админ-панель SHALL содержать компонент `RangeSelector`, отображающий сегмент-кнопки
"Сегодня | Неделя | Месяц" (по текущему i18n-языку). Компонент MUST принимать `value: Range` и
`onChange: (next: Range) => void`, где `Range = 'today'|'week'|'month'`. Выбранная кнопка MUST
иметь визуальное отличие (aria-selected="true").

#### Scenario: Renders three options

- **WHEN** компонент рендерится с `value='month'`
- **THEN** отображаются три кнопки: `today`, `week`, `month`
- **AND** у кнопки `month` атрибут `aria-selected="true"`
- **AND** у остальных — `aria-selected="false"`

#### Scenario: Click dispatches onChange

- **WHEN** пользователь кликает кнопку `today`
- **THEN** вызывается `onChange('today')` ровно один раз

#### Scenario: Click on already-selected is idempotent

- **WHEN** `value='today'` и пользователь кликает `today`
- **THEN** `onChange` вызывается с `'today'` (компонент не фильтрует — решение за родителем)

### Requirement: StatsCards component

Админ-панель SHALL содержать компонент `StatsCards`, принимающий `revenueKopecks: number`,
`ordersCount: number`, `locale: 'ru'|'en'`. Рендерит ДВЕ карточки: выручка
(в локализованной валютной форме через `formatKopecks`) и количество заказов.
(Источник: PDD §4.5 Admin Panel analytics, §7.1 Phase 6 item 1.)

#### Scenario: Renders formatted revenue

- **WHEN** компонент рендерится с `revenueKopecks=1234500`, `locale='ru'`
- **THEN** первая карточка содержит подстроки `12`, `345`, `00` и валютный знак `₽` (или `RUB`
  в зависимости от ICU-данных)

#### Scenario: Zero revenue

- **WHEN** `revenueKopecks=0`, `ordersCount=0`
- **THEN** карточка выручки показывает `0,00 ₽` (ru-locale) или аналогичный nil-формат
- **AND** карточка заказов показывает `0`

#### Scenario: English locale

- **WHEN** `locale='en'`
- **THEN** разделители групп/десятичных — точка/запятая в en-формате; значения отрисовываются без краша

### Requirement: PopularItemsList component

Админ-панель SHALL содержать компонент `PopularItemsList`, принимающий
`items: { name_ru: string, name_en: string, quantity: number }[]` и `locale: 'ru'|'en'`.
Рендерит таблицу: `name` по локали (`name_ru` при `ru`, иначе `name_en`), `quantity`. Порядок
— как получен от сервера (сервер уже сортирует по `quantity` DESC). При пустом `items` MUST
отображать сообщение `pages.dashboard.popular.empty`.

#### Scenario: Renders rows in given order

- **WHEN** передан `items=[{name_ru:'Латте',name_en:'Latte',quantity:28},{name_ru:'Капучино',name_en:'Cappuccino',quantity:17}]`, `locale='ru'`
- **THEN** первая строка содержит `Латте` и `28`
- **AND** вторая строка содержит `Капучино` и `17`

#### Scenario: Empty list shows empty state

- **WHEN** `items=[]`
- **THEN** отображается текст `pages.dashboard.popular.empty` (Нет данных за период / No data
  for this period)
- **AND** тело таблицы не содержит data-строк

#### Scenario: Uses English names in en-locale

- **WHEN** `locale='en'` и `items=[{name_ru:'Латте',name_en:'Latte',quantity:28}]`
- **THEN** строка содержит `Latte`, не `Латте`

### Requirement: Money formatting helper

Админ-панель SHALL предоставлять helper `formatKopecks(kopecks: number, locale: 'ru'|'en'): string`
в `web/admin/src/lib/money.ts`. Helper MUST конвертировать копейки в рубли (деление на 100) и
форматировать через `Intl.NumberFormat` со `style='currency'`, `currency='RUB'` и
`minimumFractionDigits=2`.

#### Scenario: Formats large amount in ru-locale

- **WHEN** вызывается `formatKopecks(1234500, 'ru')`
- **THEN** возвращаемая строка содержит `12`, `345`, `,00` (ru-locale) или `.00` (зависит от ICU);
  тест допускает оба вида десятичного разделителя
- **AND** строка содержит валютный индикатор `₽` либо `RUB`

#### Scenario: Formats zero

- **WHEN** вызывается `formatKopecks(0, 'ru')`
- **THEN** строка содержит `0` и валютный индикатор

#### Scenario: Pure function

- **WHEN** helper вызывается дважды с одинаковыми аргументами
- **THEN** возвращаются равные строки (без побочных эффектов на время/локаль системы)

### Requirement: RBAC gate on index route

Админ-панель SHALL гарантировать, что index-маршрут `/` рендерит `DashboardPage` только
для роли `admin`. Для роли `barista` (залогинен в admin-SPA) `/` MUST редиректить на
`/orders`. Для отсутствующей роли / токена — срабатывает внешний `ProtectedRoute` (редирект
на `/login`). (Источник: PDD §4.5, INV-010.)

#### Scenario: Admin sees dashboard

- **WHEN** `localStorage.staffRole='admin'`, `accessToken` задан, пользователь переходит на `/`
- **THEN** рендерится `DashboardPage` (наличие тестируемого якоря, например, текста
  `pages.dashboard.title` или `data-testid='dashboard-page'`)

#### Scenario: Barista redirects to orders

- **WHEN** `localStorage.staffRole='barista'`, `accessToken` задан, пользователь переходит на `/`
- **THEN** происходит редирект на `/orders`
- **AND** `DashboardPage` НЕ монтируется (API не вызывается)

#### Scenario: Courier redirects to courier shell

- **WHEN** `localStorage.staffRole='courier'` — существующий `ProtectedRoute` внешнего wrapper'а
  уже редиректит на `/courier`
- **THEN** поведение НЕ меняется этим change'ом (inner-гейт недостижим для курьера)

### Requirement: i18n keys for dashboard

Админ-панель SHALL содержать в `web/admin/src/i18n/locales/ru/common.json` и
`web/admin/src/i18n/locales/en/common.json` ключи:

- `pages.dashboard.title` (существующий — не трогаем семантику)
- `pages.dashboard.description` (существующий)
- `pages.dashboard.range.today`
- `pages.dashboard.range.week`
- `pages.dashboard.range.month`
- `pages.dashboard.cards.revenue`
- `pages.dashboard.cards.orders`
- `pages.dashboard.popular.title`
- `pages.dashboard.popular.column.name`
- `pages.dashboard.popular.column.quantity`
- `pages.dashboard.popular.empty`

#### Scenario: Russian translations present

- **WHEN** `i18n.changeLanguage('ru')` применён
- **THEN** `t('pages.dashboard.range.today')` возвращает `Сегодня` (не raw key)
- **AND** все 9 новых ключей присутствуют в `ru/common.json` с непустыми строками

#### Scenario: English translations present

- **WHEN** `i18n.changeLanguage('en')` применён
- **THEN** `t('pages.dashboard.range.today')` возвращает `Today`
- **AND** все 9 новых ключей присутствуют в `en/common.json` с непустыми строками
