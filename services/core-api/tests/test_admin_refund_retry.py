"""Admin refund retry route tests (PDD §6.2, INV-002, INV-016)."""
from __future__ import annotations

import uuid
from unittest.mock import patch

import fakeredis
import pytest
from fastapi.testclient import TestClient

from core_api.main import app
from core_api.rbac_matrix import ADMIN, BARISTA, PUBLIC_ROUTES, ROUTE_MATRIX
from shared.enums import OrderStatus, OrderType, PaymentStatus
from tests._factories.orders import make_user


@pytest.fixture
def admin_refund_client(db_session):
    def _override_db():
        yield db_session

    fake_redis = fakeredis.FakeRedis()

    def _override_redis():
        yield fake_redis

    with (
        patch("core_api.deps.redis.get_redis", side_effect=_override_redis),
        patch("core_api.deps.database.get_session", side_effect=_override_db),
        patch("core_api.deps.database.get_db", side_effect=_override_db),
        TestClient(app) as c,
    ):
        yield c
    fake_redis.flushall()


def _seed_order_payment(
    db_session,
    *,
    payment_status: PaymentStatus = PaymentStatus.REFUND_FAILED,
    amount: int = 50000,
):
    from shared.models import Order, Payment

    user = make_user(db_session)
    order = Order(
        user_id=user.id,
        status=OrderStatus.CANCELLED,
        type=OrderType.PICKUP,
        subtotal=amount,
        discount_amount=0,
        delivery_fee=0,
        total=amount,
    )
    db_session.add(order)
    db_session.flush()
    payment = Payment(
        order_id=order.id,
        amount=amount,
        status=payment_status,
        yukassa_payment_id="pay_" + uuid.uuid4().hex[:10],
    )
    db_session.add(payment)
    db_session.commit()
    return order, payment


def test_admin_refund_retry_route_registered_once() -> None:
    matches = []
    for route in app.routes:
        methods = getattr(route, "methods", set()) or set()
        path = getattr(route, "path", "")
        if "POST" in methods and path == "/api/v1/admin/orders/{order_id}/refund/retry":
            matches.append(route)

    assert len(matches) == 1


def test_admin_refund_retry_rbac_matrix_admin_only() -> None:
    key = ("POST", "/api/v1/admin/orders/{order_id}/refund/retry")
    assert ROUTE_MATRIX[key] == {ADMIN}
    assert BARISTA not in ROUTE_MATRIX[key]
    assert key not in PUBLIC_ROUTES


def test_admin_refund_retry_requires_authorization(admin_refund_client) -> None:
    response = admin_refund_client.post(
        f"/api/v1/admin/orders/{uuid.uuid4()}/refund/retry"
    )

    assert response.status_code == 401


def test_admin_refund_retry_rejects_barista(
    admin_refund_client, barista_headers, db_session
) -> None:
    order, _payment = _seed_order_payment(db_session)

    response = admin_refund_client.post(
        f"/api/v1/admin/orders/{order.id}/refund/retry",
        headers=barista_headers,
    )

    assert response.status_code == 403


def test_admin_refund_retry_enqueues_payment_worker_task(
    admin_refund_client, admin_headers, db_session
) -> None:
    order, payment = _seed_order_payment(db_session)

    with patch("core_api.services.refund_retry.celery_app.send_task") as send_task:
        response = admin_refund_client.post(
            f"/api/v1/admin/orders/{order.id}/refund/retry",
            headers=admin_headers,
        )

    assert response.status_code == 202
    body = response.json()
    assert body["order_id"] == str(order.id)
    assert body["payment_id"] == str(payment.id)
    assert body["payment_status"] == "refund_failed"
    assert body["queued"] is True

    send_task.assert_called_once()
    args, kwargs = send_task.call_args
    assert args[0] == "payment_worker.tasks.initiate_refund"
    payload = kwargs["args"]
    assert payload[0] == str(payment.id)
    assert payload[1] == payment.amount
    assert payload[2].startswith(f"refund-retry-{payment.id}-")


def test_admin_refund_retry_rejects_non_failed_payment(
    admin_refund_client, admin_headers, db_session
) -> None:
    order, _payment = _seed_order_payment(
        db_session,
        payment_status=PaymentStatus.SUCCEEDED,
    )

    with patch("core_api.services.refund_retry.celery_app.send_task") as send_task:
        response = admin_refund_client.post(
            f"/api/v1/admin/orders/{order.id}/refund/retry",
            headers=admin_headers,
        )

    assert response.status_code == 409
    assert response.json()["detail"] == "refund_not_retryable"
    send_task.assert_not_called()
