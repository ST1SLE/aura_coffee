## 1. Migration 0008

- [x] 1.1 [database] MIGRATE: Create
  `database/migrations/versions/0008_shop_settings_auto_close.py` with
  `revision='0008'`, `down_revision='0007'`, `upgrade()` adding
  `sa.Column('auto_close_minutes', sa.Integer(), nullable=False,
  server_default='60')` via `op.add_column`, and `downgrade()` dropping
  the column via `op.drop_column`. → satisfies RED 2.1, 2.2.
- [x] 1.2 [core-api] VERIFY: Run `pytest
  services/core-api/tests/test_migration_0008_auto_close.py::
  test_upgrade_adds_auto_close_minutes_column` and
  `::test_downgrade_drops_auto_close_minutes_column` against PG to confirm
  the migration applies and reverses cleanly.

## 2. Shared model

- [x] 2.1 [shared] GREEN: Add `auto_close_minutes: Mapped[int] =
  mapped_column(sa.Integer(), nullable=False, default=60,
  server_default=sa.text('60'))` to
  `packages/shared/src/shared/models/shop_settings.py`. → satisfies RED 4.2
  (ORM constructor accepts new field).

## 3. Seed

- [x] 3.1 [database] GREEN: Update `database/seeds/shop_settings.py`:
  - Add `"auto_close_minutes": 60` to `DEFAULTS` dict.
  - Add `auto_close_minutes` to INSERT column list and `:auto_close_minutes`
    to VALUES list.
  - Add `auto_close_minutes = EXCLUDED.auto_close_minutes` to the
    `ON CONFLICT DO UPDATE SET` list.
  → satisfies RED 2.3.

## 4. Pydantic schemas

- [x] 4.1 [core-api] GREEN: Edit
  `services/core-api/src/core_api/schemas/shop_settings.py` to add
  `auto_close_minutes: int` to existing `ShopSettingsResponse` (no other
  changes).
- [x] 4.2 [core-api] GREEN: In the same file, add `ShopSettingsUpdate`
  (full-snapshot body). Fields: `shop_lat: Decimal = Field(ge=-90, le=90)`,
  `shop_lon: Decimal = Field(ge=-180, le=180)`, `delivery_radius_km: Decimal
  = Field(ge=Decimal('0.1'), le=Decimal('50'))`, `min_delivery_amount: int =
  Field(ge=0)`, `free_delivery_threshold: int = Field(ge=0)`,
  `delivery_fee: int = Field(ge=0)`, `loyalty_percent: int = Field(ge=0,
  le=100)`, `default_prep_time_minutes: int = Field(ge=1)`,
  `estimated_delivery_time_minutes: int = Field(ge=1)`,
  `auto_close_minutes: int = Field(ge=1, le=1440)`,
  `working_hours: dict[str, WorkingHoursSlot | None]`. → satisfies RED 5.1
  field-bounded cases.
- [x] 4.3 [core-api] GREEN: Add `WorkingHoursSlot` pydantic model in the
  same file with `open: str` and `close: str`. Use
  `field_validator('open', 'close')` to match `^\d{2}:\d{2}$` with HH∈00..23,
  MM∈00..59; `model_validator(mode='after')` to enforce strict `open < close`
  (lexicographic string compare on HH:MM is safe). → satisfies RED 5.1
  `wh-bad-time`, `wh-open-eq-close`.
- [x] 4.4 [core-api] GREEN: Add `model_validator(mode='after')` on
  `ShopSettingsUpdate` that (a) asserts the `working_hours` dict keys are
  exactly `{'mon','tue','wed','thu','fri','sat','sun'}` and (b) asserts
  `free_delivery_threshold >= min_delivery_amount`, raising
  `ValueError` otherwise. → satisfies RED 5.1 `wh-missing-sun` and
  `free-threshold-below-min`.
- [x] 4.5 [core-api] GREEN: Confirm `None` is accepted for a day
  (`working_hours.tue = null`) — the schema uses `WorkingHoursSlot | None`.
  → satisfies RED 5.2.

## 5. Service layer

- [x] 5.1 [core-api] GREEN: Create
  `services/core-api/src/core_api/services/admin_shop_settings.py` defining
  `class ShopSettingsNotSeededError(RuntimeError)` and a `get_settings(db:
  Session) -> ShopSettings` function that loads id=1 and raises
  `ShopSettingsNotSeededError` if the row is missing. → satisfies RED 3.1
  (admin GET returns 200 with seeded row).
- [x] 5.2 [core-api] GREEN: Add `update_settings(db: Session, payload:
  ShopSettingsUpdate) -> ShopSettings` in the same module: fetch id=1,
  `setattr` each column from `payload.model_dump()`, convert `working_hours`
  via `model.working_hours = {k: (v.model_dump() if v else None) for k, v in
  payload.working_hours.items()}`, `db.flush()`, return the instance. → satisfies
  RED 4.1.

## 6. Router

- [x] 6.1 [core-api] GREEN: Create
  `services/core-api/src/core_api/routers/admin_shop_settings.py` with
  `router = APIRouter(prefix='/api/v1/admin', tags=['admin-settings'])` and
  two handlers: `@router.get('/settings',
  response_model=ShopSettingsResponse)` → calls `get_settings(db)`;
  `@router.put('/settings', response_model=ShopSettingsResponse)` → calls
  `update_settings(db, payload)` then `db.commit()`, `db.refresh(row)`.
  Map `ShopSettingsNotSeededError` to `HTTPException(500, 'shop_settings not
  seeded')`. → satisfies RED 3.1, 4.1.

## 7. Main + RBAC wiring

- [x] 7.1 [core-api] GREEN: Include the new router in
  `services/core-api/src/core_api/main.py`: add
  `from core_api.routers.admin_shop_settings import router as admin_settings_router`
  and `app.include_router(admin_settings_router)` near the other admin
  routers.
- [x] 7.2 [core-api] GREEN: Add two rows to
  `services/core-api/src/core_api/rbac_matrix.py` `ROUTE_MATRIX`:
  `("GET", "/api/v1/admin/settings"): {ADMIN}` and
  `("PUT", "/api/v1/admin/settings"): {ADMIN}`. → satisfies RED 6.x.

## 8. Verify GREEN

- [x] 8.1 [core-api] VERIFY: Run `pytest
  services/core-api/tests/test_admin_shop_settings_get.py
  services/core-api/tests/test_admin_shop_settings_put.py
  services/core-api/tests/test_admin_shop_settings_validation.py
  services/core-api/tests/test_admin_shop_settings_rbac.py` and confirm all
  tests pass.
- [x] 8.2 [core-api] VERIFY: Run `pytest
  services/core-api/tests/test_migration_0008_auto_close.py` against PG and
  confirm all three migration tests pass.
- [x] 8.3 [core-api] VERIFY: Run `pytest services/core-api/tests/
  test_rbac_matrix.py services/core-api/tests/test_route_coverage.py` to
  confirm no regression (every registered route covered by matrix/public).

## 9. Refactor pass

- [x] 9.1 [core-api] REFACTOR: Review `schemas/shop_settings.py`,
  `services/admin_shop_settings.py`, `routers/admin_shop_settings.py` for
  unused imports, overly verbose comments, duplicated literals (e.g.
  `('mon','tue',...)`). Extract the day-key tuple to a module-level constant
  in the schema. No behaviour change.
