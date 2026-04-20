## 1. GREEN — schema module

- [x] 1.1 [core-api] IMPL: Create `services/core-api/src/core_api/schemas/admin_stats.py`. Define Pydantic v2 models: `PopularItemOut { name_ru: str; name_en: str; quantity: int }` and `AdminStatsResponse { range: Literal["today","week","month"]; range_start: datetime; range_end: datetime; revenue_kopecks: int; orders_count: int; popular_items: list[PopularItemOut] }`. Use `model_config = ConfigDict(from_attributes=True)` on both so `list[PopularItem]` (dataclass) can be serialised via FastAPI.

## 2. GREEN — service helpers

- [x] 2.1 [core-api] IMPL: Create `services/core-api/src/core_api/services/admin_stats.py`. Declare module-level `TIMEZONE = "Europe/Moscow"`. Define `@dataclass(frozen=True) PopularItem(name_ru: str, name_en: str, quantity: int)`.
- [x] 2.2 [core-api] IMPL: Implement `compute_range(range_param: Literal["today","week","month"]) -> tuple[datetime, datetime]`. Capture `end = datetime.now(timezone.utc)` once. For `"today"`: `ZoneInfo(TIMEZONE)` → `datetime.combine(date.today(), time.min, tzinfo=tz).astimezone(timezone.utc)`. For `"week"` / `"month"`: `end - timedelta(days=7|30)`.
- [x] 2.3 [core-api] IMPL: Implement `get_revenue_and_count(db: Session, start: datetime, end: datetime) -> tuple[int, int]`. Use SQLAlchemy 2.0 `select(func.coalesce(func.sum(Order.total), 0), func.count()).where(Order.status == OrderStatus.COMPLETED, Order.created_at >= start, Order.created_at < end)`. Execute with `db.execute(stmt).one()` and cast to `(int(revenue), int(count))`.
- [x] 2.4 [core-api] IMPL: Implement `get_popular_items(db: Session, start: datetime, end: datetime, limit: int = 10) -> list[PopularItem]`. Build `select(OrderItem.menu_item_name_ru, OrderItem.menu_item_name_en, func.sum(OrderItem.quantity).label("quantity")).join(Order, OrderItem.order_id == Order.id).where(Order.status == OrderStatus.COMPLETED, Order.created_at >= start, Order.created_at < end).group_by(OrderItem.menu_item_name_ru, OrderItem.menu_item_name_en).order_by(desc("quantity")).limit(limit)`. Materialise as `[PopularItem(name_ru=r[0], name_en=r[1], quantity=int(r[2])) for r in db.execute(stmt).all()]`.

## 3. GREEN — router

- [x] 3.1 [core-api] IMPL: Create `services/core-api/src/core_api/routers/admin_stats.py`. Declare `router = APIRouter(prefix="/api/v1/admin", tags=["admin", "stats"])`. Handler: `@router.get("/stats", response_model=AdminStatsResponse)` taking `range: Literal["today","week","month"] = Query("month")` and `db: Session = Depends(get_db)`. Body: call `compute_range(range)` → `(start, end)`; call `get_revenue_and_count(db, start, end)` → `(revenue, count)`; call `get_popular_items(db, start, end)` → `items`; return `AdminStatsResponse(range=range, range_start=start, range_end=end, revenue_kopecks=revenue, orders_count=count, popular_items=[PopularItemOut(name_ru=..., name_en=..., quantity=...) for i in items])`.

## 4. GREEN — RBAC matrix + main.py wiring

- [x] 4.1 [core-api] IMPL: Edit `services/core-api/src/core_api/rbac_matrix.py`. Add `("GET", "/api/v1/admin/stats"): {ADMIN}` to `ROUTE_MATRIX`. Do NOT add the route to `PUBLIC_ROUTES`.
- [x] 4.2 [core-api] IMPL: Edit `services/core-api/src/core_api/main.py` to import `admin_stats_router` from `core_api.routers.admin_stats` and call `app.include_router(admin_stats_router)` alongside the other admin routers.

## 5. VERIFY — RED suite now flips green

- [x] 5.1 [core-api] VERIFY: Run `docker compose exec core-api pytest services/core-api/tests/test_admin_stats_range.py services/core-api/tests/test_admin_stats_revenue.py services/core-api/tests/test_admin_stats_popular.py services/core-api/tests/test_admin_stats_rbac.py -v` and confirm all 27 tests pass (22 that were failing in RED + the 5 that already passed trivially in RED).
- [x] 5.2 [core-api] VERIFY: Run the wider core-api suite to confirm no collateral regressions: `docker compose exec core-api pytest services/core-api/tests/ -q`. Any pre-existing failures from before this change (baseline on `feat/dashboard-api` / `admin_ui_phase`) remain; no admin-stats-related failures are introduced.
