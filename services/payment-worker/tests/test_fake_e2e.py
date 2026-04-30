"""RED: end-to-end fake → webhook → Order/Payment достигают финального статуса.

Здесь мы НЕ используем Celery-брокер — вместо этого напрямую дёргаем
FakeYukassaClient, затем зовём yukassa_fake_callback как функцию, перехватывая
исходящий httpx.post и прокидывая его в TestClient(app).
"""

from __future__ import annotations

import importlib
from unittest.mock import patch

from fastapi.testclient import TestClient


def _make_app_client(sqlite_engine, fake_redis):
    with (
        patch(
            "payment_worker.webhook.get_engine",
            return_value=sqlite_engine,
            create=True,
        ),
        patch(
            "payment_worker.webhook.get_redis",
            return_value=fake_redis,
            create=True,
        ),
    ):
        from payment_worker.webhook import app

        return TestClient(app)


def _drive_fake(outcome: str, app_client: TestClient, payment_id: str) -> None:
    """Форсирует срабатывание fake callback — POST в webhook через TestClient."""
    monkey_http = _MonkeyHttp(app_client)
    import payment_worker.yukassa_fake as fake_module

    with patch.object(fake_module.httpx, "Client", monkey_http.client_cls):
        fake_module.yukassa_fake_callback.run(
            payment_id, f"payment.{outcome}"
        )


class _MonkeyHttp:
    """Подменяет httpx.Client на адаптер к TestClient FastAPI."""

    def __init__(self, app_client: TestClient):
        app_client_ref = app_client

        class _Inner:
            def __init__(self, *a, **kw):
                self._c = app_client_ref

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def post(self, url, json=None, **kw):
                # url как http://payment-webhook:8241/webhooks/yukassa → path
                from urllib.parse import urlparse

                path = urlparse(url).path
                return self._c.post(
                    path,
                    json=json,
                    headers={
                        "X-Forwarded-For": "127.0.0.1",
                        "X-Event-Id": f"fake-{json['object']['id']}",
                    },
                )

        self.client_cls = _Inner


def _reload_fake(monkeypatch, outcome: str):
    monkeypatch.setenv("YUKASSA_BACKEND", "fake")
    monkeypatch.setenv("YUKASSA_FAKE_OUTCOME", outcome)
    monkeypatch.setenv("YUKASSA_WEBHOOK_IPS", "127.0.0.1")
    import payment_worker.settings as settings_module

    importlib.reload(settings_module)
    import payment_worker.yukassa_fake as fake_module

    importlib.reload(fake_module)
    return fake_module


def test_fake_success_drives_order_to_paid(
    monkeypatch, seed_user_order_payment, db_session, sqlite_engine, fake_redis
) -> None:
    from shared.enums import (
        LoyaltyTransactionType,
        OrderStatus,
        PaymentStatus,
    )

    payment = seed_user_order_payment["payment"]
    order = seed_user_order_payment["order"]

    fake_module = _reload_fake(monkeypatch, "success")
    client = fake_module.FakeYukassaClient()
    with patch.object(fake_module.yukassa_fake_callback, "apply_async", autospec=True):
        resp = client.create_payment(
            amount_kopecks=order.total,
            idempotency_key="k1",
            return_url="https://example.test/",
            description="Order",
        )
    # payment должен быть связан с yukassa_payment_id до webhook'а
    payment.status = PaymentStatus.AWAITING_CONFIRMATION
    payment.yukassa_payment_id = resp["payment_id"]
    db_session.commit()

    app_client = _make_app_client(sqlite_engine, fake_redis)
    _drive_fake("succeeded", app_client, resp["payment_id"])

    db_session.refresh(payment)
    db_session.refresh(order)
    assert payment.status == PaymentStatus.SUCCEEDED
    assert order.status == OrderStatus.PAID

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


def test_fake_canceled_drives_order_to_cancelled(
    monkeypatch, seed_user_order_payment, db_session, sqlite_engine, fake_redis
) -> None:
    from shared.enums import (
        LoyaltyTransactionType,
        OrderStatus,
        PaymentStatus,
    )

    payment = seed_user_order_payment["payment"]
    order = seed_user_order_payment["order"]
    promo = seed_user_order_payment["promocode"]
    initial_uses = promo.current_uses

    fake_module = _reload_fake(monkeypatch, "canceled")
    client = fake_module.FakeYukassaClient()
    with patch.object(fake_module.yukassa_fake_callback, "apply_async", autospec=True):
        resp = client.create_payment(
            amount_kopecks=order.total,
            idempotency_key="k1",
            return_url="https://example.test/",
            description="Order",
        )
    payment.status = PaymentStatus.AWAITING_CONFIRMATION
    payment.yukassa_payment_id = resp["payment_id"]
    db_session.commit()

    app_client = _make_app_client(sqlite_engine, fake_redis)
    _drive_fake("canceled", app_client, resp["payment_id"])

    db_session.refresh(payment)
    db_session.refresh(order)
    db_session.refresh(promo)
    assert order.status == OrderStatus.CANCELLED
    assert payment.status == PaymentStatus.PAYMENT_FAILED

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
    assert promo.current_uses == initial_uses - 1


def test_fake_http_error_triggers_compensation(
    monkeypatch, seed_user_order_payment, db_session, sqlite_engine, fake_redis
) -> None:
    """outcome=http_error → create_payment рейзит httpx.RequestError, Celery
    исчерпывает max_retries и вызывает _fail_payment_and_cancel_order.
    """
    from shared.enums import (
        LoyaltyTransactionType,
        OrderStatus,
        PaymentStatus,
    )

    order = seed_user_order_payment["order"]
    payment = seed_user_order_payment["payment"]
    promo = seed_user_order_payment["promocode"]
    initial_uses = promo.current_uses

    monkeypatch.setenv("YUKASSA_BACKEND", "fake")
    monkeypatch.setenv("YUKASSA_FAKE_OUTCOME", "http_error")

    import payment_worker.settings as settings_module
    import payment_worker.tasks as tasks_module
    import payment_worker.yukassa_fake as fake_module

    importlib.reload(settings_module)
    importlib.reload(fake_module)
    importlib.reload(tasks_module)

    # Прямо вызываем компенсацию — контракт RED: её должен вызывать taskов
    # retry-loop после истощения max_retries. В GREEN проверим через Celery
    # eager, здесь — прямой вызов.
    with patch.object(tasks_module, "get_engine", return_value=sqlite_engine):
        tasks_module._fail_payment_and_cancel_order(
            str(order.id), str(payment.id)
        )

    db_session.refresh(order)
    db_session.refresh(payment)
    db_session.refresh(promo)
    assert order.status == OrderStatus.CANCELLED
    assert payment.status == PaymentStatus.PAYMENT_FAILED
    assert promo.current_uses == initial_uses - 1

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
