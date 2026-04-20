## Context

Affected modules: **[core-api]**, **[database]**, **[shared]**.

`shop_settings` — singleton (`CHECK id = 1`) с географией, тарифами, лояльностью и
рабочими часами (PDD §5.2). Сейчас row создаётся и обновляется только
`database/seeds/shop_settings.py` — админ через UI/API править настройки не может.
Phase 6.1 (§6.1 auto-close, INV-010) дополнительно требует поле
`auto_close_minutes` (по умолчанию 60), которого в модели ещё нет.

Эта change — **RED-фаза TDD**: вводит набор failing-тестов, фиксирующих контракт
будущего API и миграции 0008. GREEN-цикл реализует код, который эти тесты
превращает в passing.

## Goals / Non-Goals

**Goals:**
- Зафиксировать контракт миграции 0008 (upgrade/downgrade/seed-compat) тестом.
- Зафиксировать контракт `GET /api/v1/admin/settings` (snapshot-форма).
- Зафиксировать контракт `PUT /api/v1/admin/settings` (full snapshot, 200 на валид,
  422 на невалид, singleton-инвариант).
- Зафиксировать RBAC: только ADMIN (barista/courier/customer → 403, без токена → 401).
- Зафиксировать табличные негативные кейсы валидации (lat/lon/loyalty/threshold/
  auto_close/working_hours).

**Non-Goals:**
- Реализация эндпоинтов, сервисного слоя, схем, миграции — это GREEN-цикл.
- PATCH-эндпоинт (частичное обновление) — вне scope.
- Audit-таблица `shop_settings_audit` — отдельный тикет.
- Overnight working_hours (close < open) — отдельный тикет.
- Admin-UI для настроек — отдельный тикет.

## Decisions

### D1: RED-only diff — тесты пишем до production-кода
**Decision:** RED-цикл SHALL содержать только новые тестовые файлы +,
при необходимости, тестовые хелперы (`_factories`, `_helpers`). Production-код
(роутер, сервис, схема, модель, миграция, rbac_matrix) — не трогаем.

**Rationale:** цель RED — получить красный pytest-ран, который в GREEN станет
зелёным. Если изменить production-код до тестов, мы не увидим, что тест вообще
ловит регрессию.

**Alternative rejected:** сразу писать тесты + skeleton (pass-реализация). Отклонено:
smaller diff RED/GREEN, но теряется «красный» сигнал.

### D2: Формат failing-тестов
**Decision:** тесты SHALL импортировать модули, которых ещё нет
(`core_api.routers.admin_shop_settings`, `core_api.services.admin_shop_settings`,
`core_api.schemas.shop_settings.ShopSettingsUpdate`). ImportError / AttributeError
— приемлемый failure-mode для RED.

**Rationale:** консистентно с phase 5/5.5 RED-циклами (см. history phase 5
order-history RED).

### D3: Тестовая инфраструктура
**Decision:** использовать существующие фикстуры:
- `admin_client` / `barista_client` / `courier_client` / `customer_client` —
  httpx.AsyncClient с правильным ролевым токеном (если уже есть; иначе
  добавить в `conftest.py` как часть RED-scope, но без изменения production).
- `migrated_db_session` — для теста миграции 0008 upgrade→downgrade→upgrade.

**Rationale:** переиспользуем phase 5 test-harness.

### D4: Working_hours валидация — строгая 7-дневная карта
**Decision:** тест SHALL проверять, что pydantic-схема `ShopSettingsUpdate`
отклоняет:
- working_hours без ключа `sun` → 422.
- open=`25:00` → 422.
- open==close → 422.
- day = null (выходной) → 200.

**Rationale:** контракт из task §4 пункт working_hours. Overnight (close < open)
не тестируем — он не поддерживается.

### D5: Singleton-инвариант
**Decision:** тест `test_admin_shop_settings_put.py` SHALL попытаться вставить
row с id=2 через ORM (в обход endpoint) и зафиксировать `IntegrityError` от
`ck_shop_settings_singleton`. Это защита миграции 0008 — добавление колонки
не должно ронять CHECK-constraint.

**Rationale:** PDD §5.2 shop_settings — singleton. INV-010 role isolation не
предполагает per-admin настроек.

## Risks / Trade-offs

- **[Risk] Тесты зависят от ещё не существующих фабрик/ролевых хелперов** →
  Mitigation: если нужный хелпер отсутствует, добавляем минимальный, как часть
  RED (без production-кода).
- **[Risk] Миграция 0008 ещё не написана → migrated_db_session упадёт по
  `Can't locate revision '0008'`** → Mitigation: таков и есть дизайн failing-теста
  (красный pytest), GREEN цикл добавит 0008 и тест станет зелёным.
- **[Risk] Тест working_hours может случайно пройти из-за loose-валидации
  существующей схемы** → Mitigation: тест импортирует `ShopSettingsUpdate`,
  которой нет — ImportError гарантирует RED.

## Migration Plan

Миграций в RED нет. GREEN-цикл введёт `0008_shop_settings_auto_close.py`:
- Forward: `ALTER TABLE shop_settings ADD COLUMN auto_close_minutes INTEGER
  NOT NULL DEFAULT 60`.
- Rollback: `DROP COLUMN auto_close_minutes`.
- Seed: `database/seeds/shop_settings.py` SHALL быть обновлён включить
  `auto_close_minutes=60` в INSERT/UPSERT (иначе ON CONFLICT DO UPDATE сотрёт
  пользовательское значение).

Forward-only. Data backfill не требуется — NOT NULL DEFAULT 60 покрывает
существующую row.

## 152-FZ Compliance

Не применимо — shop_settings не содержат PII. INV-013 не затрагивается.

## Open Questions

- Нужно ли фиксировать в тесте RED статус-код на попытку создать вторую row
  (например, 500 vs отсутствие POST-эндпоинта)? — **Resolved в GREEN:** endpoint
  POST вообще не существует, ORM-попытка вставить id=2 → `IntegrityError` из
  db-уровня. RED тест должен падать по этой схеме.
