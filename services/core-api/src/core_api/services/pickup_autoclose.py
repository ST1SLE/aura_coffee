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
