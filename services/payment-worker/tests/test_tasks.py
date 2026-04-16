"""RED: контракт Celery-тасков payment-worker.

Эти тесты импортируют payment_worker.tasks.create_payment / initiate_refund,
которых ещё нет (в tasks.py сейчас только health_check). Ожидание: ImportError
до GREEN.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest


def test_create_payment_happy_path_marks_awaiting_confirmation(
    seed_user_order_payment, db_session, yukassa_env, sqlite_engine
) -> None:
    from shared.enums import OrderStatus, PaymentStatus

    # Подкладываем sqlite-движок под модуль payment-worker
    with patch("payment_worker.tasks.get_engine", return_value=sqlite_engine, create=True):
        fake_client = MagicMock()
        fake_client.create_payment.return_value = {
            "payment_id": "pay_xyz",
            "confirmation_url": "https://yoo/confirm",
            "status": "pending",
        }
        with patch("payment_worker.tasks.YukassaClient", return_value=fake_client, create=True):
            from payment_worker.tasks import create_payment

            create_payment.run(
                order_id=str(seed_user_order_payment["order"].id),
                amount_kopecks=seed_user_order_payment["order"].total,
                idempotency_key="uuid-3",
            )

    from shared.models.order import Order
    from shared.models.payment import Payment

    payment = db_session.get(Payment, seed_user_order_payment["payment"].id)
    order = db_session.get(Order, seed_user_order_payment["order"].id)
    db_session.refresh(payment)
    db_session.refresh(order)
    assert payment.yukassa_payment_id == "pay_xyz"
    assert payment.confirmation_url == "https://yoo/confirm"
    assert payment.status == PaymentStatus.AWAITING_CONFIRMATION
    assert order.status == OrderStatus.CREATED


def test_create_payment_task_has_retry_policy() -> None:
    from payment_worker.tasks import create_payment

    assert create_payment.max_retries == 3
    assert create_payment.retry_backoff  # truthy
    autoretry = getattr(create_payment, "autoretry_for", ())
    # autoretry_for может быть tuple или set
    assert httpx.RequestError in tuple(autoretry)


def test_create_payment_compensation_on_exhausted_retries(
    seed_user_order_payment, db_session, sqlite_engine
) -> None:
    from shared.enums import LoyaltyTransactionType, OrderStatus, PaymentStatus

    with patch("payment_worker.tasks.get_engine", return_value=sqlite_engine, create=True):
        from payment_worker.tasks import _fail_payment_and_cancel_order

        _fail_payment_and_cancel_order(
            order_id=str(seed_user_order_payment["order"].id),
            payment_id=str(seed_user_order_payment["payment"].id),
        )

    from shared.models.loyalty_transaction import LoyaltyTransaction
    from shared.models.order import Order
    from shared.models.payment import Payment
    from shared.models.promocode import Promocode

    payment = db_session.get(Payment, seed_user_order_payment["payment"].id)
    order = db_session.get(Order, seed_user_order_payment["order"].id)
    promo = db_session.get(Promocode, seed_user_order_payment["promocode"].id)
    db_session.refresh(payment)
    db_session.refresh(order)
    db_session.refresh(promo)

    assert payment.status == PaymentStatus.PAYMENT_FAILED
    assert order.status == OrderStatus.CANCELLED
    assert promo.current_uses == 0

    reversals = [
        tx
        for tx in db_session.query(LoyaltyTransaction)
        .filter(LoyaltyTransaction.order_id == order.id)
        .all()
        if tx.type == LoyaltyTransactionType.REVERSAL
    ]
    assert len(reversals) == 1
    assert reversals[0].amount == 100
    assert reversals[0].balance_after == 100


def test_create_payment_compensation_is_atomic(
    seed_user_order_payment, db_session, sqlite_engine
) -> None:
    """Компенсация должна быть атомарной — если падает промокод, Payment/Order
    откатываются.
    """
    from shared.enums import OrderStatus, PaymentStatus

    with patch("payment_worker.tasks.get_engine", return_value=sqlite_engine, create=True):
        with patch(
            "payment_worker.tasks._decrement_promocode",
            side_effect=RuntimeError("boom"),
            create=True,
        ):
            from payment_worker.tasks import _fail_payment_and_cancel_order

            with pytest.raises(RuntimeError):
                _fail_payment_and_cancel_order(
                    order_id=str(seed_user_order_payment["order"].id),
                    payment_id=str(seed_user_order_payment["payment"].id),
                )

    from shared.models.order import Order
    from shared.models.payment import Payment

    payment = db_session.get(Payment, seed_user_order_payment["payment"].id)
    order = db_session.get(Order, seed_user_order_payment["order"].id)
    db_session.refresh(payment)
    db_session.refresh(order)
    # Исходное состояние не тронуто
    assert payment.status == PaymentStatus.PENDING
    assert order.status == OrderStatus.CREATED


def test_initiate_refund_success_marks_refund_pending(
    seed_user_order_payment, db_session, sqlite_engine
) -> None:
    from shared.enums import PaymentStatus

    # Переводим Payment в SUCCEEDED перед refund
    payment = db_session.get(
        __import__(
            "shared.models.payment", fromlist=["Payment"]
        ).Payment,
        seed_user_order_payment["payment"].id,
    )
    payment.status = PaymentStatus.SUCCEEDED
    payment.yukassa_payment_id = "pay_xyz"
    db_session.commit()

    fake_client = MagicMock()
    fake_client.create_refund.return_value = {
        "id": "ref_abc",
        "status": "pending",
        "payment_id": "pay_xyz",
    }
    with patch("payment_worker.tasks.get_engine", return_value=sqlite_engine, create=True):
        with patch("payment_worker.tasks.YukassaClient", return_value=fake_client, create=True):
            from payment_worker.tasks import initiate_refund

            initiate_refund.run(
                payment_id=str(payment.id),
                amount_kopecks=payment.amount,
            )

    db_session.refresh(payment)
    assert payment.status == PaymentStatus.REFUND_PENDING


def test_initiate_refund_failure_does_not_mutate(
    seed_user_order_payment, db_session, sqlite_engine
) -> None:
    from shared.enums import PaymentStatus

    payment = db_session.get(
        __import__(
            "shared.models.payment", fromlist=["Payment"]
        ).Payment,
        seed_user_order_payment["payment"].id,
    )
    payment.status = PaymentStatus.SUCCEEDED
    payment.yukassa_payment_id = "pay_xyz"
    db_session.commit()

    fake_client = MagicMock()
    fake_client.create_refund.side_effect = httpx.RequestError("boom")

    with patch("payment_worker.tasks.get_engine", return_value=sqlite_engine, create=True):
        with patch("payment_worker.tasks.YukassaClient", return_value=fake_client, create=True):
            from payment_worker.tasks import initiate_refund

            # Задача не должна падать наружу — ошибка поглощается и логируется
            initiate_refund.run(
                payment_id=str(payment.id),
                amount_kopecks=payment.amount,
            )

    db_session.refresh(payment)
    assert payment.status == PaymentStatus.SUCCEEDED
