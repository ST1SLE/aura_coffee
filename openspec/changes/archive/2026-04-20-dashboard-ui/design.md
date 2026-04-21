## Context

Затронутые модули: **[web-admin]**.

`web/admin` — существующий React 19 + Vite SPA с уже сложившимися паттернами:
- API-клиенты в `src/api/*.ts` поверх `authenticatedFetch` (`src/api/client.ts`). Ошибки
  бросаются как `ApiError(status, body, message)`; 401 уже обрабатывается централизованно
  (редирект на `/admin/login`).
- Страницы в `src/pages/<Feature>/` с `index.tsx` (re-export) + `<Feature>Page.tsx` + вложенные
  компоненты и `*.test.tsx`.
- Маршруты в `App.tsx`. Внешняя обёртка `ProtectedRoute allowedRoles=['admin','barista']`
  + `<Layout/>` охватывает все admin/barista-страницы; отдельные маршруты заворачиваются во
  **внутренний** `ProtectedRoute allowedRoles=['admin']` (пример: `/promos`).
- Роль хранится в `localStorage` под ключом `staffRole`, читается через `getRole()` /
  `useCurrentRole()` (`src/lib/auth.ts`). Источник истины — backend (INV-010); клиентская
  проверка — UX-гейт.
- i18n — `react-i18next`, ресурсы в `src/i18n/locales/{ru,en}/common.json`. Форматирование
  чисел/валют — через `Intl.NumberFormat`, не через i18n-format.
- Тесты — `vitest` + `@testing-library/react`, mock API через `vi.mock('@/api/…')`.
- Money-helper: сегодня конверсия копейки↔рубли разбросана (в `api/promocodes.ts` —
  `toKopecks(rubles)`). Единого форматтера копейки→валютная строка нет. В текущем change'е
  вводим его в `src/lib/money.ts` (scope дашборда), чтобы последующие фичи могли переиспользовать.

Дашборд — первое использование `GET /api/v1/admin/stats`, backend для которого поставляется
в одной phase (dashboard-api, merge_order 1 предшествует dashboard-ui, merge_order 6 в
`docs/phase6-plan.yaml`). В момент разработки frontend-ветки backend может быть ещё не
merged в `admin_ui_phase`; это не блокирует фронт: тесты mock'ают API-слой.

Сегодня `/` (index) — `DashboardPage` внутри admin+barista-wrapper'а, контент — stub. Если
barista залогинится, текущий stub бесплатно увидит (он только заголовок). После этого change'а
дашборд станет admin-only: barista, попавший на `/` после логина, должен попадать на свою
рабочую страницу (`/orders`), а не смотреть на admin-редирект-loop.

## Goals / Non-Goals

**Goals:**
- Рабочий дашборд admin-only, потребляющий `GET /api/v1/admin/stats?range=…`.
- Переключение периода `today|week|month` с перезагрузкой данных.
- Форматирование копеек → валюта по текущему i18n-locale.
- Pattern-reuse: API-клиент, page-layout, тесты — как в `/promos`.
- Новый `lib/money.ts`-хелпер готов для будущих фич (orders, users, settings).
- Inner `ProtectedRoute allowedRoles=['admin']` для `/`, без loop'а у barista.

**Non-Goals:**
- Графики / charts-библиотеки.
- Polling / refresh по таймеру.
- Экспорт, drill-down, server-side фильтры помимо `range`.
- Server-side изменения (backend = в dashboard-api change).
- Переделывать существующий `LoginPage` post-login редирект (роль-специфичный redirect — отдельный
  тикет, если он нужен).

## Decisions

### D1: Роль-специфичный редирект barista с `/`

**Проблема:** внешний wrapper `Layout` охватывает `/` (admin+barista). Внутренний
`ProtectedRoute allowedRoles=['admin']` у DashboardPage сделает `Navigate to="/"`
для barista → infinite loop (`/` → admin-only → redirect на `/` → …).

**Паттерн в коде:** `ProtectedRoute` уже имеет исключение — `role === 'courier'` редиректит
на `/courier`. Расширять логику внешнего `ProtectedRoute` НЕ буду (чужая зона, чужой change).

**Альтернативы:**
1. Поменять `ProtectedRoute` так, чтобы при "роль разрешена внешнему wrapper'у, но не разрешена
   внутреннему" он редиректил на `/orders` (hard-coded).
2. Оставить loop (плохо для UX, но "безопасно").
3. Вместо inner wrapper'а — рендерить условный контент: если `role === 'admin'` → dashboard,
   иначе → `Navigate to="/orders" replace`. Inline-решение в `AppRoutes` без модификации
   `ProtectedRoute`.

**Решение (D1): вариант 3 — inline-гейт в `App.tsx`.**
```tsx
<Route index element={
  getRole() === 'admin'
    ? <DashboardPage/>
    : <Navigate to="/orders" replace/>
} />
```
Причины:
- Не трогает общий `ProtectedRoute` → scope остаётся локальным.
- Явный "edge-case" для index-маршрута: `/` не имеет смысла для barista, но у barista есть
  `/orders`. Редирект — UX, не безопасность.
- Никаких loop'ов, потому что `/orders` внутри того же внешнего wrapper'а разрешён barista.

**Компромисс:** если barista каким-то образом вручную откроет `/` с admin-токеном (невозможный
сценарий — роль = серверная), увидит admin-контент. Это совпадает с INV-010 (роль — сервер).
Для UX-однозначности достаточно.

**Проверить в тестах:** `App.test.tsx` добавить кейс:
- `role=barista` на `/` → рендерится контент страницы `/orders`, а не DashboardPage.
- `role=admin` на `/` → рендерится DashboardPage.

Если окажется, что `getRole()` нельзя вызывать на уровне routes-массива (так как это чистая
функция, возвращающая snapshot — можно), используется inline-компонент `DashboardIndex`,
который hook'ом `useCurrentRole()` принимает решение при каждом рендере.

### D2: Range state — local, не URL

PDD §4.5 не требует shareable-ссылок на стат-диапазон. Local state проще в тестах и
сохраняет контракт compact (без зависимости от location.search).
- Default: `month`.
- Храним в `useState<Range>('month')`.
- При изменении — `getAdminStats(range)` перезапрашивается.

**Альтернатива:** URL-query (`?range=today`). Отказ: добавляет синхронизацию state ↔ URL
без явной пользы (refresh страницы прокидывает default месяц — приемлемо для admin-tool).

### D3: Data-fetching — без react-query

Промос-паттерн использует ручной `useEffect + useState`. Консистентность > вводить новую
зависимость. Один endpoint, один state, один `loading` / `error` flag — достаточно.
- `loading: boolean`, `data: AdminStatsResponse | null`, `error: string | null`.
- Invariant: при смене `range` → `loading = true`, данные сохраняются до прихода новых
  (чтобы не моргать между табами). Переключение table/cards показывает предыдущие
  значения + spinner-overlay ("Загрузка..." под cards). Проще: сначала clean loading,
  перезаписать data на новое.

Для MVP берём простую версию: `setLoading(true); setData(null);` при смене range → spinner
→ setData(resp).

### D4: Money format helper — единый хелпер для копеек

Новый файл `web/admin/src/lib/money.ts`:
```ts
export function formatKopecks(kopecks: number, locale: 'ru'|'en'): string {
  return new Intl.NumberFormat(locale === 'ru' ? 'ru-RU' : 'en-US', {
    style: 'currency',
    currency: 'RUB',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(kopecks / 100);
}
```
- Детерминированный вывод: `1234500 → "12 345,00 ₽"` (ru) / `"RUB 12,345.00"` (en). Точный
  формат зависит от ICU-данных Node/jsdom; тесты проверяют не-space-sensitive substring
  `'12'` + `'345'` + валютный знак.
- Alternatives rejected:
  - Rolling own formatter — reinventing wheel.
  - i18n `formatNumber` — добавляет зависимость от i18n-ключей, а у нас чисто численный helper.
- Кто ещё это будет использовать: orders, users, settings (все в phase 6). Общий модуль
  — удобно, не premature, т.к. 4 страницы уже в плане.

### D5: Popular items — отображаемое имя по locale

Backend отдаёт `popular_items: [{name_ru, name_en, quantity}, …]`. В UI выбор языка:
```ts
const name = i18n.language.startsWith('ru') ? item.name_ru : item.name_en;
```
Для поддержки fallback: если `name_en === ''` — fall back на `name_ru` (и наоборот).
(Бэкенд гарантирует оба поля, но оборонительно.)

### D6: Loading / empty / error

- Loading: текстовая "Загрузка..." (reuse `common.loading`), pattern Promos. Skeleton
  (pulse) — избыточно для MVP.
- Empty popular_items: `pages.dashboard.popular.empty` — "Нет данных за период" / "No data
  for this period".
- Error:
  - 401 — already handled by `authenticatedFetch` (редирект на `/login`).
  - 403 — `ApiError`. Показать toast через `NotificationList`+`useNotifier` (та же пара,
    что в PromosPage). Потенциально admin потерял права в runtime (понижен до barista) —
    редкий case; показываем ошибку без редиректа.
  - 5xx/network — generic toast "Не удалось загрузить статистику".

### D7: File structure + re-export

`pages/DashboardPage.tsx` сегодня импортируется в `App.tsx` как именованный экспорт
`{ DashboardPage }`. Создаём папку `pages/Dashboard/` с:
- `index.tsx` → `export { DashboardPage } from './DashboardPage';`
- `DashboardPage.tsx` → page-компонент.
- `RangeSelector.tsx` + `.test.tsx`.
- `StatsCards.tsx` + `.test.tsx`.
- `PopularItemsList.tsx` + `.test.tsx`.
- `DashboardPage.test.tsx` — интеграция.

`pages/DashboardPage.tsx` переписываем на `export { DashboardPage } from './Dashboard';`
— НЕ удаляем, т.к. phase6-plan указывает этот путь как валидную file-zone; плюс оставить
re-export безопаснее, чем менять импорт в App.tsx (минимизируем diff-зону).

### D8: Тесты — mock API через `vi.mock`

- `vi.mock('@/api/admin-stats', …)` в интеграционном тесте page'а.
- `vi.mock('@/api/client', …)` в тесте api-клиента (так как `authenticatedFetch` не
  мокнет fetch, тесту нужен либо fetch-mock, либо мокать `authenticatedFetch`). Проверить
  паттерн в `api/promocodes.test.ts`, если есть. Если нет — мокать `global.fetch` руками
  (как в других тестах admin-UI).

Каждый компонент (RangeSelector / StatsCards / PopularItemsList) — юнит-тестится изолированно
без API-мока (props-driven).

## Risks / Trade-offs

[R1] Barista может увидеть "flash" DashboardPage перед редиректом на /orders (D1):
  inline-гейт — синхронный; flash невозможен в React router semantics (Navigate resolves до
  render children). **Митигация:** unit-test `App.test.tsx` убеждается, что role=barista
  на `/` показывает контент /orders, а не dashboard.

[R2] `Intl.NumberFormat('ru-RU', {currency:'RUB'})` в jsdom может давать разный вывод
  (с пробелом неразрывным / обычным). **Митигация:** тесты проверяют substring 'RUB' /
  '12' / '345' / '00', не точный whitespace.

[R3] Backend (dashboard-api) не merge'нут в момент PR; CI прогонит frontend-тесты без
  интеграционного вызова. **Митигация:** все тесты — unit/mock; reviewer проверит, что
  shape AdminStatsResponse в `admin-stats.ts` совпадает со спекой dashboard-api.

[R4] Если `popular_items` содержит 10 row'ов с одинаковым именем (переименование — две
  snapshot-строки), UI покажет обе — это корректно по INV-014, но для читаемости можно
  добавить tooltip "исторический снапшот". **Митигация:** не вводим сейчас; если UX
  пожалуется — отдельный тикет.

[R5] В ru/en common.json ключи `pages.dashboard.title/description` уже заняты другими
  строками. Reuse их (UI не требует новые). Новые ключи — чисто подпапки. Конфликт
  невозможен (валидный JSON).

[R6] `getRole()` в inline-гейте: если `localStorage` пуст (первый рендер после logout), 
  inline возвращает `null`. `null !== 'admin'` → redirect на /orders. /orders тоже под
  тем же внешним wrapper'ом, без токена → редирект на /login. Итоговый редирект корректен,
  но проходит через промежуточный `/orders`. **Митигация:** приемлемо; можно при желании
  использовать `Navigate to='/login'` если `!token`, но внешний wrapper уже это делает.

## Atomicity Analysis

Нет финансовых операций — чистый read API (aggregation). INV-004 не применяется.

## State Machines

Не затрагиваются. Данные читаются из `orders` (COMPLETED, §6.1), но UI — read-only.

## 152-FZ Compliance

`AdminStatsResponse` не содержит PII (`revenue_kopecks`, `orders_count`, `popular_items[].name_*/
quantity`). INV-013 не затрагивается. Если backend в будущем начнёт возвращать user-данные —
spec придётся расширять.

## Migration Plan

Чисто frontend-изменение, без миграций БД. Rollback — revert коммита.

## Open Questions

Нет.
