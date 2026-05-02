"""Customer notification feed tests (PDD §5.2, INV-002, INV-013)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import fakeredis
import pytest
from fastapi.testclient import TestClient

from core_api.main import app
from core_api.rbac_matrix import CUSTOMER, PUBLIC_ROUTES, ROUTE_MATRIX
from shared.enums import (
    NotificationChannel,
    NotificationStatus,
    NotificationType,
    OrderStatus,
    OrderType,
)
from shared.models.notification import Notification
from tests._factories.orders import make_user, seed_orders_across_statuses
from tests._helpers.jwt import auth_headers_for_user


@pytest.fixture
def notification_client(db_session):
    """TestClient wired to the current DB session and fake Redis."""

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


def _seed_notification(
    db_session,
    *,
    user_id,
    message_ru: str,
    message_en: str,
    channel: NotificationChannel = NotificationChannel.IN_APP,
    order_id=None,
    created_at: datetime,
) -> Notification:
    row = Notification(
        user_id=user_id,
        order_id=order_id,
        channel=channel,
        type=NotificationType.ORDER_STATUS_CHANGE,
        status=NotificationStatus.SENT,
        message_ru=message_ru,
        message_en=message_en,
        sent_at=created_at,
        created_at=created_at,
    )
    db_session.add(row)
    db_session.flush()
    return row


def test_customer_notifications_route_registered_once() -> None:
    matches = []
    for route in app.routes:
        methods = getattr(route, "methods", set()) or set()
        path = getattr(route, "path", "")
        if "GET" in methods and path == "/api/v1/profile/notifications":
            matches.append(route)

    assert len(matches) == 1


def test_customer_notifications_rbac_matrix_customer_only() -> None:
    key = ("GET", "/api/v1/profile/notifications")
    assert ROUTE_MATRIX[key] == {CUSTOMER}
    assert key not in PUBLIC_ROUTES


def test_customer_notifications_requires_authorization(notification_client) -> None:
    response = notification_client.get("/api/v1/profile/notifications")

    assert response.status_code == 401


def test_customer_notifications_rejects_staff(
    notification_client,
    barista_headers,
) -> None:
    response = notification_client.get(
        "/api/v1/profile/notifications",
        headers=barista_headers,
    )

    assert response.status_code == 403


def test_customer_notifications_returns_own_in_app_rows_newest_first(
    notification_client,
    db_session,
) -> None:
    user = make_user(db_session)
    other_user = make_user(db_session)
    db_session.commit()
    seed = seed_orders_across_statuses(
        db_session,
        user=user,
        counts={(OrderStatus.PAID, OrderType.PICKUP): 1},
    )
    [order_id] = seed.order_ids_by_bucket[(OrderStatus.PAID, OrderType.PICKUP)]
    base_time = datetime(2026, 5, 2, 12, 0, tzinfo=UTC)
    older = _seed_notification(
        db_session,
        user_id=user.id,
        order_id=order_id,
        message_ru="Заказ оплачен",
        message_en="Order paid",
        created_at=base_time,
    )
    newer = _seed_notification(
        db_session,
        user_id=user.id,
        order_id=None,
        message_ru="Заказ готовится",
        message_en="Order is being prepared",
        created_at=base_time + timedelta(minutes=5),
    )
    _seed_notification(
        db_session,
        user_id=user.id,
        message_ru="SMS duplicate",
        message_en="SMS duplicate",
        channel=NotificationChannel.SMS,
        created_at=base_time + timedelta(minutes=10),
    )
    _seed_notification(
        db_session,
        user_id=other_user.id,
        message_ru="Чужое уведомление",
        message_en="Other user notification",
        created_at=base_time + timedelta(minutes=15),
    )
    db_session.commit()

    response = notification_client.get(
        "/api/v1/profile/notifications",
        headers=auth_headers_for_user(user.id),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_count"] == 2
    assert [row["id"] for row in body["notifications"]] == [
        str(newer.id),
        str(older.id),
    ]
    assert body["notifications"][1]["order_id"] == str(order_id)
    assert body["notifications"][0]["channel"] == "in_app"
    assert "user_id" not in body["notifications"][0]


def test_customer_notifications_paginates(
    notification_client,
    db_session,
) -> None:
    user = make_user(db_session)
    db_session.commit()
    base_time = datetime(2026, 5, 2, 12, 0, tzinfo=UTC)
    seeded = [
        _seed_notification(
            db_session,
            user_id=user.id,
            message_ru=f"Уведомление {idx}",
            message_en=f"Notification {idx}",
            created_at=base_time + timedelta(minutes=idx),
        )
        for idx in range(3)
    ]
    db_session.commit()

    response = notification_client.get(
        "/api/v1/profile/notifications?page=2&per_page=1",
        headers=auth_headers_for_user(user.id),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_count"] == 3
    assert body["page"] == 2
    assert body["per_page"] == 1
    assert [row["id"] for row in body["notifications"]] == [str(seeded[1].id)]


def test_customer_notifications_rejects_per_page_over_50(
    notification_client,
    db_session,
) -> None:
    user = make_user(db_session)
    db_session.commit()

    response = notification_client.get(
        "/api/v1/profile/notifications?per_page=51",
        headers=auth_headers_for_user(user.id),
    )

    assert response.status_code == 422


def test_customer_notifications_does_not_log_pii(
    notification_client,
    db_session,
    grace_logs,
) -> None:
    user = make_user(db_session)
    db_session.commit()
    raw_phone = "+79991234567"
    _seed_notification(
        db_session,
        user_id=user.id,
        message_ru="Заказ готов",
        message_en="Order ready",
        created_at=datetime(2026, 5, 2, 12, 0, tzinfo=UTC),
    )
    db_session.commit()

    response = notification_client.get(
        "/api/v1/profile/notifications",
        headers=auth_headers_for_user(user.id),
    )

    assert response.status_code == 200
    assert raw_phone not in "\n".join(grace_logs.lines)
