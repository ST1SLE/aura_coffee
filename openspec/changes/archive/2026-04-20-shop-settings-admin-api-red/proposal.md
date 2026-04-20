## Why

Admin Panel (PDD §7.1 Phase 6 item 3, §5.2 Shop Settings) требует CRUD-интерфейс
к singleton-строке `shop_settings` для управления географией, тарифами, лояльностью,
рабочими часами и временем авто-закрытия. Сейчас настройки меняются только seed-скриптом
— админ не может отредактировать их через UI. Также phase 6.1 `auto-close` transition
(§6.1 "N минут с момента перехода в READY", INV-010) требует нового поля
`auto_close_minutes`, которого ещё нет в модели.

Это **RED-фаза TDD-цикла**: вводит failing-тесты, фиксирующие контракт миграции
0008, pydantic-валидации, сервисного слоя, RBAC и HTTP-маршрутов. Реализация —
в GREEN-цикле `shop-settings-admin-api-green`.

## What Changes

- Новые failing-тесты (без реализации — все падают):
  - `test_migration_0008_auto_close.py` — колонка `auto_close_minutes INT NOT NULL DEFAULT 60`,
    upgrade/downgrade, seed row инвариант.
  - `test_admin_shop_settings_get.py` — GET возвращает snapshot с новым полем.
  - `test_admin_shop_settings_put.py` — PUT обновляет всю строку; попытка создать
    второй row ломается CHECK ck_shop_settings_singleton.
  - `test_admin_shop_settings_validation.py` — табличные 422-кейсы:
    lat/lon/loyalty/free_delivery_threshold/auto_close_minutes/working_hours.
  - `test_admin_shop_settings_rbac.py` — barista/courier/customer → 403, без токена → 401.
- Не трогаем production-код (кроме, возможно, `conftest`/фабрик), чтобы тесты реально
  провалились по отсутствию эндпоинтов, новых схем и колонки.

## Capabilities

### New Capabilities
- `admin-shop-settings-api`: GET/PUT `/api/v1/admin/settings` — admin-only CRUD
  для singleton-строки `shop_settings`, миграция 0008 с `auto_close_minutes`,
  валидация working_hours/географии/лимитов.

### Modified Capabilities
<!-- none in RED — изменения существующих capabilities пойдут в GREEN-цикле -->

## Impact

- Test-only diff: `services/core-api/tests/test_migration_0008_auto_close.py`,
  `test_admin_shop_settings_{get,put,validation,rbac}.py`.
- Вспомогательные фабрики/фикстуры в `tests/_factories` или `_helpers` — при необходимости.
- Non-Goals:
  - Реализация эндпоинтов, схем, сервиса, миграции — это GREEN-цикл.
  - PATCH-эндпоинт (частичное обновление) — вне scope (избегаем JSONB merge на working_hours).
  - Audit-лог изменений (shop_settings_audit) — премэчурно, отдельный тикет.
  - Overnight working_hours (close < open) — вне scope, отдельный тикет.
  - Изменение customer-facing использования `ShopSettingsResponse`.
- MVP Phase: **6 (Admin Panel)**, item 3 (`/admin/settings`).
- Inviolable Rules: INV-010 (role isolation), частично INV-016 (auto-close transition).
- PDD refs: §5.2, §6.1, §7.1.
