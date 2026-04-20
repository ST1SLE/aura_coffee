"""RED: тесты staff-scoped листинга заказов (admin-orders-api, PDD §4.5, INV-010).

Все импорты target-символов (list_orders_for_staff / router admin_orders)
выполняются ВНУТРИ тел тестов: в RED-фазе они отсутствуют и import на уровне
модуля сорвал бы сборку файла.

БД-тесты требуют PostgreSQL (db_session фикстура skip-ает на sqlite).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import fakeredis
import pytest
from fastapi.testclient import TestClient

from core_api.main import app
from shared.enums import OrderStatus, OrderType
from tests._factories.orders import make_user, seed_orders_across_statuses


# ---------------------------------------------------------------------------
# Fixtures: TestClient с реальной PG-сессией (зеркалит test_route_order_history.py)
# ---------------------------------------------------------------------------


@pytest.fixture
def admin_feed_client(db_session):
    """TestClient, у которого get_session/get_db указывают на db_session."""

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
# 2.x — list_orders_for_staff service tests
# ===========================================================================


def test_list_orders_for_staff_symbol_absent() -> None:
    """2.1 — символ list_orders_for_staff должен существовать после GREEN."""
    from core_api.services.order_history import list_orders_for_staff  # noqa: F401

    assert callable(list_orders_for_staff)


def test_list_orders_for_staff_active_excludes_finalized(db_session) -> None:
    """2.2 — status_filter='active' не возвращает COMPLETED/CANCELLED."""
    from core_api.services.order_history import list_orders_for_staff

    user_a = make_user(db_session)
    user_b = make_user(db_session)
    db_session.commit()

    seed_orders_across_statuses(
        db_session,
        user=user_a,
        counts={
            (OrderStatus.CREATED, OrderType.PICKUP): 1,
            (OrderStatus.PAID, OrderType.PICKUP): 1,
            (OrderStatus.PREPARING, OrderType.PICKUP): 1,
            (OrderStatus.READY, OrderType.PICKUP): 1,
            (OrderStatus.COMPLETED, OrderType.PICKUP): 1,
        },
    )
    seed_orders_across_statuses(
        db_session,
        user=user_b,
        counts={
            (OrderStatus.IN_DELIVERY, OrderType.DELIVERY): 1,
            (OrderStatus.CANCELLED, OrderType.DELIVERY): 1,
        },
    )

    result = list_orders_for_staff(
        status_filter="active",
        type_filter=None,
        page=1,
        per_page=50,
        db_session=db_session,
    )

    statuses = {row.status for row in result.orders}
    assert statuses == {
        OrderStatus.CREATED,
        OrderStatus.PAID,
        OrderStatus.PREPARING,
        OrderStatus.READY,
        OrderStatus.IN_DELIVERY,
    }
    assert OrderStatus.COMPLETED not in statuses
    assert OrderStatus.CANCELLED not in statuses
    assert result.total_count == 5


def test_list_orders_for_staff_explicit_status_filters_exact(db_session) -> None:
    """2.3 — status_filter=PREPARING → только PREPARING."""
    from core_api.services.order_history import list_orders_for_staff

    user = make_user(db_session)
    db_session.commit()

    seed_orders_across_statuses(
        db_session,
        user=user,
        counts={
            (OrderStatus.CREATED, OrderType.PICKUP): 2,
            (OrderStatus.PREPARING, OrderType.PICKUP): 3,
            (OrderStatus.COMPLETED, OrderType.PICKUP): 1,
        },
    )

    result = list_orders_for_staff(
        status_filter=OrderStatus.PREPARING,
        type_filter=None,
        page=1,
        per_page=50,
        db_session=db_session,
    )

    assert result.total_count == 3
    assert all(row.status == OrderStatus.PREPARING for row in result.orders)


def test_list_orders_for_staff_type_filter_combines_with_status(db_session) -> None:
    """2.4 — status + type фильтры AND-объединены."""
    from core_api.services.order_history import list_orders_for_staff

    user = make_user(db_session)
    db_session.commit()

    seed_orders_across_statuses(
        db_session,
        user=user,
        counts={
            (OrderStatus.PREPARING, OrderType.PICKUP): 2,
            (OrderStatus.PREPARING, OrderType.DELIVERY): 3,
            (OrderStatus.READY, OrderType.DELIVERY): 1,
        },
    )

    result = list_orders_for_staff(
        status_filter=OrderStatus.PREPARING,
        type_filter=OrderType.DELIVERY,
        page=1,
        per_page=50,
        db_session=db_session,
    )

    assert result.total_count == 3
    for row in result.orders:
        assert row.status == OrderStatus.PREPARING
        assert row.type == OrderType.DELIVERY


def test_list_orders_for_staff_active_orders_by_created_at_desc(db_session) -> None:
    """2.5 — active-фид отсортирован created_at DESC."""
    from core_api.services.order_history import list_orders_for_staff

    user = make_user(db_session)
    db_session.commit()

    seed = seed_orders_across_statuses(
        db_session,
        user=user,
        counts={(OrderStatus.PREPARING, OrderType.PICKUP): 3},
        base_time=datetime(2026, 4, 1, 12, 0, tzinfo=UTC),
        step=timedelta(minutes=5),
    )
    ids_asc = seed.order_ids_by_bucket[(OrderStatus.PREPARING, OrderType.PICKUP)]

    result = list_orders_for_staff(
        status_filter="active",
        type_filter=None,
        page=1,
        per_page=50,
        db_session=db_session,
    )

    returned_ids = [row.id for row in result.orders]
    assert returned_ids == list(reversed(ids_asc)), "ожидалось DESC по created_at"


def test_list_orders_for_staff_finalized_orders_by_updated_at_desc(db_session) -> None:
    """2.6 — finalized-фид отсортирован updated_at DESC, даже если created_at в обратном порядке."""
    from core_api.services.order_history import list_orders_for_staff
    from shared.models.order import Order

    user = make_user(db_session)
    db_session.commit()

    # Сеем 3 CANCELLED заказа с created_at T1<T2<T3
    seed = seed_orders_across_statuses(
        db_session,
        user=user,
        counts={(OrderStatus.CANCELLED, OrderType.PICKUP): 3},
        base_time=datetime(2026, 4, 1, 12, 0, tzinfo=UTC),
        step=timedelta(minutes=10),
    )
    ids_by_created_asc = seed.order_ids_by_bucket[
        (OrderStatus.CANCELLED, OrderType.PICKUP)
    ]

    # updated_at перезаписываем в ОБРАТНОМ порядке:
    # самый старый по created_at получает самый свежий updated_at,
    # так что сортировка по updated_at DESC должна дать ids_by_created_asc.
    base_updated = datetime(2026, 4, 2, 9, 0, tzinfo=UTC)
    for idx, oid in enumerate(ids_by_created_asc):
        db_session.query(Order).filter(Order.id == oid).update(
            {Order.updated_at: base_updated + timedelta(minutes=10 * (3 - idx))}
        )
    db_session.commit()

    result = list_orders_for_staff(
        status_filter=OrderStatus.CANCELLED,
        type_filter=None,
        page=1,
        per_page=50,
        db_session=db_session,
    )

    returned_ids = [row.id for row in result.orders]
    # Самый свежий updated_at — у первого по created_at (idx=0).
    assert returned_ids == list(ids_by_created_asc), "ожидалось DESC по updated_at"


def test_list_orders_for_staff_pagination_slice_and_total(db_session) -> None:
    """2.7 — page=2, per_page=10 → rows 11..20, total_count=25."""
    from core_api.services.order_history import list_orders_for_staff

    user = make_user(db_session)
    db_session.commit()

    seed = seed_orders_across_statuses(
        db_session,
        user=user,
        counts={(OrderStatus.PREPARING, OrderType.PICKUP): 25},
        base_time=datetime(2026, 4, 1, 12, 0, tzinfo=UTC),
        step=timedelta(minutes=1),
    )
    ids_asc = seed.order_ids_by_bucket[(OrderStatus.PREPARING, OrderType.PICKUP)]
    ids_desc = list(reversed(ids_asc))

    result = list_orders_for_staff(
        status_filter="active",
        type_filter=None,
        page=2,
        per_page=10,
        db_session=db_session,
    )

    assert result.total_count == 25
    returned_ids = [row.id for row in result.orders]
    assert returned_ids == ids_desc[10:20]
    assert result.page == 2
    assert result.per_page == 10


def test_list_orders_for_staff_sees_all_users(db_session) -> None:
    """2.8 — персонал видит заказы всех пользователей."""
    from core_api.services.order_history import list_orders_for_staff

    user_a = make_user(db_session)
    user_b = make_user(db_session)
    db_session.commit()

    seed_orders_across_statuses(
        db_session,
        user=user_a,
        counts={(OrderStatus.PREPARING, OrderType.PICKUP): 2},
    )
    seed_orders_across_statuses(
        db_session,
        user=user_b,
        counts={(OrderStatus.PREPARING, OrderType.DELIVERY): 3},
    )

    result = list_orders_for_staff(
        status_filter="active",
        type_filter=None,
        page=1,
        per_page=50,
        db_session=db_session,
    )

    assert result.total_count == 5
    user_ids = {row.user_id for row in result.orders}
    assert user_ids == {user_a.id, user_b.id}


# ===========================================================================
# 4.x — GET /api/v1/admin/orders router tests
# ===========================================================================


def test_admin_orders_list_route_not_registered() -> None:
    """4.1 — после GREEN маршрут GET /api/v1/admin/orders регистрируется ровно один раз."""
    matches = []
    for route in app.routes:
        methods = getattr(route, "methods", set()) or set()
        path = getattr(route, "path", "")
        if "GET" in methods and path == "/api/v1/admin/orders":
            matches.append(route)

    assert len(matches) == 1, (
        f"Ожидался ровно 1 GET /api/v1/admin/orders, нашли {len(matches)}"
    )


def test_admin_orders_list_requires_authorization(admin_feed_client) -> None:
    """4.2 — без Authorization header → 401."""
    response = admin_feed_client.get("/api/v1/admin/orders")
    assert response.status_code == 401


def test_admin_orders_list_rejects_customer(admin_feed_client, customer_headers) -> None:
    """4.3 — customer → 403 (INV-010)."""
    response = admin_feed_client.get("/api/v1/admin/orders", headers=customer_headers)
    assert response.status_code == 403


def test_admin_orders_list_rejects_courier(admin_feed_client, courier_headers) -> None:
    """4.4 — courier → 403 (INV-010)."""
    response = admin_feed_client.get("/api/v1/admin/orders", headers=courier_headers)
    assert response.status_code == 403


def test_admin_orders_list_rejects_per_page_over_100(
    admin_feed_client, admin_headers
) -> None:
    """4.5 — per_page=101 → 422 (FastAPI Query le=100)."""
    response = admin_feed_client.get(
        "/api/v1/admin/orders?per_page=101", headers=admin_headers
    )
    assert response.status_code == 422


def test_admin_orders_list_defaults_to_active_filter(
    admin_feed_client, admin_headers, db_session
) -> None:
    """4.6 — дефолтный фильтр 'active' исключает COMPLETED/CANCELLED."""
    user = make_user(db_session)
    db_session.commit()

    seed_orders_across_statuses(
        db_session,
        user=user,
        counts={
            (OrderStatus.PREPARING, OrderType.PICKUP): 2,
            (OrderStatus.COMPLETED, OrderType.PICKUP): 1,
            (OrderStatus.CANCELLED, OrderType.PICKUP): 1,
        },
    )

    response = admin_feed_client.get("/api/v1/admin/orders", headers=admin_headers)
    assert response.status_code == 200

    body = response.json()
    statuses = {row["status"] for row in body["orders"]}
    assert OrderStatus.COMPLETED.value not in statuses
    assert OrderStatus.CANCELLED.value not in statuses
    assert body["total_count"] == 2


def test_admin_orders_list_type_filter(
    admin_feed_client, admin_headers, db_session
) -> None:
    """4.7 — ?type=delivery → только delivery."""
    user = make_user(db_session)
    db_session.commit()

    seed_orders_across_statuses(
        db_session,
        user=user,
        counts={
            (OrderStatus.PREPARING, OrderType.PICKUP): 2,
            (OrderStatus.PREPARING, OrderType.DELIVERY): 3,
        },
    )

    response = admin_feed_client.get(
        "/api/v1/admin/orders?type=delivery", headers=admin_headers
    )
    assert response.status_code == 200

    body = response.json()
    assert body["total_count"] == 3
    for row in body["orders"]:
        assert row["type"] == OrderType.DELIVERY.value


def test_admin_orders_list_barista_same_access_as_admin(
    admin_feed_client, admin_headers, barista_headers, db_session
) -> None:
    """4.8 — бариста видит тот же payload, что и админ."""
    user = make_user(db_session)
    db_session.commit()

    seed_orders_across_statuses(
        db_session,
        user=user,
        counts={(OrderStatus.PREPARING, OrderType.PICKUP): 2},
    )

    admin_response = admin_feed_client.get(
        "/api/v1/admin/orders", headers=admin_headers
    )
    barista_response = admin_feed_client.get(
        "/api/v1/admin/orders", headers=barista_headers
    )

    assert admin_response.status_code == 200
    assert barista_response.status_code == 200
    assert barista_response.json()["total_count"] == admin_response.json()["total_count"]


def test_admin_orders_list_sees_multiple_users_orders(
    admin_feed_client, admin_headers, db_session
) -> None:
    """4.9 — staff видит заказы всех клиентов."""
    user_a = make_user(db_session)
    user_b = make_user(db_session)
    db_session.commit()

    seed_orders_across_statuses(
        db_session,
        user=user_a,
        counts={(OrderStatus.PREPARING, OrderType.PICKUP): 2},
    )
    seed_orders_across_statuses(
        db_session,
        user=user_b,
        counts={(OrderStatus.PREPARING, OrderType.DELIVERY): 3},
    )

    response = admin_feed_client.get("/api/v1/admin/orders", headers=admin_headers)
    assert response.status_code == 200

    body = response.json()
    assert body["total_count"] == 5
    user_ids = {row["user_id"] for row in body["orders"]}
    assert user_ids == {str(user_a.id), str(user_b.id)}
