## Why

Сегодня `/admin` стартовая страница — stub с заголовком. PDD §7.1 Phase 6 item 1 требует рабочий
дашборд для admin: выручка, кол-во заказов и популярные позиции за выбранный период (сегодня /
неделя / месяц). Backend `GET /api/v1/admin/stats` уже готов (dashboard-api, merge_order 1
в `docs/phase6-plan.yaml`). Фронту нужен UI-потребитель, иначе MVP admin-панели не закрыт.

## What Changes

- Новый API-клиент `web/admin/src/api/admin-stats.ts` с функцией `getAdminStats(range)` →
  `AdminStatsResponse` (`revenue_kopecks`, `orders_count`, `popular_items[]`).
- Новая директория `web/admin/src/pages/Dashboard/` (`index.tsx`, `DashboardPage.tsx`,
  `RangeSelector.tsx`, `StatsCards.tsx`, `PopularItemsList.tsx`), заменяющая текущий
  stub `pages/DashboardPage.tsx` (файл остаётся как re-export для `App.tsx`).
- `RangeSelector` — segmented control "Сегодня | Неделя | Месяц"; выбранное значение
  хранится в локальном state компонента (default `month`).
- `StatsCards` — две карточки: выручка (копейки → ₽) и `orders_count`.
- `PopularItemsList` — таблица top-10: `name` (по текущему i18n-языку) + `quantity`, либо
  empty state "Нет данных за период".
- Новый `web/admin/src/lib/money.ts` с `formatKopecks(value, locale)` через
  `Intl.NumberFormat(locale, { style: 'currency', currency: 'RUB' })`.
- `App.tsx` — обернуть `<Route index element={<DashboardPage/>}/>` во внутренний
  `<ProtectedRoute allowedRoles={['admin']}>` (точно как `/promos`). Если баристу
  редиректит `/` — остаётся в внешней обёртке, но не попадает на дашборд.
- i18n `ru/en/common.json`: ключи `pages.dashboard.range.*`, `pages.dashboard.cards.*`,
  `pages.dashboard.popular.*` (title/description уже есть).
- Loading: текстовая "Загрузка..." (pattern Promos). 403 → `ApiError`
  проброс; 401 уже обрабатывается в `authenticatedFetch` (редирект на `/login`).
  Пустой `popular_items` → строка "Нет данных за период".

## Capabilities

### New Capabilities
- `admin-dashboard-ui`: Фронт админ-дашборда (page + api client + RBAC-обёртка маршрута +
  i18n-ключи + money-helper + loading/empty states).

### Modified Capabilities
(пусто — создаётся новый spec, существующие не затрагиваются. `admin-auth-ui`/`frontend-routing`
описывают общие паттерны, конкретная RBAC-обёртка маршрута дашборда — частный случай, покрывается
новым spec'ом.)

## Impact

- Код: `web/admin/src/api/admin-stats.ts` (new), `web/admin/src/api/admin-stats.test.ts` (new),
  `web/admin/src/pages/Dashboard/` (new), `web/admin/src/pages/DashboardPage.tsx` (re-export),
  `web/admin/src/lib/money.ts` (new), `web/admin/src/App.tsx` (inner RBAC-wrapper для `/`),
  `web/admin/src/i18n/locales/{ru,en}/common.json` (дополнить `pages.dashboard.*`).
- API: потребляется существующий `GET /api/v1/admin/stats?range=today|week|month`. Сервер не
  меняется.
- Зависимости: `react-i18next`, `@testing-library/react`, vitest (уже в проекте). Графические
  библиотеки НЕ добавляются.
- Роли: `/` доступен из внешней обёртки `admin+barista` layout'у, но содержимое (DashboardPage)
  открывается только admin — для barista внутренний `ProtectedRoute` сделает `Navigate` на
  `/` (loop). Чтобы избежать loop'а, баристу редиректит не на `/`, а сайдбар-фильтр ведёт сразу
  на `/orders` при логине — подробнее в design.md.
- Безопасность: backend — авторитет (INV-010). UI-гейт — UX-согласованность, не безопасность.
- MVP phase: 6 (item 1).
- Ссылки: PDD §4.5 Admin Panel, §7.1 Phase 6 item 1, INV-010.

## Non-Goals

- Графики / временные ряды (charts). MVP ограничен карточками + списком; charts — отдельный
  Phase 7+ тикет.
- Polling stats (PDD §4.5 `≤5s` относится к barista-feed заказов, не к дашборду). Пользователь
  обновляет данные ручным переключением range.
- Экспорт (CSV/Excel) — out of scope Phase 6.
- Фильтры по типу заказа (pickup vs delivery), по курьеру, по категории меню — premature,
  backend не группирует по этим осям.
- Edit / admin-actions над статистикой — дашборд read-only.
- Кэш в localStorage / IndexedDB — каждый переключатель делает свежий fetch.
