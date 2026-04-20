"""RED: тесты staff-scoped detail заказа (admin-orders-api, PDD §4.5, INV-010).

Символы из core_api.services.order_history и router /api/v1/admin/orders/{id}
импортируются ВНУТРИ тестов — RED-фаза их не содержит.
"""
from __future__ import annotations

import uuid
from unittest.mock import patch

import fakeredis
import pytest
from fastapi.testclient import TestClient

from core_api.main import app
from shared.enums import OrderStatus, OrderType
from tests._factories.orders import make_user, seed_orders_across_statuses


@pytest.fixture
def admin_feed_client(db_session):
    def _override_db():
        yield db_session

    fake_redis = fakeredis.FakeRedis()

    def _override_redis():
        yield fake_redis

    with (
        patch("core_api.deps.redis.get_redis", side_effect=_override_redis),
        patch("core_api.deps.database.get_session", side_effect=_override_db),
        patch("core_api.deps.database.get_db", side_effect=_override_db),
    ):
        with TestClient(app) as c:
            yield c
    fake_redis.flushall()


# ===========================================================================
# 3.x — get_order_for_staff service tests
# ===========================================================================


def test_get_order_for_staff_symbol_absent() -> None:
    """3.1 — символ get_order_for_staff должен существовать после GREEN."""
    from core_api.services.order_history import get_order_for_staff  # noqa: F401

    assert callable(get_order_for_staff)


def test_get_order_for_staff_returns_other_users_order(db_session) -> None:
    """3.2 — персонал может прочитать заказ любого клиента без ownership-check."""
    from core_api.services.order_history import get_order_for_staff

    user_b = make_user(db_session)
    db_session.commit()

    seed = seed_orders_across_statuses(
        db_session,
        user=user_b,
        counts={(OrderStatus.PREPARING, OrderType.PICKUP): 1},
    )
    [order_id] = seed.order_ids_by_bucket[(OrderStatus.PREPARING, OrderType.PICKUP)]

    result = get_order_for_staff(order_id=order_id, db_session=db_session)

    assert result.user_id == user_b.id
    assert result.id == order_id


def test_get_order_for_staff_raises_on_unknown_id(db_session) -> None:
    """3.3 — несуществующий id → designated "order not found" domain error."""
    from core_api.services.order_history import (
        OrderNotFoundForStaffError,
        get_order_for_staff,
    )

    unknown_id = uuid.uuid4()

    with pytest.raises(OrderNotFoundForStaffError):
        get_order_for_staff(order_id=unknown_id, db_session=db_session)


# ===========================================================================
# 5.x — GET /api/v1/admin/orders/{order_id} router tests
# ===========================================================================


def test_admin_orders_detail_route_not_registered() -> None:
    """5.1 — маршрут регистрируется ровно один раз в app.routes."""
    matches = []
    for route in app.routes:
        methods = getattr(route, "methods", set()) or set()
        path = getattr(route, "path", "")
        if "GET" in methods and path == "/api/v1/admin/orders/{order_id}":
            matches.append(route)

    assert len(matches) == 1, (
        f"Ожидался ровно 1 GET /api/v1/admin/orders/{{order_id}}, нашли {len(matches)}"
    )


def test_admin_orders_detail_requires_authorization(admin_feed_client) -> None:
    """5.2 — без Authorization header → 401."""
    response = admin_feed_client.get(f"/api/v1/admin/orders/{uuid.uuid4()}")
    assert response.status_code == 401


def test_admin_orders_detail_rejects_customer(
    admin_feed_client, customer_headers
) -> None:
    """5.3 — customer → 403 (INV-010)."""
    response = admin_feed_client.get(
        f"/api/v1/admin/orders/{uuid.uuid4()}",
        headers=customer_headers,
    )
    assert response.status_code == 403


def test_admin_orders_detail_returns_other_users_order(
    admin_feed_client, admin_headers, db_session
) -> None:
    """5.4 — админ видит заказ другого пользователя."""
    user_b = make_user(db_session)
    db_session.commit()

    seed = seed_orders_across_statuses(
        db_session,
        user=user_b,
        counts={(OrderStatus.PREPARING, OrderType.PICKUP): 1},
    )
    [order_id] = seed.order_ids_by_bucket[(OrderStatus.PREPARING, OrderType.PICKUP)]

    response = admin_feed_client.get(
        f"/api/v1/admin/orders/{order_id}", headers=admin_headers
    )
    assert response.status_code == 200

    body = response.json()
    assert body["id"] == str(order_id)
    assert body["user_id"] == str(user_b.id)


def test_admin_orders_detail_barista_sees_other_users_order(
    admin_feed_client, barista_headers, db_session
) -> None:
    """5.5 — бариста тоже видит чужой заказ."""
    user_b = make_user(db_session)
    db_session.commit()

    seed = seed_orders_across_statuses(
        db_session,
        user=user_b,
        counts={(OrderStatus.PREPARING, OrderType.PICKUP): 1},
    )
    [order_id] = seed.order_ids_by_bucket[(OrderStatus.PREPARING, OrderType.PICKUP)]

    response = admin_feed_client.get(
        f"/api/v1/admin/orders/{order_id}", headers=barista_headers
    )
    assert response.status_code == 200
    assert response.json()["user_id"] == str(user_b.id)


def test_admin_orders_detail_returns_404_on_unknown_id(
    admin_feed_client, admin_headers
) -> None:
    """5.6 — неизвестный order_id → 404."""
    response = admin_feed_client.get(
        f"/api/v1/admin/orders/{uuid.uuid4()}", headers=admin_headers
    )
    assert response.status_code == 404
