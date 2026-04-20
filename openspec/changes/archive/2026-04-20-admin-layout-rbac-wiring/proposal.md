## Why

Phase-3.5 коммит `cf656ce` заявил admin-role-wiring завершённым, но фактически `Layout.tsx` рендерит все 6 sidebar-пунктов безусловно, а `Menu/index.tsx` использует hardcoded-stub `useCurrentRole()` с TODO-комментарием. Route-gating (`ProtectedRoute.tsx`) работает корректно, но UX-слой показывает barista'м admin-only разделы (Users, Promos, Settings, Dashboard), что вводит в заблуждение и нарушает дух INV-010.

MVP Phase: 6 (Admin Panel) — завершение phase-3.5 перед запуском.

## What Changes

- Добавить `useCurrentRole(): StaffRole | null` hook в `web/admin/src/lib/auth.ts` (useMemo-обёртка над существующим `getRole()`, без реактивной подписки на storage).
- Удалить local-stub `useCurrentRole()` в `web/admin/src/pages/Menu/index.tsx` (строки 10-13 с TODO), импортировать hook из `@/lib/auth`.
- Ввести role-aware sidebar в `Layout.tsx` через `NAV_BY_ROLE: Record<StaffRole, readonly string[]>`:
  - `admin`: dashboard, orders, menu, users, promos, settings (6 пунктов)
  - `barista`: orders, menu (2 пункта, menu для стоп-листа)
  - `courier`: `[]` (defensive default — у courier свой `CourierShell`)
- Добавить `data-testid={`nav-${item.key}`}` на `<Link>` для тестируемости.
- Тесты: расширить `auth.test.ts` (useCurrentRole null / persisted), новый `Layout.test.tsx` (render-матрица по ролям).

## Capabilities

### New Capabilities
_нет_

### Modified Capabilities
- `admin-auth-ui`: sidebar в admin Layout фильтруется по роли staff'а; добавлен публичный hook `useCurrentRole()` в auth-модуле admin SPA.

## Impact

- **Код (web/admin)**: `lib/auth.ts`, `lib/auth.test.ts`, `pages/Menu/index.tsx`, `components/Layout.tsx`, `components/Layout.test.tsx`.
- **Не затрагивается**: `ProtectedRoute.tsx`, `App.tsx` (allowedRoles уже корректны), backend rbac_matrix (INV-010 server-side защита остаётся источником истины).
- **i18n**: существующие ключи `nav.*` покрывают все пункты, новых ключей не вводится.
- **Breaking**: нет. UX-улучшение без изменения API.

## Non-Goals

- Реактивная подписка на `storage` event (hot-swap роли без перезагрузки). Роль устанавливается один раз при логине, logout выполняет полный `navigate('/login')`. Если hot-swap понадобится — отдельный тикет.
- Изменения в `CourierShell` / courier-панели (Layout.tsx для courier не рендерится).
- Серверная RBAC-валидация — уже реализована через `rbac_matrix` (INV-010), sidebar-фильтр это чисто UX-слой.
- Новые i18n-ключи или изменения label'ов навигации.
