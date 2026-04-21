## 1. Prerequisites

- [x] 1.1 PREREQ [web-admin] Подтвердить, что `dashboard-api` (merge_order 1) либо уже
      merge'нут в `admin_ui_phase`, либо shape `AdminStatsResponse` совпадает со спекой
      в `docs/phase6-plan.yaml` (поле `range_start`, `range_end`, `revenue_kopecks`,
      `orders_count`, `popular_items[]` с `name_ru`/`name_en`/`quantity`). Frontend-тесты
      mock'ают API, поэтому отсутствие merge не блокирует работу.

## 2. Money helper

- [x] 2.1 RED [web-admin] Создать `web/admin/src/lib/money.test.ts` с тестами
      `formatKopecks(1234500, 'ru')` содержит '12' + '345' + valid currency mark, и
      `formatKopecks(0, 'ru')` содержит '0' + currency mark, и для `locale='en'`
      формат не падает. Импорт из `./money` → ImportError (файл ещё не существует).
- [x] 2.2 GREEN [web-admin] Создать `web/admin/src/lib/money.ts` с
      `formatKopecks(kopecks: number, locale: 'ru'|'en'): string` через `Intl.NumberFormat`
      (`ru-RU`/`en-US`, `style:'currency'`, `currency:'RUB'`, `minimumFractionDigits:2`).
      Проходит RED tests из 2.1.

## 3. API client

- [x] 3.1 RED [web-admin] Создать `web/admin/src/api/admin-stats.test.ts`. Mock
      `@/api/client` → `authenticatedFetch`. Тесты:
      (a) `getAdminStats('month')` → fetch вызван с `/api/v1/admin/stats?range=month`;
      (b) response JSON парсится в `AdminStatsResponse`;
      (c) non-ok response → проброс `ApiError(status, body, msg)`.
      Импорт из `@/api/admin-stats` → ImportError.
- [x] 3.2 GREEN [web-admin] Создать `web/admin/src/api/admin-stats.ts`: типы
      `AdminStatsResponse`, `PopularItem`, `StatsRange = 'today'|'week'|'month'`; экспорт
      `getAdminStats(range)` через `authenticatedFetch`. Повторное использование паттернов
      из `api/promocodes.ts` (`json<T>` wrapper).

## 4. RangeSelector component

- [x] 4.1 IMPL [web-admin] Создать `web/admin/src/pages/Dashboard/RangeSelector.tsx`:
      props `{ value: StatsRange, onChange: (next: StatsRange) => void }`. Рендер трёх
      кнопок (через `@/components/ui/button`) с `role='tab'`, `aria-selected`,
      `data-testid='range-tab-<today|week|month>'`. Локализованные лейблы из
      `pages.dashboard.range.today|week|month`.
- [x] 4.2 TEST [web-admin] Создать `web/admin/src/pages/Dashboard/RangeSelector.test.tsx`:
      (a) рендерятся три кнопки; активная — та, что соответствует `value`;
      (b) клик на `today` → `onChange('today')` вызывается ровно 1 раз;
      (c) `aria-selected` правильно установлено.

## 5. StatsCards component

- [x] 5.1 IMPL [web-admin] Создать `web/admin/src/pages/Dashboard/StatsCards.tsx`:
      props `{ revenueKopecks: number, ordersCount: number, locale: 'ru'|'en' }`. Две
      карточки: revenue (через `formatKopecks`) + orders_count. Лейблы — из
      `pages.dashboard.cards.revenue` и `pages.dashboard.cards.orders`.
- [x] 5.2 TEST [web-admin] Создать `web/admin/src/pages/Dashboard/StatsCards.test.tsx`:
      (a) `revenueKopecks=1234500`, `locale='ru'` → первая карточка содержит '12', '345',
      currency mark; (b) `ordersCount=42` рендерится; (c) zero-values отрисовываются.

## 6. PopularItemsList component

- [x] 6.1 IMPL [web-admin] Создать `web/admin/src/pages/Dashboard/PopularItemsList.tsx`:
      props `{ items: PopularItem[], locale: 'ru'|'en' }`. Таблица (через
      `@/components/ui/table`) с двумя колонками: `name` (по locale) и `quantity`.
      Header'ы из `pages.dashboard.popular.column.name|quantity`. Пустой список →
      сообщение `pages.dashboard.popular.empty`.
- [x] 6.2 TEST [web-admin] Создать `web/admin/src/pages/Dashboard/PopularItemsList.test.tsx`:
      (a) rows рендерятся в переданном порядке; (b) `locale='ru'` использует `name_ru`,
      `locale='en'` — `name_en`; (c) `items=[]` → empty-message, tbody без data-строк.

## 7. DashboardPage + re-export + i18n

- [x] 7.1 IMPL [web-admin] Создать `web/admin/src/pages/Dashboard/DashboardPage.tsx`:
      page компонент. State: `range`, `data`, `loading`, `error`. `useEffect` на `range`
      → вызов `getAdminStats(range)`. Рендерит title + description + RangeSelector +
      StatsCards (когда `data`) или loading/error. Locale определяется через
      `useTranslation().i18n.language.startsWith('ru') ? 'ru' : 'en'`.
- [x] 7.2 IMPL [web-admin] Создать `web/admin/src/pages/Dashboard/index.tsx`:
      `export { DashboardPage } from './DashboardPage';`.
- [x] 7.3 IMPL [web-admin] Обновить `web/admin/src/pages/DashboardPage.tsx`:
      заменить содержимое на `export { DashboardPage } from './Dashboard';` (re-export для
      существующего импорта из `App.tsx`).
- [x] 7.4 IMPL [web-admin] Добавить ключи в `web/admin/src/i18n/locales/ru/common.json`:
      `pages.dashboard.range.today/week/month`,
      `pages.dashboard.cards.revenue/orders`,
      `pages.dashboard.popular.title/column.name/column.quantity/empty`.
      Переводы: "Сегодня/Неделя/Месяц", "Выручка/Количество заказов",
      "Популярные позиции/Позиция/Количество/Нет данных за период".
- [x] 7.5 IMPL [web-admin] Добавить те же ключи в
      `web/admin/src/i18n/locales/en/common.json`. Переводы:
      "Today/Week/Month", "Revenue/Orders", "Popular Items/Item/Quantity/No data for this period".
- [x] 7.6 TEST [web-admin] Создать
      `web/admin/src/pages/Dashboard/DashboardPage.test.tsx`. Mock
      `@/api/admin-stats`. Тесты:
      (a) mount → `getAdminStats` вызван с `'month'`;
      (b) клик `today` таб → refetch с `'today'`;
      (c) ответ с `popular_items` → строки появляются;
      (d) API reject с `ApiError(500)` → показан error-notice, не крашится.

## 8. Routing — admin-only `/`

- [x] 8.1 IMPL [web-admin] В `web/admin/src/App.tsx` заменить
      `<Route index element={<DashboardPage />} />` на inline-гейт:
      создать локальный функциональный компонент `DashboardIndex`, который через
      `useCurrentRole()` проверяет роль: `'admin'` → `<DashboardPage/>`, иначе
      `<Navigate to='/orders' replace/>`. Использовать этот компонент в `<Route index/>`.
- [x] 8.2 TEST [web-admin] Обновить `web/admin/src/App.test.tsx`: добавить тесты
      (a) role=admin на `/` → в документе есть элемент из DashboardPage (например, текст
      `pages.dashboard.title` "Панель управления"/"Dashboard"); (b) role=barista на `/`
      → рендерится `OrdersPage` (текст `pages.orders.title`). Существующие тесты НЕ
      ломать.

## 9. Verify

- [x] 9.1 VERIFY [web-admin] Прогнать `npm run test` в `web/admin` — все тесты, включая
      новые DashboardPage-тесты и обновлённый App.test, должны быть зелёными.
- [x] 9.2 VERIFY [web-admin] Прогнать `npm run typecheck` (или `tsc --noEmit`) в
      `web/admin` — без ошибок типизации.
- [x] 9.3 VERIFY [web-admin] Прогнать `npm run lint` в `web/admin` (если есть) — без новых
      нарушений.
