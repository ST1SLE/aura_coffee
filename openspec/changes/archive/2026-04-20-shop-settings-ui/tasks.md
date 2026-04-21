## 1. API client (logic, TDD RED→GREEN)

- [x] 1.1 RED [web-admin] Create `web/admin/src/api/admin-settings.test.ts` asserting: `getSettings()` GETs `/api/v1/admin/settings`, `updateSettings(payload)` PUTs same path with JSON body, `ApiError` propagates on non-2xx (expect ImportError for now).
- [x] 1.2 RED [web-admin] Extend `admin-settings.test.ts` with case: `parseFieldErrorsDeep` maps `detail[{loc:['body','working_hours','mon','open'], msg:'invalid'}]` → `{'working_hours.mon.open': 'invalid'}`; top-level `['body','loyalty_percent']` → `{'loyalty_percent': 'msg'}`.
- [x] 1.3 RED [web-admin] Extend `admin-settings.test.ts` with money helpers: `toKopecks(100) === 10000`, `toKopecks(1.5) === 150`, `kopecksToRubles(10000) === '100'` (trailing `.00` stripped).
- [x] 1.4 GREEN [web-admin] Create `web/admin/src/api/admin-settings.ts` with types `ShopSettingsResponse` / `ShopSettingsUpdate` / `WorkingHoursDay` / `WorkingHours`, `getSettings()`, `updateSettings(payload)`, `parseFieldErrorsDeep`, `toKopecks`, `kopecksToRubles` — satisfies 1.1, 1.2, 1.3.

## 2. Routing — admin-only guard on `/settings`

- [x] 2.1 TEST [web-admin] Add test case to `web/admin/src/components/ProtectedRoute.test.tsx` (or a new `App.test.tsx` block) asserting barista on `/settings` redirects to `/`, admin renders `SettingsPage`.
- [x] 2.2 IMPL [web-admin] Modify `web/admin/src/App.tsx`: wrap `<SettingsPage />` at route `/settings` with inner `<ProtectedRoute allowedRoles={['admin']}>` (mirrors `/promos` pattern).

## 3. Page scaffold (container)

- [x] 3.1 IMPL [web-admin] Create `web/admin/src/pages/Settings/SettingsPage.tsx` — container: loads via `getSettings()`, holds `form`/`initialForm` state, computes `isDirty`/`isValid`, renders loading skeleton, renders 5 sections with `value`/`onChange`/`errors`, Save button, `NotificationList`/`useNotifier` for toasts, submit calls `updateSettings` with kopecks-converted payload, handles 422 via `parseFieldErrorsDeep`, generic toast for 500/network.
- [x] 3.2 IMPL [web-admin] Create `web/admin/src/pages/Settings/index.tsx` re-exporting `SettingsPage`.
- [x] 3.3 IMPL [web-admin] Replace `web/admin/src/pages/SettingsPage.tsx` with a one-line re-export `export { SettingsPage } from './Settings'` (keeps existing import path in `App.tsx` green).

## 4. Section components (IMPL + TEST each)

- [x] 4.1 IMPL [web-admin] Create `web/admin/src/pages/Settings/SectionCoords.tsx` — numeric inputs for `shop_lat` / `shop_lon` with labels from i18n, accepts `value`/`onChange`/`errors` props.
- [x] 4.2 TEST [web-admin] Create `web/admin/src/pages/Settings/SectionCoords.test.tsx` — renders both inputs, `onChange` fires on edit, inline error shown when `errors.shop_lat` set (smoke).
- [x] 4.3 IMPL [web-admin] Create `web/admin/src/pages/Settings/SectionDelivery.tsx` — 4 inputs (`delivery_radius_km` with km suffix; `min_delivery_amount`, `free_delivery_threshold`, `delivery_fee` with ₽ suffix; values in rubles).
- [x] 4.4 TEST [web-admin] Create `web/admin/src/pages/Settings/SectionDelivery.test.tsx` — `free_delivery_threshold < min_delivery_amount` triggers inline error; changing rubles input emits numeric `onChange`; assert `toKopecks(100) === 10000` round-trip via test utility import.
- [x] 4.5 IMPL [web-admin] Create `web/admin/src/pages/Settings/SectionLoyalty.tsx` — single number input `loyalty_percent` with `%` suffix, `min=0 max=100`.
- [x] 4.6 TEST [web-admin] Create `web/admin/src/pages/Settings/SectionLoyalty.test.tsx` — boundary 0 OK, 100 OK, 101 triggers error via validator.
- [x] 4.7 IMPL [web-admin] Create `web/admin/src/pages/Settings/SectionTiming.tsx` — three number inputs (`default_prep_time_minutes`, `estimated_delivery_time_minutes`, `auto_close_minutes`) with minutes suffix.
- [x] 4.8 TEST [web-admin] Create `web/admin/src/pages/Settings/SectionTiming.test.tsx` — `auto_close_minutes=0` error, `1441` error, `60` OK.
- [x] 4.9 IMPL [web-admin] Create `web/admin/src/pages/Settings/SectionWorkingHours.tsx` — 7 rows (mon..sun) each with Closed checkbox + two `<input type="time">`; when closed, hide time inputs and serialize `null`.
- [x] 4.10 TEST [web-admin] Create `web/admin/src/pages/Settings/SectionWorkingHours.test.tsx` — unchecking Closed reveals time pickers; `open=12:00 close=10:00` inline error; empty open + not-closed → error; toggling Closed serializes `null`.

## 5. Page-level tests

- [x] 5.1 TEST [web-admin] Create `web/admin/src/pages/Settings/SettingsPage.test.tsx` — mount with mocked `getSettings` → inputs pre-filled; Save disabled when `!isDirty`; edit → Save enabled.
- [x] 5.2 TEST [web-admin] Extend `SettingsPage.test.tsx` — mock `updateSettings` reject with `ApiError(422, { detail: [{loc:['body','working_hours','mon','open'], msg:'invalid'}] })` → Monday open inline error appears after save attempt.
- [x] 5.3 TEST [web-admin] Extend `SettingsPage.test.tsx` — happy save: `updateSettings` resolves with new snapshot → success toast shown; `isDirty` resets (Save disabled again).

## 6. i18n

- [x] 6.1 IMPL [web-admin] Extend `web/admin/src/i18n/locales/ru/common.json` — replace `pages.settings.{title,description}` with full subtree: `title`, `description`, `sections.{coords,delivery,loyalty,timing,working_hours}`, `fields.{shop_lat,shop_lon,delivery_radius_km,min_delivery_amount,free_delivery_threshold,delivery_fee,loyalty_percent,default_prep_time_minutes,estimated_delivery_time_minutes,auto_close_minutes}`, `units.{km,rub,percent,minutes}`, `days.{mon,tue,wed,thu,fri,sat,sun}`, `closed`, `save_button`, `toast.{saved,error}`, `errors.{out_of_range,below_min_delivery,open_after_close,empty_time,generic}`.
- [x] 6.2 IMPL [web-admin] Mirror the same keys in `web/admin/src/i18n/locales/en/common.json` with English translations.

## 7. Verify

- [x] 7.1 VERIFY [web-admin] Run `pnpm --filter aura-coffee-admin test` (or `npm test` inside `web/admin/`). All tests green.
- [x] 7.2 VERIFY [web-admin] Run `pnpm --filter aura-coffee-admin lint` (or `npm run lint`). Zero warnings on new files.
- [x] 7.3 VERIFY [web-admin] Run `pnpm --filter aura-coffee-admin build` (or `npm run build`). TypeScript + Vite build clean, no errors.
