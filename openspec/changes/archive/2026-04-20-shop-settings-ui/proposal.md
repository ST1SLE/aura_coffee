## Why

Админу кофейни нужен UI для редактирования настроек магазина (координаты, радиус доставки, пороги, рабочие часы, лояльность, тайминги, `auto_close_minutes`). Сейчас `SettingsPage` — stub; единственный способ поменять значения — SQL в `shop_settings`. Phase 6 вводит backend-эндпоинты `GET/PUT /api/v1/admin/settings`; UI — парный фронтенд-тикет, закрывающий Phase 6 item 3.

## What Changes

- Новый API-клиент `web/admin/src/api/admin-settings.ts`:
  - `getSettings()` → `ShopSettingsResponse`.
  - `updateSettings(payload)` → `ShopSettingsResponse`.
  - Конвертация kopecks ↔ rubles на UI-слое (пишем сетевому API в копейках).
  - Парсер 422 `detail[].loc → field-path` для field-level-ошибок.
- Директория `web/admin/src/pages/Settings/` заменяет `SettingsPage.tsx`:
  - `SettingsPage.tsx` — контейнер с loading-skeleton, submit-handler, toast-ом, `isDirty`-gating кнопки сохранения.
  - 5 секций: `SectionCoords`, `SectionDelivery`, `SectionLoyalty`, `SectionTiming`, `SectionWorkingHours`.
  - `SectionWorkingHours`: 7 строк (пн..вс), чекбокс «Выходной» (null) + пара `<input type="time">`, inline-валидация `open < close`.
  - Native React state + валидация (как `PromoFormDialog`), zod/react-hook-form не вводим — стек и так без них.
- `App.tsx`: маршрут `/settings` оборачивается в inner `<ProtectedRoute allowedRoles={['admin']}>` (поверх общей admin+barista-обёртки — двойная защита INV-010).
- Добавлены ключи i18n в `ru/common.json` и `en/common.json`: `pages.settings.{title,description,sections,fields,units,days,closed,save_button,toast,errors}`.
- Тесты (Vitest + React Testing Library): одна `.test.tsx` на секцию + `SettingsPage.test.tsx` + `api/admin-settings.test.ts`.

## Capabilities

### New Capabilities
- `shop-settings-ui`: admin-only SPA-страница для редактирования singleton `shop_settings` через `GET/PUT /api/v1/admin/settings`, с field-level-валидацией и маппингом 422-ошибок сервера.

### Modified Capabilities
- `frontend-routing`: маршрут `/settings` в `web/admin/App.tsx` получает inner `ProtectedRoute allowedRoles=['admin']` — ранее доступ контролировался только sidebar-фильтром.

## Non-Goals

- НЕ добавлять Yandex-Maps-пикер для `shop_lat/shop_lon` — числовые поля достаточны, перенос `customer-ui` компонента — premature.
- НЕ поддерживать overnight-режим рабочих часов (закрытие после полуночи); backend такой payload отклонит 422, UI-валидация `open < close` совпадает.
- НЕ делать PATCH/partial-save — форма всегда отправляет full snapshot (PUT), как backend.
- НЕ вводить кнопку «Reset to defaults».
- НЕ кэшировать ответ — после успешного save делаем refetch, чтобы `updated_at` был актуальным.
- НЕ заводить новый state-management (Zustand/Redux) — локальный `useState` хватает.
- НЕ вводить zod/react-hook-form — в `web/admin` этих зависимостей нет, следуем паттерну `PromoFormDialog` (native React).

## Impact

- **Код:**
  - New: `web/admin/src/api/admin-settings.ts`, `web/admin/src/api/admin-settings.test.ts`.
  - New: `web/admin/src/pages/Settings/{index,SettingsPage,SectionCoords,SectionDelivery,SectionLoyalty,SectionTiming,SectionWorkingHours}.tsx` + соответствующие `.test.tsx`.
  - Modified: `web/admin/src/pages/SettingsPage.tsx` (re-export / удаление stub-а в пользу новой директории).
  - Modified: `web/admin/src/App.tsx` — inner `ProtectedRoute` для `/settings`.
  - Modified: `web/admin/src/i18n/locales/{ru,en}/common.json` — расширение `pages.settings`.
- **API (консьюмер):** зависит от `GET/PUT /api/v1/admin/settings` из `shop-settings-admin-api` (phase 6, merge_order 3). Payload-контракт — `ShopSettingsResponse/ShopSettingsUpdate` из `services/core-api/src/core_api/schemas/shop_settings.py`.
- **RBAC / INV-010:** `/settings` становится admin-only (double-guard: inner `ProtectedRoute` + sidebar-фильтр). Сервер всё равно owner-of-truth.
- **Зависимости npm:** без изменений — `react-i18next`, `@radix-ui/*`, существующий `ui/notifier.tsx`.
- **PDD sections:** §5.2 ShopSettings, §6.1 (auto-close), §7.1 Phase 6 item 3, INV-010.
- **MVP Phase:** Phase 6 (Admin Panel).
