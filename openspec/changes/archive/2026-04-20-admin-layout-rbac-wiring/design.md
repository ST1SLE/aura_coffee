## Context

Affected modules: [web-admin].

Phase-3.5 коммит `cf656ce` добавил `getRole/setRole/clearRole` в `web/admin/src/lib/auth.ts` и wire-up в `ProtectedRoute.tsx` + `App.tsx` (`allowedRoles`). Однако:

- `web/admin/src/components/Layout.tsx` рендерит все 6 пунктов sidebar'а безусловно (Layout.tsx:6-13, 26-39).
- `web/admin/src/pages/Menu/index.tsx:10-13` содержит local-stub `useCurrentRole(): 'admin' | 'barista'` с hardcoded `return 'admin'` и TODO-комментарием.
- Публичного hook'а `useCurrentRole()` в `@/lib/auth` не существует.

Route-gating (`ProtectedRoute`) работает корректно — courier не попадает на `/menu`, barista не попадает на `/users`. Но sidebar barista показывает admin-only пункты как кликабельные ссылки, которые при переходе редиректят на `/`. Это UX-баг, не security-дыра (INV-010 соблюдён server-side через `rbac_matrix`).

## Goals / Non-Goals

**Goals:**
- MUST ввести публичный `useCurrentRole(): StaffRole | null` в `@/lib/auth`.
- MUST удалить local-stub в `Menu/index.tsx` и использовать hook.
- MUST фильтровать `navItems` в `Layout.tsx` по роли через exhaustive `Record<StaffRole, readonly string[]>`.
- MUST покрыть тестами: hook (null/persisted) и Layout (4 render-матрицы).
- MUST добавить `data-testid={`nav-${item.key}`}` для стабильных селекторов в тестах.

**Non-Goals:**
- Реактивная подписка на `storage` event. Роль set'ится один раз при логине; logout делает `window.location.assign('/admin/login')` — полный reload, hook читает свежий `localStorage`. Если hot-swap role понадобится — отдельный тикет.
- Trigger re-render при смене роли внутри SPA сессии. `useMemo(() => getRole(), [])` читает один раз при mount — этого достаточно.
- Изменения `ProtectedRoute.tsx`, `App.tsx`, backend `rbac_matrix`.
- Новые i18n-ключи (все `nav.*` существуют).
- Серверная RBAC — INV-010 уже защищён, sidebar это чистый UX.

## Decisions

### D1. Hook: `useMemo(() => getRole(), [])`, а не `useState` + `useEffect`

**Выбор:** функциональный hook, считывающий `localStorage` один раз при mount через `useMemo`.

**Почему:** роль в admin-SPA не меняется в пределах сессии. Login → `setRole` → navigate → полный mount. Logout → `window.location.assign('/admin/login')` → полный reload. Хот-свапа нет.

**Альтернативы:**
- `useState + useEffect(subscribe to storage)`: лишняя сложность ради несуществующего сценария. Storage events не срабатывают в той же вкладке, где был `setItem`, — пришлось бы эмитить custom event вручную. Отложено в non-goals.
- Прямой вызов `getRole()` в render'е: каждый ре-рендер дёргает `localStorage.getItem`. `useMemo` дешевле и явнее коммуницирует "value is stable".

### D2. `NAV_BY_ROLE` — exhaustive `Record<StaffRole, readonly string[]>`

**Выбор:** constant-map от `StaffRole` к списку разрешённых `key`'ов навигации.

```ts
const NAV_BY_ROLE: Record<StaffRole, readonly string[]> = {
  admin:   ['dashboard', 'orders', 'menu', 'users', 'promos', 'settings'],
  barista: ['orders', 'menu'],
  courier: [],
};
```

**Почему:**
- `Record<StaffRole, ...>` форсит exhaustiveness — добавление новой роли в `StaffRole` union сломает компиляцию, пока map не дополнен.
- `courier: []` — defensive default. Courier использует `CourierShell` (route `/courier`), Layout.tsx для него не рендерится. Пустой массив гарантирует, что даже при edge-case попадании courier'а в Layout-tree он не увидит admin-only ссылки.
- Хранение keys, а не path'ов: `navItems` уже содержит `{path, key}`, фильтр через `allowedKeys.includes(item.key)` проще и стабильнее к рефакторингу URL'ов.

**Альтернативы:**
- Per-item `allowedRoles: StaffRole[]` внутри `navItems`: дублирует знание о ролях, сложнее проверить exhaustiveness.
- Inline `switch` по роли: менее декларативно, тяжелее тестировать.

### D3. Null-guard в `Menu/index.tsx` через early return

**Выбор:**
```ts
const currentRole = useCurrentRole();
if (currentRole === null) return null;
```

**Почему:** страница обёрнута в `ProtectedRoute` с `allowedRoles={['admin','barista']}` в `App.tsx`, поэтому null в production unreachable. Но `useCurrentRole()` возвращает `StaffRole | null`, и TypeScript не знает про route-инвариант. Early return — самый явный способ сузить тип.

**Альтернативы:**
- Non-null assertion `useCurrentRole()!`: короче, но теряет явность. Выбираем early return (per task scope).

### D4. `data-testid={`nav-${item.key}`}` на `<Link>`

**Выбор:** добавить атрибут `data-testid="nav-dashboard"` (и т.п.) в render-loop `Layout.tsx`.

**Почему:** тесты матрицы по ролям должны утверждать наличие/отсутствие каждой ссылки независимо от i18n (`t('nav.orders')` резолвится в RU или EN в зависимости от настройки i18next в тесте). `data-testid` — стабильный селектор, не коррелирует с label'ами.

**Альтернативы:** селекторы по тексту с форсированной EN-locale в тестах — хрупко, тесты падают при правке label'ов.

## Risks / Trade-offs

- **Risk:** Будущий разработчик добавит роль в `StaffRole` union и забудет дополнить `NAV_BY_ROLE`. → **Mitigation:** `Record<StaffRole, ...>` типизация не скомпилируется без новой записи. TS-compiler enforces.
- **Risk:** `useMemo(() => getRole(), [])` не реагирует на будущий hot-swap роли. → **Mitigation:** задокументировано в non-goals; hot-swap = отдельный тикет. Текущий flow logout→reload покрывает случай смены роли.
- **Trade-off:** `data-testid` добавляет атрибут в production DOM. Не оптимизируем: один строковый атрибут на `<Link>`, ≤6 элементов, overhead незаметен.
- **Risk:** `NAV_BY_ROLE.barista = ['orders', 'menu']` включает menu. Но barista не должен видеть CRUD-контролы внутри Menu. → **Mitigation:** CRUD-гейтинг уже реализован в `Menu/index.tsx` через `currentRole === 'admin'`, страница остаётся доступной только для стоп-листа (PDD §4.5). Не меняем.

## Migration Plan

Код-change only, DB/API без изменений. Деплой атомарен: Vite-build admin SPA.

**Rollout:**
1. Merge в `delivery` после phase-3.5 pipeline зелёный.
2. В production bundle попадает фильтрованный sidebar.
3. Залогиненные barista-пользователи при следующем ре-загрузке страницы увидят урезанный sidebar — без invalidation'а существующих токенов.

**Rollback:** git revert. Никаких DB-миграций не вводится.

## Open Questions

Нет. Scope жёстко зафиксирован в исходной задаче.
