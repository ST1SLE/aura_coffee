## Context

Affected modules: **[core-api]**, **[database]**, **[shared]**.

RED-цикл зафиксировал контракт. GREEN пишет production-код. Основные артефакты
RED лежат в `openspec/changes/archive/2026-04-20-shop-settings-admin-api-red/` и
`openspec/specs/admin-shop-settings-api/spec.md`. RED-тесты — в
`services/core-api/tests/test_migration_0008_auto_close.py`,
`test_admin_shop_settings_{get,put,validation,rbac}.py`.

Текущее состояние:
- `shop_settings` singleton (CHECK id=1) из миграции 0005 содержит все PDD §5.2
  поля кроме `auto_close_minutes`.
- `ShopSettingsResponse` — только в `schemas/shop_settings.py`, без customer-
  facing потребителя (grep подтвердил).
- `database/seeds/shop_settings.py` — идемпотентный UPSERT.
- RBAC middleware читает `ROUTE_MATRIX` из `rbac_matrix.py`.

## Goals / Non-Goals

**Goals:**
- Перевести RED-тесты в зелёное минимальным diff.
- Additive-миграция 0008 (никаких rename).
- Строгая pydantic-валидация на уровне схемы — 422 при нарушении контракта.
- Сервисный слой изолирован от HTTP — роутер транспортная обёртка.
- Seed остаётся идемпотентным (UPSERT со всеми колонками).

**Non-Goals:**
- PATCH-эндпоинт.
- Audit-таблица.
- Overnight working_hours.
- Admin-UI.
- Hot-reload настроек в бизнес-сервисах — потребители (checkout, pricing,
  delivery) читают row напрямую при каждом запросе, кэширование не добавляем.

## Decisions

### D1: Миграция 0008 — additive only
**Decision:** `op.add_column("shop_settings", sa.Column("auto_close_minutes",
sa.Integer(), nullable=False, server_default="60"))`. Downgrade —
`op.drop_column`.

**Rationale:** `NOT NULL DEFAULT 60` покрывает существующую row без backfill;
откат безопасен. Миграция остаётся schema-only (INV-002, AGENTS constraint:
`alembic upgrade head` работает на чистом worktree без секретов).

**Alternative rejected:** создавать новую колонку как nullable и добавлять
backfill — избыточно для 1 row с гарантированным defaults.

### D2: Pydantic-схема `ShopSettingsUpdate`
**Decision:** отдельный класс с:
- `shop_lat: Decimal = Field(..., ge=-90, le=90)`
- `shop_lon: Decimal = Field(..., ge=-180, le=180)`
- `delivery_radius_km: Decimal = Field(..., ge=Decimal("0.1"), le=Decimal("50"))`
- `min_delivery_amount / free_delivery_threshold / delivery_fee: int >= 0`
- `loyalty_percent: int = Field(..., ge=0, le=100)`
- `default_prep_time_minutes / estimated_delivery_time_minutes: int >= 1`
- `auto_close_minutes: int = Field(..., ge=1, le=1440)`
- `working_hours: WorkingHoursMap`

`WorkingHoursMap` = `dict[Literal['mon'..'sun'], WorkingHoursSlot | None]` с
`model_validator(mode='after')`, проверяющим ровно 7 ключей.
`WorkingHoursSlot` — pydantic-модель с `open: str, close: str` и
`field_validator` на HH:MM regex + `model_validator` на `open < close` (строго).

Cross-field валидация `free_delivery_threshold ≥ min_delivery_amount` —
`model_validator(mode='after')` на `ShopSettingsUpdate`.

`ShopSettingsResponse` — добавить `auto_close_minutes: int`, остальное не
трогать.

**Rationale:** pydantic v2 валидирует до попадания в сервис; 422 возвращается
FastAPI автоматически. `Decimal` для lat/lon/radius соответствует существующим
аннотациям `Mapped[float]` + `Numeric`.

**Alternative rejected:** валидация в сервисе через explicit raises. Отклонено:
валидация payload — это граница pydantic v2 (FastAPI best practice), и 422 →
PyVal пути бесплатен.

### D3: Сервисный слой
**Decision:** модуль `services/admin_shop_settings.py` экспортирует:
- `get_settings(db: Session) -> ShopSettings` — `db.get(ShopSettings, 1)`; если
  None → `raise ShopSettingsNotSeededError()` (роутер маппит на 500).
- `update_settings(db: Session, payload: ShopSettingsUpdate) -> ShopSettings` —
  достаёт row, присваивает поля, `db.flush()`; `db.commit()` делает роутер.

**Rationale:** тонкий сервис, чистая инверсия зависимостей; комитить должен тот
слой, который владеет транзакцией (роутер через Depends(get_db)).

### D4: Роутер
**Decision:** `routers/admin_shop_settings.py`:
```
router = APIRouter(prefix="/api/v1/admin", tags=["admin-settings"])

@router.get("/settings", response_model=ShopSettingsResponse)
def get_settings_endpoint(db: Session = Depends(get_db)): ...

@router.put("/settings", response_model=ShopSettingsResponse)
def update_settings_endpoint(
    payload: ShopSettingsUpdate, db: Session = Depends(get_db)
): ...
```
Включается в `main.py` рядом с `admin_promocodes_router`.

### D5: Seed — additive UPSERT
**Decision:** обновить `database/seeds/shop_settings.py`:
- `DEFAULTS["auto_close_minutes"] = 60`
- INSERT-секция: добавить `auto_close_minutes` в колонки и `:auto_close_minutes`
  в VALUES.
- ON CONFLICT DO UPDATE: добавить `auto_close_minutes = EXCLUDED.auto_close_minutes`.

**Rationale:** иначе повторный запуск seed (после ручной правки админом)
сотрёт пользовательское значение — тот же UPSERT-паттерн, что для остальных
полей.

### D6: RBAC matrix
**Decision:** добавить две строки в `ROUTE_MATRIX`:
```
("GET", "/api/v1/admin/settings"): {ADMIN},
("PUT", "/api/v1/admin/settings"): {ADMIN},
```
RBACMiddleware + `test_route_coverage.py` автоматически покрывают новые
маршруты.

### D7: SQLAlchemy-модель
**Decision:** добавить в `shared.models.shop_settings.ShopSettings`:
```
auto_close_minutes: Mapped[int] = mapped_column(
    sa.Integer(), nullable=False, default=60, server_default=sa.text("60")
)
```
`default=60` — для ORM-инстансов без явного значения; `server_default` — для
DB-вставок в обход ORM.

## Risks / Trade-offs

- **[Risk] pydantic v2 `model_validator` порядок** → Mitigation: явно указываем
  `mode='after'` для cross-field проверок, чтобы field-валидаторы успели
  отработать.
- **[Risk] Decimal vs float при сериализации** → Mitigation: `ConfigDict(
  from_attributes=True)` + явно `Decimal | float` в `ShopSettingsResponse`
  (как сейчас).
- **[Risk] Сервис требует уже существующую row — иначе 500** → Mitigation:
  миграция 0005 + seed гарантируют присутствие id=1; в проде DB-init всегда
  проходит через seed. Комментарий в коде + тест на "не создавать вторую row".
- **[Risk] Working_hours overnight close < open — пользователь захочет 20→02** →
  Mitigation: явно вне scope (Non-Goal); при попытке — 422. Отдельный тикет.
- **[Risk] Rate-limit на PUT не настроен** → Mitigation: вне scope; админ-роут
  и так за авторизацией, стоимость атаки низкая.

## Migration Plan

Forward-only:
1. Deploy green-branch → `alembic upgrade head` автоматически прокатит 0008.
2. Seed-скрипт при следующем запуске догонит UPSERT по `auto_close_minutes=60`.
3. Откат: `alembic downgrade 0007` убирает колонку; модель/схема/роутер
   компилируются, но `get_settings` упадёт на отсутствующем атрибуте — поэтому
   откат выполняется только при полном развороте релиза.

## 152-FZ Compliance

Не применимо: shop_settings не содержат PII, INV-013 не затрагивается.

## Open Questions

Нет. Все поля и границы зафиксированы task-заданием и RED-спекой.
