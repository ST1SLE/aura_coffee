## Context

Affected modules: **[core-api]**, **[redis]** (Celery broker),
**[docker-compose]** (new scheduler + worker containers).

Current state (после RED):
- 15 failing-тестов в
  `services/core-api/tests/test_pickup_autoclose_{service,task}.py` и
  `test_celery_beat_schedule.py` фиксируют контракт.
- `core_api.celery_app.celery_app = Celery("core_api", broker=
  settings.redis_url)` — минимальный клиент без `include`, без
  `beat_schedule`.
- `core_api.services.order_lifecycle.transition_order(order_id,
  new_status, actor_role, db_session)` требует
  `actor_role ∈ _ALLOWED_ROLES[(from, to)]` и безусловно вызывает
  `send_order_notification(order, new_status)` после `_apply_transition`.
  `_ALLOWED_ROLES[(READY, COMPLETED)] = {"barista", "admin"}`.
- Модели `Order` уже имеют `auto_completed`, `auto_completed_at`
  (0005). `ShopSettings.auto_close_minutes` с default 60 (0008).
- docker-compose имеет payment-worker, sms-worker, но нет core-api-worker
  и нет scheduler.

## Goals / Non-Goals

**Goals:**
- Реализовать `services/pickup_autoclose.py` так, чтобы все 11 тестов из
  `test_pickup_autoclose_service.py` прошли.
- Расширить `order_lifecycle` минимально: allow `"system"` для
  `(READY, COMPLETED)` и suppress SMS при `actor_role == "system"`.
  Ни один существующий тест `test_order_lifecycle.py` не должен упасть.
- Реализовать `core_api/tasks/pickup_autoclose.py` с таской
  `pickup.close_stale` — тонкая обёртка, чтобы 2 теста из
  `test_pickup_autoclose_task.py` прошли.
- Настроить `celery_app.py`: `include=[...]` + `beat_schedule`,
  чтобы 2 теста `test_celery_beat_schedule.py` прошли.
- Добавить `scheduler` и `core-api-worker` сервисы в docker-compose.yml,
  использующие тот же Dockerfile `target: dev`, что и core-api.

**Non-Goals:**
- Новые миграции.
- Admin-UI для `auto_close_minutes`.
- Prometheus healthcheck для scheduler/worker.
- Override частоты Beat (60s фиксировано).
- Postgres-specific concurrency test (FOR UPDATE SKIP LOCKED) —
  может быть добавлен позже, не блокирует GREEN.

## Decisions

### D1: Реиспользовать `order_lifecycle.transition_order`, а не дублировать

**Decision:** сервис `close_stale_pickups` SHALL вызывать
`order_lifecycle.transition_order(order_id, OrderStatus.COMPLETED,
actor_role="system", db)` для каждого stale заказа. После перехода —
выставляет `order.auto_completed=True`, `order.auto_completed_at=now`
прямо в ORM и делает второй `commit`.

**Rationale:** single-entry-point для переходов (INV-016). Loyalty
accrual — side-effect `_accrue_loyalty`, уже встроенный в
`_apply_transition`. Дубликация логики → риск рассинхронизации.

**Alternative rejected:** прямая мутация `order.status = COMPLETED` +
ручной вызов `_accrue_loyalty`. Отклонено — ломает INV-016 и
тестируемость (непонятно, что будет, если правила перехода изменятся).

### D2: Роль `"system"` — служебный actor

**Decision:** `_ALLOWED_ROLES[(OrderStatus.READY, OrderStatus.COMPLETED)]
= frozenset({"barista", "admin", "system"})`. В `transition_order`:

```python
order = _apply_transition(...)
if actor_role != "system":
    send_order_notification(order, new_status)
db_session.commit()
return order
```

**Rationale:**
- PDD §6.1 row явно говорит "notifications column пуста" для
  auto-close.
- INV-010 требует role isolation — но `"system"` не user-role (его
  нельзя присвоить через JWT, check'ается только в коде scheduler'а).
  Добавление в allow-list ограничено именно `(READY, COMPLETED)` —
  `"system"` не может делать другие переходы.
- Минимальный diff — не трогаем `transition_order_bridge` (он для
  delivery, не касается auto-close).

**Alternative rejected:**
- параметр `suppress_notifications: bool` в `transition_order`. Ок, но
  оставляет возможность бариста случайно подавить SMS. Через роль это
  атомарно — "system" ≡ "no SMS".
- Полностью обходить `transition_order`, вручную дергать
  `_apply_transition`. Ломает инкапсуляцию.

### D3: `close_stale_pickups` — один SELECT, потом цикл с savepoint

**Decision:** сервис SHALL выполнить

```python
settings = db.get(ShopSettings, 1)
cutoff = now - timedelta(minutes=settings.auto_close_minutes)
stale_ids = db.execute(
    sa.select(Order.id)
    .where(Order.type == OrderType.PICKUP)
    .where(Order.status == OrderStatus.READY)
    .where(Order.updated_at < cutoff)
    .limit(100)
).scalars().all()

closed = 0
for oid in stale_ids:
    try:
        with db.begin_nested():
            transition_order(oid, OrderStatus.COMPLETED, "system", db)
            order = db.get(Order, oid)
            order.auto_completed = True
            order.auto_completed_at = now
            db.flush()
        closed += 1
    except Exception:  # noqa: BLE001 — batch-resilience
        # Один плохой заказ не ломает весь прогон.
        db.rollback()  # откат savepoint внутри begin_nested достаточно
        continue
db.commit()
return closed
```

**Примечание FOR UPDATE SKIP LOCKED:** добавить `.with_for_update(
skip_locked=True)` только когда бэкенд — Postgres. Для SQLite (тесты)
этот clause не поддерживается — используем conditional через dialect
check или через параметр-флаг. Проще всего — `with_for_update(
skip_locked=True)` no-op под SQLite с
`execute_options(no_autoflush=True)` + `try/except NotImplementedError`.
Но самое простое: проверка `db.bind.dialect.name == "postgresql"` и
условное добавление clause.

**Rationale:** batch с SKIP LOCKED защищает от гонки двух beat'ов;
savepoint обеспечивает per-order atomicity; ограничение 100 не даёт
одному прогону растянуться в огромную транзакцию.

### D4: Celery task — `bind=True` не нужен

**Decision:** таска SHALL быть простой функцией без `bind=True`:

```python
@celery_app.task(name="pickup.close_stale")
def close_stale_pickups_task() -> int:
    from core_api.deps.database import SessionLocal
    from core_api.services.pickup_autoclose import close_stale_pickups

    with SessionLocal() as db:
        return close_stale_pickups(db, datetime.now(timezone.utc))
```

**Rationale:** нет нужды в `self.retry` (идемпотентность обеспечена
фильтром `status=READY` + `FOR UPDATE SKIP LOCKED`) и нет state.

### D5: Beat schedule — статический dict в celery_app.py

**Decision:**

```python
celery_app = Celery(
    "core_api",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["core_api.tasks.pickup_autoclose"],
)
celery_app.conf.beat_schedule = {
    "close-stale-pickups-every-60s": {
        "task": "pickup.close_stale",
        "schedule": 60.0,
    },
}
```

`backend=settings.redis_url` добавляется для `.apply().get()` в eager-
mode тестов (без backend `AsyncResult.get()` падает).

**Rationale:** частота жёстко закодирована (§Non-Goals). Добавление
`backend` — минимальный ценовой шаг (Redis уже broker, переиспользуем).

### D6: docker-compose — 2 новых сервиса, переиспользуем core-api Dockerfile

**Decision:** добавить `scheduler` и `core-api-worker` с `build.context=
. ; dockerfile=services/core-api/Dockerfile ; target: dev`, теми же
env_file/environment/volumes, что и `core-api`. Commands:

- `scheduler`: `["celery", "-A", "core_api.celery_app", "beat",
  "--loglevel=info"]`.
- `core-api-worker`: `["celery", "-A", "core_api.celery_app", "worker",
  "--loglevel=info", "--concurrency=2"]`.

depends_on: redis (healthy) + postgres (healthy) + db-seed
(completed_successfully, только для core-api-worker).

**Rationale:** shared-codebase approach (см. AGENTS.md rule: монорепо
packages устанавливаются в editable-mode). Scheduler не требует БД —
только очередь, так что depends_on только на redis.

**Alternative rejected:**
- один контейнер `celery -B -A ...` (beat + worker). Отклонено по
  task-spec: "NOT совмещать beat и worker в один контейнер" — production
  anti-pattern.
- отдельный Dockerfile для scheduler. Overkill; shared image работает.

### D7: Порядок внесения правок — минимизация blast radius

**Decision:** Изменения в `order_lifecycle.py` — в отдельном коммите
(логически GREEN-шаг 1), потом сервис и таска, потом celery_app, потом
docker-compose. Внутри одного GREEN-цикла (одна change) порядок
важен только для отладки тестов.

## Risks / Trade-offs

- **[Risk]** Расширение allow-list `{READY, COMPLETED}` ролью `system`
  может вскрыть непокрытый кейс — например, test_order_lifecycle
  assert'ит что `actor='system'` → reason=`role_not_allowed`. →
  **Mitigation:** grep test_order_lifecycle.py на `"system"`; если
  найдутся, разобраться — но `"system"` новая роль, скорее всего
  тестов нет.
- **[Risk]** `with db.begin_nested()` под SQLite может работать иначе
  (SQLite эмулирует savepoint'ы). → **Mitigation:** в тестах проверяем
  только happy-path закрытия; batch-resilience не покрыт тестом (не
  входил в RED-спец). Для GREEN это ок — production Postgres
  поддерживает savepoint полноценно.
- **[Risk]** `transition_order` делает `db.commit()` в конце — это
  сделает `auto_completed=true` невидимым, если мы выставляем его
  ПОСЛЕ `transition_order`. → **Mitigation:** после коммита от
  `transition_order` состояние в session уже "expired"; re-fetch
  `Order`, выставить `auto_completed=True`, второй commit. Либо
  использовать `transition_order_bridge` (без commit и без notify)
  и делать single commit на каждый заказ. **Preferred:** bridge-вариант
  — меньше round-trip'ов, чище семантика. Расширяем `_ALLOWED_ROLES`
  и используем `transition_order_bridge(oid, COMPLETED, "system", db)`
  (он не шлёт notification и не коммитит). Это лучше, чем
  `transition_order` — нам notification не нужна ни при каких обстоятельствах.
- **[Risk]** `backend=redis_url` может нарушить поведение existing
  `celery_app.send_task("sms_worker.order_status_changed", ...)` —
  sms-worker не ждёт результата, а backend теперь появится. →
  **Mitigation:** backend — broker для результатов, не меняет send_task
  semantics; sms-worker как был stateless, так и остаётся. Но на всякий
  случай проверим — если появляется leak, откатываем backend.
- **[Risk]** Postgres SKIP LOCKED под in-memory sqlite. →
  **Mitigation:** dialect check — под sqlite not-op clause, под
  postgres применяем.

### Atomicity Analysis (INV-004)

Операции auto-close НЕ относятся к финансовым платёжным потокам
(YuKassa), но они **косвенно** затрагивают loyalty accrual (INV-003).

Атомарность: каждый переход `READY → COMPLETED` вместе с
`_accrue_loyalty`, `auto_completed=true` и `auto_completed_at=now`
выполняется в одном savepoint (или одной транзакции при bridge-
варианте, см. D решение). Если что-то падает — savepoint откатывается,
заказ остаётся в READY, loyalty accrual не создаётся, следующий beat-
run попробует снова. Никаких частичных состояний.

### References: state machine §6.1

Affected transition: `READY → COMPLETED` (pickup только, PDD §6.1 row).
Этот переход уже разрешён в `_ALLOWED_TRANSITIONS`; GREEN расширяет
только `_ALLOWED_ROLES` — добавляет `"system"` к существующему
`{"barista", "admin"}`. Других переходов change не вводит.

## Migration Plan

Нет новых миграций. БД уже готова — `auto_completed`,
`auto_completed_at` (0005), `auto_close_minutes` (0008).

Deployment: после merge в main — пересборка docker-compose подтянет
новые сервисы. Возможен короткий window без scheduler — не критично
(auto-close задерживается на минуты, но не теряется).

Rollback: удалить `scheduler` и `core-api-worker` из docker-compose.
Code-level изменения в celery_app.py/order_lifecycle.py/services —
backward-compatible (allow-list только расширен, notification
suppression — no-op для существующих actor_role's).

## 152-FZ Compliance

Не применимо — сервис работает с `orders` и `shop_settings`, PII не
затрагивается.

## Open Questions

- **Использовать `transition_order` или `transition_order_bridge`?** →
  **Resolved:** bridge — не делает commit и не шлёт notification, что
  ровно то, что нужно. Сервис делает single commit per order (можно
  wrap'ить в savepoint). См. D3 updated.
- **SKIP LOCKED под sqlite?** → **Resolved:** через
  `db.bind.dialect.name == "postgresql"` conditional.
- **Нужен ли dead-letter / retry для failed заказа?** → **Resolved:**
  нет. Savepoint-rollback оставляет заказ в READY; следующий beat-run
  его подхватит. Если проблема системная — логируем, человек разбирает.
