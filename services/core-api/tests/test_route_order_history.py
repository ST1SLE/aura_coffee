"""RED: тесты HTTP-эндпоинтов order-history и order-repeat (PDD §7.7).

GET /api/v1/orders — пагинированная история своих заказов.
POST /api/v1/orders/{order_id}/repeat — повтор заказа из истории в корзину.

Все тесты должны провалиться в RED-фазе: либо 404 (route не зарегистрирован),
либо ImportError на сервисах. После GREEN-фазы все тесты должны пройти.
"""
from __future__ import annotations

from unittest.mock import patch

import fakeredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from core_api.main import app
from shared.enums import SizeLabel
from tests._factories.menu import (
    make_category,
    make_menu_item,
    make_modifier,
    make_size_option,
)
from tests._factories.orders import (
    HistoryItemSpec,
    make_user,
    seed_history_order,
    seed_n_orders_for_user,
)
from tests._helpers.jwt import auth_headers_for_user, make_jwt_for_user


# ---------------------------------------------------------------------------
# Фикстуры: TestClient с fake Redis и реальной (PG) БД-сессией
# ---------------------------------------------------------------------------

@pytest.fixture
def cart_redis_client():
    """FakeRedis, подменённый в deps.redis.get_redis."""
    fake = fakeredis.FakeRedis()

    def _override():
        yield fake

    with patch("core_api.deps.redis.get_redis", side_effect=_override):
        yield fake
    fake.flushall()


@pytest.fixture
def db_client(cart_redis_client, db_session):
    """TestClient с fakeredis и реальной PG-сессией (скип на sqlite)."""
    def _override_redis():
        yield cart_redis_client

    def _override_db():
        yield db_session

    with (
        patch("core_api.deps.redis.get_redis", side_effect=_override_redis),
        patch("core_api.deps.database.get_session", side_effect=_override_db),
        patch("core_api.deps.database.get_db", side_effect=_override_db),
    ):
        with TestClient(app) as c:
            yield c


# ---------------------------------------------------------------------------
# 4.1 — GET /api/v1/orders не зарегистрирован (RED-маркер)
# ---------------------------------------------------------------------------

def test_get_orders_route_not_registered() -> None:
    """В RED-фазе GET /api/v1/orders отсутствует в app.routes."""
    matches = []
    for route in app.routes:
        methods = getattr(route, "methods", set()) or set()
        path = getattr(route, "path", "")
        if "GET" in methods and path == "/api/v1/orders":
            matches.append(route)

    # После GREEN — ровно 1 matching route.
    assert len(matches) == 1, (
        f"Ожидался ровно 1 GET /api/v1/orders, нашли {len(matches)}"
    )


# ---------------------------------------------------------------------------
# 4.2 — 401 без Authorization header
# ---------------------------------------------------------------------------

def test_get_orders_requires_authorization(db_client) -> None:
    response = db_client.get("/api/v1/orders")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# 4.3 — 403 для non-customer роли
# ---------------------------------------------------------------------------

def test_get_orders_forbids_non_customer_role(db_client, barista_headers) -> None:
    response = db_client.get("/api/v1/orders", headers=barista_headers)
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# 4.4 — 422 при per_page > 50
# ---------------------------------------------------------------------------

def test_get_orders_rejects_per_page_over_50(db_client, db_session) -> None:
    user = make_user(db_session)
    db_session.commit()
    headers = auth_headers_for_user(user.id)

    response = db_client.get("/api/v1/orders?per_page=51", headers=headers)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# 4.5 — caller видит только свои заказы
# ---------------------------------------------------------------------------

def test_get_orders_returns_only_own_orders(db_client, db_session) -> None:
    user_a = make_user(db_session)
    user_b = make_user(db_session)
    db_session.commit()

    seed_n_orders_for_user(db_session, user_a, count=3)
    seed_n_orders_for_user(db_session, user_b, count=2)

    headers = auth_headers_for_user(user_a.id)
    response = db_client.get("/api/v1/orders", headers=headers)
    assert response.status_code == 200

    body = response.json()
    assert body["total_count"] == 3
    for order in body["orders"]:
        assert order["user_id"] == str(user_a.id)


# ---------------------------------------------------------------------------
# 4.6 — пустая история → 200, пустой список
# ---------------------------------------------------------------------------

def test_get_orders_empty_returns_200_with_empty_list(db_client, db_session) -> None:
    user = make_user(db_session)
    db_session.commit()

    headers = auth_headers_for_user(user.id)
    response = db_client.get("/api/v1/orders", headers=headers)
    assert response.status_code == 200

    body = response.json()
    assert body["orders"] == []
    assert body["total_count"] == 0
    assert body["page"] == 1
    assert body["per_page"] == 20


# ---------------------------------------------------------------------------
# 4.7 — POST /repeat не зарегистрирован (RED-маркер)
# ---------------------------------------------------------------------------

def test_post_repeat_route_not_registered() -> None:
    matches = []
    for route in app.routes:
        methods = getattr(route, "methods", set()) or set()
        path = getattr(route, "path", "")
        if "POST" in methods and path == "/api/v1/orders/{order_id}/repeat":
            matches.append(route)

    assert len(matches) == 1, (
        f"Ожидался ровно 1 POST /api/v1/orders/{{order_id}}/repeat, нашли {len(matches)}"
    )


# ---------------------------------------------------------------------------
# 4.8 — 401 без Authorization header
# ---------------------------------------------------------------------------

def test_post_repeat_requires_authorization(db_client) -> None:
    import uuid as _uuid

    response = db_client.post(f"/api/v1/orders/{_uuid.uuid4()}/repeat")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# 4.9 — 403 для non-customer роли
# ---------------------------------------------------------------------------

def test_post_repeat_forbids_non_customer_role(db_client, barista_headers) -> None:
    import uuid as _uuid

    response = db_client.post(
        f"/api/v1/orders/{_uuid.uuid4()}/repeat",
        headers=barista_headers,
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# 4.10 — 404 на чужой заказ
# ---------------------------------------------------------------------------

def test_post_repeat_returns_404_for_other_users_order(db_client, db_session) -> None:
    user_a = make_user(db_session)
    user_b = make_user(db_session)
    db_session.commit()

    cat = make_category(db_session)
    mi = make_menu_item(db_session, cat, base_price=15000)
    seed_b = seed_history_order(
        db_session, user=user_b, items=[HistoryItemSpec(menu_item=mi)]
    )

    headers = auth_headers_for_user(user_a.id)
    response = db_client.post(
        f"/api/v1/orders/{seed_b.order_id}/repeat",
        headers=headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "order_not_found"


# ---------------------------------------------------------------------------
# 4.11 — success: корзина заполняется
# ---------------------------------------------------------------------------

def test_post_repeat_success_populates_cart_and_returns_200(
    db_client, db_session, cart_redis_client
) -> None:
    import json

    user = make_user(db_session)
    cat = make_category(db_session)
    mi = make_menu_item(db_session, cat, base_price=15000, name_ru="Латте")
    seed = seed_history_order(
        db_session, user=user, items=[HistoryItemSpec(menu_item=mi, quantity=2)]
    )

    headers = auth_headers_for_user(user.id)
    response = db_client.post(
        f"/api/v1/orders/{seed.order_id}/repeat",
        headers=headers,
    )
    assert response.status_code == 200

    body = response.json()
    assert body["added_to_cart"] >= 1
    assert "skipped" in body

    # Redis должен содержать ключ cart:{user_id}
    raw = cart_redis_client.get(f"cart:{user.id}")
    assert raw is not None, "Корзина в Redis не заполнена"
    payload = json.loads(raw)
    assert len(payload.get("items", [])) >= 1


# ---------------------------------------------------------------------------
# 4.12 — 422 когда все позиции недоступны
# ---------------------------------------------------------------------------

def test_post_repeat_all_unavailable_returns_422(db_client, db_session) -> None:
    user = make_user(db_session)
    cat = make_category(db_session)
    mi_stop = make_menu_item(
        db_session, cat, base_price=15000, name_ru="Латте", available=False
    )
    seed = seed_history_order(
        db_session, user=user, items=[HistoryItemSpec(menu_item=mi_stop)]
    )

    headers = auth_headers_for_user(user.id)
    response = db_client.post(
        f"/api/v1/orders/{seed.order_id}/repeat",
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Ни одна позиция из этого заказа сейчас недоступна"


# ---------------------------------------------------------------------------
# 4.13 — repeat не делает auto-checkout
# ---------------------------------------------------------------------------

def test_post_repeat_does_not_auto_checkout(db_client, db_session) -> None:
    user = make_user(db_session)
    cat = make_category(db_session)
    mi = make_menu_item(db_session, cat, base_price=15000)
    seed = seed_history_order(
        db_session, user=user, items=[HistoryItemSpec(menu_item=mi)]
    )

    orders_before = db_session.execute(text("SELECT count(*) FROM orders")).scalar_one()
    payments_before = db_session.execute(text("SELECT count(*) FROM payments")).scalar_one()

    headers = auth_headers_for_user(user.id)
    response = db_client.post(
        f"/api/v1/orders/{seed.order_id}/repeat",
        headers=headers,
    )
    assert response.status_code == 200

    # Откатим/обновим сессию — repeat может commit-ить в свою сессию;
    # count в нашей сессии отражает то, что видно после commit транзакции сервера.
    db_session.expire_all()
    orders_after = db_session.execute(text("SELECT count(*) FROM orders")).scalar_one()
    payments_after = db_session.execute(text("SELECT count(*) FROM payments")).scalar_one()

    assert orders_after == orders_before, "repeat не должен создавать новый Order"
    assert payments_after == payments_before, "repeat не должен создавать новый Payment"


# ---------------------------------------------------------------------------
# 4.14 — single-order detail не дублируется
# ---------------------------------------------------------------------------

def test_single_order_detail_is_not_duplicated() -> None:
    """GET /api/v1/orders/{order_id} — ровно 1 маршрут (owner: order-checkout feature)."""
    matches = []
    for route in app.routes:
        methods = getattr(route, "methods", set()) or set()
        path = getattr(route, "path", "")
        if "GET" in methods and path == "/api/v1/orders/{order_id}":
            matches.append(route)

    assert len(matches) == 1, (
        f"Ожидался ровно 1 GET /api/v1/orders/{{order_id}}, нашли {len(matches)}. "
        f"Либо order-checkout не зарегистрирован, либо order-history дублирует маршрут."
    )
