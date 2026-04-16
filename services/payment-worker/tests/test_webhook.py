"""RED: контракт FastAPI-эндпоинта POST /webhooks/yukassa (PDD §4.2, §7.9).

Импорт payment_worker.webhook пока даёт ImportError — это и есть RED-состояние.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest


WHITELISTED_IP = "127.0.0.1"


def _make_client(sqlite_engine, fake_redis):
    """Поднимает TestClient с подкинутыми sqlite + fakeredis."""
    from fastapi.testclient import TestClient

    with patch("payment_worker.webhook.get_engine", return_value=sqlite_engine, create=True):
        with patch("payment_worker.webhook.get_redis", return_value=fake_redis, create=True):
            from payment_worker.webhook import app

            return TestClient(app)


def test_reject_request_from_untrusted_ip(
    seed_user_order_payment, db_session, sqlite_engine, fake_redis, yukassa_env
) -> None:
    from shared.enums import OrderStatus, PaymentStatus

    client = _make_client(sqlite_engine, fake_redis)
    body = {
        "event": "payment.succeeded",
        "object": {"id": "pay_xyz"},
    }
    # IP не в YUKASSA_WEBHOOK_IPS
    resp = client.post(
        "/webhooks/yukassa",
        json=body,
        headers={
            "X-Forwarded-For": "203.0.113.9",
            "X-Event-Id": str(uuid.uuid4()),
        },
    )
    assert resp.status_code == 403

    db_session.refresh(seed_user_order_payment["payment"])
    db_session.refresh(seed_user_order_payment["order"])
    assert seed_user_order_payment["payment"].status == PaymentStatus.PENDING
    assert seed_user_order_payment["order"].status == OrderStatus.CREATED


def test_duplicate_event_id_returns_200_without_mutation(
    seed_user_order_payment, db_session, sqlite_engine, fake_redis, yukassa_env
) -> None:
    from shared.enums import OrderStatus, PaymentStatus

    event_id = "evt-dup"
    # Помечаем как обработанный через тот же фейковый redis
    fake_redis.set(f"yukassa:event:{event_id}", "1")

    client = _make_client(sqlite_engine, fake_redis)
    body = {"event": "payment.succeeded", "object": {"id": "pay_xyz"}}
    resp = client.post(
        "/webhooks/yukassa",
        json=body,
        headers={
            "X-Forwarded-For": WHITELISTED_IP,
            "X-Event-Id": event_id,
        },
    )
    assert resp.status_code == 200

    db_session.refresh(seed_user_order_payment["payment"])
    db_session.refresh(seed_user_order_payment["order"])
    assert seed_user_order_payment["payment"].status == PaymentStatus.PENDING
    assert seed_user_order_payment["order"].status == OrderStatus.CREATED


def test_payment_succeeded_advances_payment_and_order(
    seed_user_order_payment, db_session, sqlite_engine, fake_redis, yukassa_env
) -> None:
    from shared.enums import (
        LoyaltyTransactionType,
        NotificationChannel,
        OrderStatus,
        PaymentStatus,
    )

    payment = seed_user_order_payment["payment"]
    order = seed_user_order_payment["order"]
    user = seed_user_order_payment["user"]
    payment.status = PaymentStatus.AWAITING_CONFIRMATION
    payment.yukassa_payment_id = "pay_xyz"
    db_session.commit()

    fake_redis.set(f"cart:{user.id}", "{}")

    client = _make_client(sqlite_engine, fake_redis)
    resp = client.post(
        "/webhooks/yukassa",
        json={"event": "payment.succeeded", "object": {"id": "pay_xyz"}},
        headers={"X-Forwarded-For": WHITELISTED_IP, "X-Event-Id": "evt-ok"},
    )
    assert resp.status_code == 200

    db_session.refresh(payment)
    db_session.refresh(order)
    assert payment.status == PaymentStatus.SUCCEEDED
    assert order.status == OrderStatus.PAID

    # Ключ корзины удалён
    assert fake_redis.get(f"cart:{user.id}") is None

    # Резерв лояльности → REDEMPTION (или пара REVERSAL+REDEMPTION)
    from shared.models.loyalty_transaction import LoyaltyTransaction

    redemptions = (
        db_session.query(LoyaltyTransaction)
        .filter(
            LoyaltyTransaction.order_id == order.id,
            LoyaltyTransaction.type == LoyaltyTransactionType.REDEMPTION,
        )
        .all()
    )
    assert len(redemptions) >= 1

    # Уведомления: sms + in_app, тело содержит «Заказ оплачен»
    from shared.models.notification import Notification

    notifs = (
        db_session.query(Notification)
        .filter(Notification.order_id == order.id)
        .all()
    )
    channels = {n.channel for n in notifs}
    assert NotificationChannel.SMS in channels
    assert NotificationChannel.IN_APP in channels
    assert any("Заказ оплачен" in (n.message_ru or "") for n in notifs)


def test_payment_canceled_cancels_order_and_unreserves(
    seed_user_order_payment, db_session, sqlite_engine, fake_redis, yukassa_env
) -> None:
    from shared.enums import (
        LoyaltyTransactionType,
        NotificationChannel,
        OrderStatus,
        PaymentStatus,
    )

    payment = seed_user_order_payment["payment"]
    order = seed_user_order_payment["order"]
    promo = seed_user_order_payment["promocode"]
    payment.status = PaymentStatus.AWAITING_CONFIRMATION
    payment.yukassa_payment_id = "pay_xyz"
    order.points_used = 50
    db_session.commit()

    client = _make_client(sqlite_engine, fake_redis)
    resp = client.post(
        "/webhooks/yukassa",
        json={"event": "payment.canceled", "object": {"id": "pay_xyz"}},
        headers={"X-Forwarded-For": WHITELISTED_IP, "X-Event-Id": "evt-cancel"},
    )
    assert resp.status_code == 200

    db_session.refresh(payment)
    db_session.refresh(order)
    db_session.refresh(promo)
    assert payment.status == PaymentStatus.PAYMENT_FAILED
    assert order.status == OrderStatus.CANCELLED
    assert promo.current_uses == 0

    from shared.models.loyalty_transaction import LoyaltyTransaction

    reversals = (
        db_session.query(LoyaltyTransaction)
        .filter(
            LoyaltyTransaction.order_id == order.id,
            LoyaltyTransaction.type == LoyaltyTransactionType.REVERSAL,
        )
        .all()
    )
    assert len(reversals) == 1
    assert reversals[0].amount == 50

    from shared.models.notification import Notification

    notifs = (
        db_session.query(Notification)
        .filter(Notification.order_id == order.id)
        .all()
    )
    assert any(
        n.channel == NotificationChannel.IN_APP
        and "Платёж не прошёл" in (n.message_ru or "")
        for n in notifs
    )


def test_refund_succeeded_marks_refunded(
    seed_user_order_payment, db_session, sqlite_engine, fake_redis, yukassa_env
) -> None:
    from shared.enums import PaymentStatus

    payment = seed_user_order_payment["payment"]
    payment.status = PaymentStatus.REFUND_PENDING
    payment.yukassa_payment_id = "pay_xyz"
    db_session.commit()

    client = _make_client(sqlite_engine, fake_redis)
    resp = client.post(
        "/webhooks/yukassa",
        json={
            "event": "refund.succeeded",
            "object": {"payment_id": "pay_xyz"},
        },
        headers={"X-Forwarded-For": WHITELISTED_IP, "X-Event-Id": "evt-ref-ok"},
    )
    assert resp.status_code == 200

    db_session.refresh(payment)
    assert payment.status == PaymentStatus.REFUNDED


def test_refund_canceled_marks_refund_failed_and_notifies_admin(
    seed_user_order_payment, db_session, sqlite_engine, fake_redis, yukassa_env
) -> None:
    from shared.enums import PaymentStatus

    payment = seed_user_order_payment["payment"]
    payment.status = PaymentStatus.REFUND_PENDING
    payment.yukassa_payment_id = "pay_xyz"
    db_session.commit()

    client = _make_client(sqlite_engine, fake_redis)
    resp = client.post(
        "/webhooks/yukassa",
        json={
            "event": "refund.canceled",
            "object": {"payment_id": "pay_xyz"},
        },
        headers={"X-Forwarded-For": WHITELISTED_IP, "X-Event-Id": "evt-ref-fail"},
    )
    assert resp.status_code == 200

    db_session.refresh(payment)
    assert payment.status == PaymentStatus.REFUND_FAILED

    from shared.models.notification import Notification

    # Хотя бы одно уведомление, связанное с этим заказом, должно быть записано
    notifs = (
        db_session.query(Notification)
        .filter(Notification.order_id == seed_user_order_payment["order"].id)
        .all()
    )
    assert len(notifs) >= 1


def test_unknown_event_type_returns_200_no_mutation(
    seed_user_order_payment, db_session, sqlite_engine, fake_redis, yukassa_env
) -> None:
    from shared.enums import OrderStatus, PaymentStatus

    payment = seed_user_order_payment["payment"]
    order = seed_user_order_payment["order"]
    payment.status = PaymentStatus.AWAITING_CONFIRMATION
    payment.yukassa_payment_id = "pay_xyz"
    db_session.commit()
    prev_payment_status = payment.status
    prev_order_status = order.status

    client = _make_client(sqlite_engine, fake_redis)
    resp = client.post(
        "/webhooks/yukassa",
        json={
            "event": "payment.waiting_for_capture",
            "object": {"id": "pay_xyz"},
        },
        headers={"X-Forwarded-For": WHITELISTED_IP, "X-Event-Id": "evt-unknown"},
    )
    assert resp.status_code == 200

    db_session.refresh(payment)
    db_session.refresh(order)
    assert payment.status == prev_payment_status
    assert order.status == prev_order_status


def test_processing_exception_surfaces_as_500(
    seed_user_order_payment, db_session, sqlite_engine, fake_redis, yukassa_env
) -> None:
    payment = seed_user_order_payment["payment"]
    payment.yukassa_payment_id = "pay_xyz"
    db_session.commit()

    client = _make_client(sqlite_engine, fake_redis)

    # Подменяем диспетчер, чтобы он взрывался
    with patch(
        "payment_worker.webhook.dispatch_event",
        side_effect=RuntimeError("kaboom"),
        create=True,
    ):
        with pytest.raises(RuntimeError):  # TestClient по умолчанию прокидывает
            client.post(
                "/webhooks/yukassa",
                json={"event": "payment.succeeded", "object": {"id": "pay_xyz"}},
                headers={
                    "X-Forwarded-For": WHITELISTED_IP,
                    "X-Event-Id": "evt-crash",
                },
            )

    # event_id НЕ должен быть помечен как обработанный — ЮKassa повторит
    assert fake_redis.get("yukassa:event:evt-crash") is None
