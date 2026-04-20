## Why

RED-цикл `shop-settings-admin-api-red` уже зафиксировал failing-контракт для
admin-управления `shop_settings` + миграцию 0008 с полем `auto_close_minutes`.
GREEN-цикл реализует production-код, переводящий все эти тесты в зелёное:
модель, схемы, сервис, роутер, миграцию, seed, RBAC-матрицу.

Без этого изменения админ не может править географию/тарифы/часы/лояльность,
и §6.1 auto-close transition не имеет конфигурируемого параметра (PDD §5.2,
§6.1, §7.1 Phase 6 item 3, INV-010).

## What Changes

- **Миграция** `database/migrations/versions/0008_shop_settings_auto_close.py`:
  `ALTER TABLE shop_settings ADD COLUMN auto_close_minutes INTEGER NOT NULL
  DEFAULT 60`; downgrade — DROP COLUMN.
- **Модель** `packages/shared/src/shared/models/shop_settings.py`: новое поле
  `auto_close_minutes: Mapped[int]` с default=60.
- **Seed** `database/seeds/shop_settings.py`: включить `auto_close_minutes=60`
  в INSERT + UPSERT-ветку, чтобы повторный запуск не терял поле.
- **Схемы** `services/core-api/src/core_api/schemas/shop_settings.py`:
  + добавить `auto_close_minutes` в `ShopSettingsResponse`;
  + новая `ShopSettingsUpdate` — full-snapshot body с pydantic-валидаторами
    (lat/lon/loyalty/radius, `free_delivery_threshold ≥ min_delivery_amount`,
    `auto_close_minutes ∈ [1, 1440]`, строгая 7-дневная карта `working_hours`
    с HH:MM и `open < close`).
- **Сервис** `services/core-api/src/core_api/services/admin_shop_settings.py`:
  `get_settings(db)` (singleton-чтение id=1; если нет row → 500), и
  `update_settings(db, payload)` (UPDATE той же row, без INSERT).
- **Роутер** `services/core-api/src/core_api/routers/admin_shop_settings.py`:
  `GET /api/v1/admin/settings` и `PUT /api/v1/admin/settings`, подключённый
  в `main.py`.
- **RBAC** `services/core-api/src/core_api/rbac_matrix.py`: обе пары → `{ADMIN}`.
- **Тесты** становятся зелёными без правок (RED их зафиксировал контрактом).

## Capabilities

### New Capabilities
<!-- все новые Requirements уже вписаны в openspec/specs/admin-shop-settings-api
     при архивации RED-цикла. GREEN не добавляет новых capability-файлов — он
     реализует код к уже зафиксированному контракту. -->

### Modified Capabilities
<!-- нет: GREEN не меняет спецификацию, только реализует её. -->

## Impact

- Files: 1 миграция, 1 seed-скрипт (edit), 1 shared-модель (edit), 3 core-api
  файла (schemas edit, services new, routers new), 1 main.py (edit),
  1 rbac_matrix.py (edit).
- Не трогает: customer-facing endpoints (ShopSettingsResponse применяется
  только в admin-слое — grep подтвердил отсутствие ссылок в
  routers/*), валидаторы рабочих часов/радиуса, checkout-pipeline.
- Non-Goals:
  - PATCH-эндпоинт (частичное обновление) — вне scope.
  - Audit-таблица `shop_settings_audit` — отдельный тикет.
  - Overnight working_hours (close < open) — отдельный тикет.
  - Admin-UI — отдельный тикет в phase 6.
  - Переименование существующих колонок/полей.
- MVP Phase: **6 (Admin Panel)**, item 3 (`/admin/settings`).
- Inviolable Rules: INV-010 (role isolation), INV-016 (exhaustive state machine —
  `auto_close_minutes` параметризует §6.1 auto-close transition).
- PDD refs: §5.2, §6.1, §7.1.
