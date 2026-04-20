## 1. Auth hook (logic: RED → GREEN)

- [x] 1.1 [web-admin] RED: в `web/admin/src/lib/auth.test.ts` добавить тест `useCurrentRole returns null when no role persisted` — использовать `renderHook` из `@testing-library/react`, `localStorage.clear()` в setup, ожидать `result.current === null`. Тест FAIL: hook не экспортируется.
- [x] 1.2 [web-admin] RED: в `web/admin/src/lib/auth.test.ts` добавить тест `useCurrentRole returns persisted role after setRole` — `setRole('barista')` → `renderHook(() => useCurrentRole())` → ожидать `'barista'`. Тест FAIL: hook не экспортируется.
- [x] 1.3 [web-admin] GREEN: в `web/admin/src/lib/auth.ts` добавить `import { useMemo } from 'react'` и экспорт `export function useCurrentRole(): StaffRole | null { return useMemo(() => getRole(), []); }`. Проходят 1.1 и 1.2.

## 2. Menu page wiring

- [x] 2.1 [web-admin] IMPL: в `web/admin/src/pages/Menu/index.tsx` удалить строки 10-13 (local stub `useCurrentRole` + TODO-комментарий), добавить `import { useCurrentRole } from '@/lib/auth'`, добавить после `useCurrentRole()`-вызова early return `if (currentRole === null) return null;` для сужения типа. CRUD-гейтинг `currentRole === 'admin'` не трогать.

## 3. Layout: role-aware sidebar

- [x] 3.1 [web-admin] IMPL: в `web/admin/src/components/Layout.tsx` импортировать `useCurrentRole` и `type StaffRole` из `@/lib/auth`, объявить `const NAV_BY_ROLE: Record<StaffRole, readonly string[]> = { admin: [...6 keys], barista: ['orders','menu'], courier: [] }`.
- [x] 3.2 [web-admin] IMPL: в render'е `Layout.tsx` вычислить `const role = useCurrentRole(); const allowedKeys = role ? NAV_BY_ROLE[role] : []; const visibleItems = navItems.filter(i => allowedKeys.includes(i.key));` и заменить `navItems.map(...)` на `visibleItems.map(...)`.
- [x] 3.3 [web-admin] IMPL: в рендере `<Link>` внутри `Layout.tsx` добавить `data-testid={`nav-${item.key}`}`.

## 4. Layout tests (render matrix)

- [x] 4.1 [web-admin] TEST: создать `web/admin/src/components/Layout.test.tsx` со скелетом: `describe('Layout role-filtered sidebar')`, `beforeEach(() => localStorage.clear())`, утилита `renderLayout(role: StaffRole | null)` с `MemoryRouter` wrapper.
- [x] 4.2 [web-admin] TEST: в `Layout.test.tsx` тест `admin sees all 6 nav items` — `setRole('admin')` → render → ожидать наличие `getByTestId('nav-dashboard')`, `nav-orders`, `nav-menu`, `nav-users`, `nav-promos`, `nav-settings`.
- [x] 4.3 [web-admin] TEST: в `Layout.test.tsx` тест `barista sees only orders and menu` — `setRole('barista')` → render → `getByTestId('nav-orders')`, `nav-menu` присутствуют; `queryByTestId('nav-dashboard' | 'nav-users' | 'nav-promos' | 'nav-settings')` равны `null`.
- [x] 4.4 [web-admin] TEST: в `Layout.test.tsx` тест `courier sees zero nav links` — `setRole('courier')` → render → `queryAllByTestId(/^nav-/)` имеет length 0.
- [x] 4.5 [web-admin] TEST: в `Layout.test.tsx` тест `null role renders zero nav links` — `clearRole()` (no setRole) → render → `queryAllByTestId(/^nav-/)` имеет length 0.

## 5. Verify

- [x] 5.1 [web-admin] VERIFY: из `web/admin/` запустить `npm run test -- auth.test.ts Layout.test.tsx` — все тесты зелёные.
- [x] 5.2 [web-admin] VERIFY: из `web/admin/` запустить `npm run typecheck` (или `tsc --noEmit`) — 0 ошибок; проверить, что `Record<StaffRole, readonly string[]>` exhaustive по 3 ролям.
- [x] 5.3 [web-admin] VERIFY: grep по `web/admin/src/` на паттерн `// TODO: wire via staff-auth` и `function useCurrentRole()` (в pages/) — 0 совпадений (stub удалён).
