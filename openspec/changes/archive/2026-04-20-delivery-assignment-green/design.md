## Context

**Affected modules:** `[core-api]`, `[shared]`, `[database]`.

RED-цикл `delivery-assignment-red` уже зафиксировал контракт через 60 падающих тестов в `services/core-api/tests/test_delivery_assignment_*` и `test_courier_endpoints.py`. Ожидаемые символы и пути:

- `shared.enums.DeliveryAssignmentStatus` (5 значений).
- `shared.models.DeliveryAssignment` (UUID pk, FK→orders UNIQUE, FK→staff_accounts nullable, статус, временные метки).
- Миграция `database/alembic/versions/0007_delivery_assignments.py`.
- `core_api.services.delivery_assignment.{take_assignment, pickup_assignment, deliver_assignment, cancel_assignment_for_order, list_available_for_courier, AssignmentTransitionError, AssignmentAlreadyTakenError}`.
- `core_api.services.order_lifecycle.transition_order_bridge`.
- `core_api.routers.courier.router` + регистрация в `core_api.main.app`.
- 5 записей в `core_api.rbac_matrix.ROUTE_MATRIX` со значением `{COURIER}`.
- `cancel_assignment_for_order` встраивается в `core_api.services.order_cancel.cancel_order` ДО `send_order_notification`.

Текущий `transition_order` (PDD §6.1, INV-016) делает: get→validate→update→`db.flush()`→`_accrue_loyalty`(если COMPLETED)→`send_order_notification`→`db.commit()`. Bridge-вариант (для вызовов изнутри `delivery_assignment`) должен делать всё то же САМОЕ, кроме `commit` и `send_order_notification` — иначе атомарность с update'ом assignment'а ломается, а ивент будет либо двойной, либо потеряется.

## Goals / Non-Goals

**Goals:**
- Все 60 RED-тестов из `delivery-assignment-red` перевести в зелёное БЕЗ изменений в самих тестах.
- Все существующие тесты `test_order_lifecycle.py`, `test_order_cancel.py`, etc. — ОСТАЮТСЯ зелёными.
- Реализовать §6.3 целиком: 5 статусов, 5 разрешённых переходов, optimistic lock на `take`, ownership на `pickup`/`deliver`.
- Сохранить INV-004 (атомарность bridge: assignment + order + loyalty в одной DB-транзакции).
- Сохранить INV-010 (роль COURIER изолирована от admin/barista/customer на курьерских эндпоинтах).
- Сохранить INV-016 (нет неявных переходов: всё внутри явных allow-list'ов).

**Non-Goals:**
- Никакого frontend-кода (UI — отдельная фича).
- Никакого ETA / геокодирования / автоназначения (отдельная фича).
- Никаких уведомлений курьеру при появлении нового AWAITING_COURIER (отдельная фича).
- Никаких новых переходов в Order Lifecycle §6.1 — только side-effect хук на PAID→PREPARING.

## Decisions

### D1. Расщепление `transition_order` на core + два публичных оборачивающих вызова

`_apply_transition(order_id, new_status, actor_role, db) -> Order` — приватный core: get→validate (allow-list, role, type-guards)→`order.status=new_status`→`db.flush()`→если COMPLETED — `_accrue_loyalty`→если PAID→PREPARING для DELIVERY — INSERT `DeliveryAssignment(AWAITING_COURIER)`→`db.flush()`. БЕЗ `commit` и БЕЗ `send_order_notification`.

`transition_order(order_id, new_status, actor_role, db)` — публичная: `_apply_transition(...)`→`send_order_notification(order, new_status)`→`db.commit()`. Сохраняет 100% поведение и тесты `test_order_lifecycle.py`.

`transition_order_bridge(order_id, new_status, actor_role, db)` — публичная для вызовов из `delivery_assignment`: `_apply_transition(...)` и ВСЁ. БЕЗ commit, БЕЗ notify. Вызывающий (pickup_assignment / deliver_assignment) сам делает commit и сам решает, нужно ли уведомление (по PDD §6.3 — НЕ нужно: уведомление о доставке клиенту посылается из delivery_assignment-сервиса по событию assignment'а, а не двух event'ов на один и тот же физический акт «курьер взял заказ»).

**Rationale:** альтернатива «параметр `commit=False`» делает API запутаннее и заставляет прятать вызовы notify за `if`. Две публичные функции с самоговорящими именами лучше отражают намерение (§6.1 vs §6.3 ↔ §6.1).

### D2. Хук PAID→PREPARING внутри `_apply_transition`, а не в `transition_order`

INSERT `DeliveryAssignment(AWAITING_COURIER)` для DELIVERY-заказа происходит ВНУТРИ `_apply_transition`. Это покрывает оба обертки (`transition_order` для барист, `transition_order_bridge` если в будущем кто-то поведёт PAID→PREPARING изнутри другого сервиса). Один источник истины.

**Rationale:** альтернатива — хук в обёртке `transition_order` — оставила бы `transition_order_bridge` без хука, что нарушает «одно правило — одно место».

### D3. `take_assignment` — optimistic lock через `UPDATE ... WHERE status=AWAITING_COURIER RETURNING *`

```python
stmt = (
    update(DeliveryAssignment)
    .where(
        DeliveryAssignment.id == aid,
        DeliveryAssignment.status == DeliveryAssignmentStatus.AWAITING_COURIER,
    )
    .values(
        status=DeliveryAssignmentStatus.COURIER_ASSIGNED,
        courier_id=cid,
        assigned_at=datetime.now(UTC),
    )
    .returning(DeliveryAssignment)
)
result = db.execute(stmt).scalar_one_or_none()
if result is None:
    # либо нет такого id, либо уже взято
    a = db.get(DeliveryAssignment, aid)
    if a is None:
        raise AssignmentTransitionError(reason="assignment_not_found")
    raise AssignmentAlreadyTakenError()
db.commit()
return result
```

**Rationale:** WHERE-предикат на `status=AWAITING_COURIER` — это сам lock. Конкурирующая транзакция, которая уже сменила статус, не найдёт строку под условием → 0 затронутых строк → проигрыш гонки. Альтернатива `SELECT ... FOR UPDATE` блокирует, а не отвергает — это нарушит PDD §6.3 «optimistic lock». RED-тест 4.2 явно проверяет «победитель один».

### D4. `pickup_assignment` / `deliver_assignment` — порядок проверок и атомарность

```python
def pickup_assignment(aid, cid, db):
    a = db.get(DeliveryAssignment, aid)
    if a is None: raise AssignmentTransitionError(reason="assignment_not_found")
    if a.status != COURIER_ASSIGNED: raise AssignmentTransitionError(reason="forbidden_transition")
    if a.courier_id != cid: raise AssignmentTransitionError(reason="not_owner")
    order = db.get(Order, a.order_id)
    if order.status != READY: raise AssignmentTransitionError(reason="order_not_ready")
    a.status = PICKED_UP
    a.picked_up_at = datetime.now(UTC)
    db.flush()
    transition_order_bridge(a.order_id, IN_DELIVERY, "courier", db)
    db.commit()
```

Аналогично `deliver_assignment`: проверки → `a.status = DELIVERED` → flush → bridge(IN_DELIVERY → COMPLETED, "courier", db) → commit. `_accrue_loyalty` сработает внутри `_apply_transition`.

**Atomicity Analysis (INV-004):** в pickup/deliver мутируем 2 строки (assignment + order), в deliver — ещё loyalty_account.balance + новая loyalty_transaction. ВСЕ мутации в одной SQLAlchemy-сессии и одном PostgreSQL transaction'е. Любое исключение между ними → исключение пробрасывается, вызывающий (FastAPI dependency / RED-тест) делает `db.rollback()` — обе строки возвращаются. Тесты 2.6 и 2.7 это явно проверяют.

### D5. `cancel_assignment_for_order` — порядок проверок и no-op

```python
def cancel_assignment_for_order(order_id, db):
    a = db.query(DeliveryAssignment).filter_by(order_id=order_id).one_or_none()
    if a is None: return None  # PICKUP-заказ, или ещё нет assignment'а
    if a.status in (PICKED_UP, DELIVERED): return None  # PDD §6.3: курьер уже забрал — отмена не сбрасывает
    if a.status == CANCELLED: return None  # idempotent
    # AWAITING_COURIER или COURIER_ASSIGNED → CANCELLED
    a.status = CANCELLED
    a.cancelled_at = datetime.now(UTC)
    db.flush()
    return a
```

Вызывается из `order_cancel.cancel_order` ВНУТРИ той же сессии, ДО `send_order_notification` (см. D9), без commit (общий commit делает `cancel_order` в самом конце цепочки).

### D6. Модель `DeliveryAssignment`

```python
class DeliveryAssignment(Base):
    __tablename__ = "delivery_assignments"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False, unique=True,  # 1:1 с заказом — INV-014 косвенно
    )
    courier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("staff_accounts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[DeliveryAssignmentStatus] = mapped_column(
        sa.Enum(DeliveryAssignmentStatus, name="delivery_assignment_status",
                native_enum=True, values_callable=lambda e: [i.value for i in e]),
        nullable=False, default=DeliveryAssignmentStatus.AWAITING_COURIER,
    )
    assigned_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    picked_up_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()"))
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()"), onupdate=sa.text("now()"))
```

UNIQUE на `order_id` — гарантия 1:1; partial index в миграции (см. D7).

### D7. Миграция `0007_delivery_assignments.py` (schema-only)

`upgrade()`:
1. `sa.Enum(... name="delivery_assignment_status").create(op.get_bind(), checkfirst=True)`.
2. `op.create_table("delivery_assignments", ...)`.
3. `op.create_index("ix_delivery_assignments_awaiting_courier", "delivery_assignments", ["status"], unique=False, postgresql_where=sa.text("status = 'awaiting_courier'"))`.

`downgrade()`: drop index → drop table → drop enum. Никаких data-операций (Alembic — только DDL).

### D8. Роутер `core_api.routers.courier`

```python
router = APIRouter(prefix="/api/v1/courier", tags=["courier"])

@router.get("/assignments/available")
def get_available(...): return list_available_for_courier(db)

@router.get("/assignments/mine")
def get_mine(current_user, db): ...  # фильтр по courier_id, статусы COURIER_ASSIGNED + PICKED_UP

@router.post("/assignments/{aid}/take")
def post_take(aid, current_user, db):
    try: return take_assignment(aid, current_user["user_id"], db)
    except AssignmentAlreadyTakenError: raise HTTPException(409, {"reason": "already_taken"})
    except AssignmentTransitionError as e: raise _to_http(e)

# pickup / deliver — аналогично
```

Mapping: `not_owner`→403, `forbidden_transition`/`order_not_ready`/`already_taken`→409, `assignment_not_found`→404. Регистрация в `core_api.main.app` через `app.include_router(courier_router)`.

### D9. RBAC: только COURIER на 5 курьерских эндпоинтах

5 записей в `ROUTE_MATRIX` со значением `{COURIER}` (без admin, без barista). Это явное «admin не может видеть assignments курьера через эти эндпоинты» — для admin'ов есть отдельная панель заказов через `/api/v1/orders/...` (другой роутер, другая RBAC). Тесты 3.4–3.8 это пинят.

### D10. Интеграция с `order_cancel`

В `cancel_order` ДО `send_order_notification` добавляется:

```python
from core_api.services.delivery_assignment import cancel_assignment_for_order
...
_return_promocode(order, db_session)
_reverse_points(order, db_session)
order.status = OrderStatus.CANCELLED
order.cancelled_by = cancelled_by
order.cancelled_at = datetime.now(UTC)
db_session.flush()
cancel_assignment_for_order(order_id, db_session)  # ← новый вызов
send_order_notification(order, OrderStatus.CANCELLED, reason=reason)
_enqueue_refund(order, db_session)
db_session.commit()
```

Порядок: rights → промокод → баллы → order.status → assignment-cancel → notify → refund-task → commit. Это ставит cancel-assignment в ту же транзакцию (атомарно с отменой order'а).

## Risks / Trade-offs

- **[Risk]** Существующие RED-тесты `test_order_lifecycle.py` ожидают, что `transition_order` всё ещё делает `db.commit()` и `send_order_notification`. **Mitigation:** обёртка `transition_order` сохранится 1-в-1 — расщепление полностью внутрикомпонентное.
- **[Risk]** Optimistic-lock-тест (4.2) запускается только на PG; sqlite-in-memory его пропускает. Если в CI нет PG → race-условие реально не проверится. **Mitigation:** скип помечен явно, в проектной матрице CI PostgreSQL обязателен (см. AGENTS.md).
- **[Trade-off]** Хук PAID→PREPARING встроен в `_apply_transition` — это связывает два модуля (`order_lifecycle` импортирует `DeliveryAssignment`). Альтернатива (event-bus / signal) сложнее и для одной точки события не оправдана. Принимаем связность.
- **[Risk]** `cancel_assignment_for_order` вызывается ДО `send_order_notification` в `cancel_order` — порядок изменился. **Mitigation:** тест 2.8 это явно проверяет; тест 2.12 оригинального §7.6 (refund-таск ставится ПОСЛЕ notify) — тоже сохраняется (refund-task всё ещё ПОСЛЕ notify).

## Migration Plan

Forward-only:
1. Применить миграцию `0007_delivery_assignments.py`: создаёт enum + таблицу + partial index.
2. Никакого backfill — старые завершённые DELIVERY-заказы в БД остаются без `delivery_assignment` строк, что эквивалентно legacy-поведению (assignment-таблица только начинает работать со следующего PAID→PREPARING).

Rollback: `alembic downgrade 0006` (если 0006 есть; иначе `0005`) — drop index → drop table → drop enum. Безопасно, так как UNIQUE FK на `orders.id` имеет `ondelete=RESTRICT`, но никаких записей в таблице ещё нет (на момент rollback после первого применения).

## 152-FZ Compliance (INV-013)

`DeliveryAssignment` НЕ хранит PII: только UUID order'а, UUID курьера, статусы, временные метки. Адрес доставки остаётся в `orders.delivery_address_snapshot` (JSONB), который уже под INV-013. Курьер видит адрес ТОЛЬКО когда читает order через `list_available_for_courier` JOIN — это допустимо по 152-ФЗ (legitimate purpose доставки).

## Open Questions

Никаких — RED-цикл уже зафиксировал контракт на 100%. Вопросы могут возникнуть только на этапе реализации (в этом случае — пауза + уточнение у пользователя).
