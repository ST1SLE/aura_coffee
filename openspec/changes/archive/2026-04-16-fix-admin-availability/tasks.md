## 1. Fix enum type and comparisons

- [x] 1.1 IMPL: [web-admin] Change `Availability` type in `web/admin/src/api/menu.ts:10` from `'AVAILABLE' | 'STOP_LIST' | 'ARCHIVED'` to `'available' | 'stop_list' | 'archived'`
- [x] 1.2 IMPL: [web-admin] Fix `AvailabilityBadge` comparisons in `web/admin/src/pages/Menu/MenuItemsTable.tsx:30,33` — `'STOP_LIST'` → `'stop_list'`, `'ARCHIVED'` → `'archived'`
- [x] 1.3 IMPL: [web-admin] Fix Switch `checked`/`disabled` comparisons in `web/admin/src/pages/Menu/MenuItemsTable.tsx:140,141` — `'AVAILABLE'` → `'available'`, `'ARCHIVED'` → `'archived'`

## 2. Verify

- [x] 2.1 VERIFY: [web-admin] Run `npx tsc --noEmit` in `web/admin/` — no type errors
- [x] 2.2 VERIFY: [web-admin] Run `npx vitest run` in `web/admin/` — existing tests pass
- [x] 2.3 VERIFY: [web-admin] Grep for remaining UPPERCASE availability literals in `web/admin/src/` — confirm none remain
