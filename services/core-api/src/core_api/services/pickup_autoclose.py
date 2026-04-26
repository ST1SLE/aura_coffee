# START_MODULE_CONTRACT
#   PURPOSE: Scheduled job that closes stale READY pickup orders by transitioning
#            them to COMPLETED via the canonical lifecycle bridge — preserves
#            INV-016 single-entry-point and suppresses notifications via
#            actor_role="system".
#   SCOPE:   close_stale_pickups (one batch per call).
#   DEPENDS: M-SHARED (Order, ShopSettings, OrderStatus/Type),
#            services.order_lifecycle.transition_order_bridge, M-DATABASE
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §6.1 (autoclose row),
#            §7.1 Phase 6/4, INV-003, INV-016
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   close_stale_pickups - close READY pickups stale beyond auto_close_minutes
# END_MODULE_MAP
"""Auto-close pickup-заказов по таймеру (PDD §6.1 row "READY → COMPLETED —
Автозакрытие по таймеру", §7.1 Phase 6 item 4).

Сервис читает `ShopSettings.auto_close_minutes` и закрывает pickup-заказы,
висящие в READY дольше cutoff. Переход идёт через `order_lifecycle`
(single-entry-point для INV-016). Уведомления подавляются через
actor_role="system".
"""
from __future__ import annotations

from datetime import datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.orm import Session

from shared.enums import OrderStatus, OrderType
from shared.models import Order, ShopSettings

from core_api.services.order_lifecycle import transition_order_bridge


_BATCH_LIMIT = 100


# START_CONTRACT: close_stale_pickups
#   PURPOSE: Sweep up to _BATCH_LIMIT READY pickup orders older than
#            ShopSettings.auto_close_minutes and finalize each with READY →
#            COMPLETED via the lifecycle bridge plus auto_completed bookkeeping.
#   INPUTS:  db: Session
#            now: datetime — caller-fixed clock
#   OUTPUTS: int — number of orders successfully closed.
#   SIDE_EFFECTS: DB SELECT (with FOR UPDATE SKIP LOCKED on Postgres),
#                 per-order savepoint with bridge transition + UPDATE, final
#                 commit. Source: READY (PICKUP). Target: COMPLETED. Loyalty
#                 accrual fires inside _apply_transition (INV-003). Failures on
#                 a single order do not abort the batch.
#   LINKS:   PDD §6.1, §7.1, INV-003, INV-016
# END_CONTRACT: close_stale_pickups
def close_stale_pickups(db: Session, now: datetime) -> int:
    """Закрывает все pickup/READY-заказы с `updated_at < now - auto_close_minutes`.

    Для каждого заказа: переход READY→COMPLETED через order_lifecycle
    (loyalty accrual как side-effect), затем `auto_completed=true`,
    `auto_completed_at=now`. Каждый заказ в своём savepoint, чтобы ошибка
    одного не отменяла остальные.
    """
    settings_row = db.get(ShopSettings, 1)
    if settings_row is None:
        return 0

    cutoff = now - timedelta(minutes=settings_row.auto_close_minutes)

    stmt = (
        sa.select(Order.id)
        .where(Order.type == OrderType.PICKUP)
        .where(Order.status == OrderStatus.READY)
        .where(Order.updated_at < cutoff)
        .limit(_BATCH_LIMIT)
    )
    # SKIP LOCKED — защита от гонки двух beat'ов; не поддерживается sqlite.
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        stmt = stmt.with_for_update(skip_locked=True)

    stale_ids = list(db.execute(stmt).scalars().all())
    if not stale_ids:
        return 0

    closed = 0
    for oid in stale_ids:
        try:
            with db.begin_nested():
                transition_order_bridge(oid, OrderStatus.COMPLETED, "system", db)
                order = db.get(Order, oid)
                if order is not None:
                    order.auto_completed = True
                    order.auto_completed_at = now
                    db.flush()
            closed += 1
        except Exception:
            # Один проблемный заказ не валит всю пачку; savepoint откатился.
            continue

    db.commit()
    return closed
