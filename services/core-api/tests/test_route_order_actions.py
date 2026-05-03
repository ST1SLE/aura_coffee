"""RED: тесты HTTP-эндпоинтов для staff-actions над заказом.

Эндпоинты:
  PATCH /api/v1/orders/{order_id}/status
  POST  /api/v1/orders/{order_id}/cancel

Роутер `core_api.routers.order_actions` и соответствующие RBAC-правила ещё
не существуют — все тесты ДОЛЖНЫ падать в RED-цикле (ModuleNotFoundError,
403/404 из-за отсутствия маршрута в RBAC-матрице, или AttributeError на
мок-пойнтах).
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

_JWT_SECRET = "aura-coffee-tests-jwt-secret-0001"


def _make_token(role: str, user_id: uuid.UUID | None = None) -> str:
    from datetime import UTC, datetime, timedelta

    import jwt as pyjwt

    uid = user_id or uuid.uuid4()
    payload = {
        "sub": str(uid),
        "role": role,
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(seconds=900),
    }
    return pyjwt.encode(payload, _JWT_SECRET, algorithm="HS256")


def _auth(role: str, user_id: uuid.UUID | None = None) -> dict[str, str]:
    return {"Authorization": f"Bearer {_make_token(role, user_id)}"}


def _patch_jwt():
    """Патч JWT-настроек для RBAC middleware."""
    return patch("core_api.services.auth.settings", **{
        "jwt_secret_key": _JWT_SECRET,
        "jwt_algorithm": "HS256",
        "access_token_ttl": 900,
    })


@pytest.fixture
def client():
    from core_api.main import app

    with _patch_jwt(), TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# 3.1 — import probe
# ---------------------------------------------------------------------------

def test_order_actions_router_module_exists() -> None:
    from core_api.routers.order_actions import router  # noqa: F401


# ---------------------------------------------------------------------------
# 3.2 — main.py регистрирует роутер
# ---------------------------------------------------------------------------

def test_main_registers_order_actions_router() -> None:
    from core_api.main import app

    patterns = {(route.path, tuple(sorted(route.methods))) for route in app.router.routes if hasattr(route, "methods")}

    has_status = any(
        path == "/api/v1/orders/{order_id}/status" and "PATCH" in methods
        for path, methods in patterns
    )
    has_cancel = any(
        path == "/api/v1/orders/{order_id}/cancel" and "POST" in methods
        for path, methods in patterns
    )
    assert has_status, f"Маршрут PATCH /api/v1/orders/{{order_id}}/status не зарегистрирован. Routes: {patterns}"
    assert has_cancel, f"Маршрут POST /api/v1/orders/{{order_id}}/cancel не зарегистрирован. Routes: {patterns}"


# ---------------------------------------------------------------------------
# Status endpoint — auth & RBAC
# ---------------------------------------------------------------------------

def test_status_endpoint_requires_auth(client: TestClient) -> None:
    resp = client.patch(
        f"/api/v1/orders/{uuid.uuid4()}/status",
        json={"new_status": "preparing"},
    )
    assert resp.status_code == 401


def test_status_endpoint_rejects_customer_with_403(client: TestClient) -> None:
    resp = client.patch(
        f"/api/v1/orders/{uuid.uuid4()}/status",
        headers=_auth("customer"),
        json={"new_status": "preparing"},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Status endpoint — happy path via mocked service
# ---------------------------------------------------------------------------

def _fake_order_response(order_id: uuid.UUID, status_val: str = "preparing") -> dict:
    from datetime import UTC, datetime

    return {
        "id": str(order_id),
        "status": status_val,
        "type": "pickup",
        "items": [],
        "subtotal": 0,
        "discount_amount": 0,
        "points_used": 0,
        "delivery_fee": 0,
        "total": 0,
        "estimated_accrual": 0,
        "confirmation_url": None,
        "requested_time": None,
        "estimated_ready_at": None,
        "cancelled_by": None,
        "cancelled_at": None,
        "created_at": datetime.now(UTC).isoformat(),
    }


def test_status_endpoint_barista_calls_service(client: TestClient) -> None:
    import core_api.routers.order_actions as router_mod
    from shared.enums import OrderStatus

    order_id = uuid.uuid4()
    stub = MagicMock(return_value=_fake_order_response(order_id, "preparing"))
    with patch.object(router_mod, "transition_order", stub):
        resp = client.patch(
            f"/api/v1/orders/{order_id}/status",
            headers=_auth("barista"),
            json={"new_status": "preparing"},
        )

    assert resp.status_code == 200, resp.text
    assert stub.call_count == 1
    # Проверим, что new_status пришёл как OrderStatus.PREPARING и actor_role="barista"
    call = stub.call_args
    all_args = list(call.args) + list(call.kwargs.values())
    assert OrderStatus.PREPARING in all_args or "preparing" in [
        getattr(x, "value", x) for x in all_args
    ]
    assert "barista" in [str(x) for x in all_args]


def test_status_endpoint_rejects_invalid_new_status_with_422(client: TestClient) -> None:
    import core_api.routers.order_actions as router_mod

    stub = MagicMock()
    with patch.object(router_mod, "transition_order", stub):
        resp = client.patch(
            f"/api/v1/orders/{uuid.uuid4()}/status",
            headers=_auth("admin"),
            json={"new_status": "not-a-status"},
        )
    assert resp.status_code == 422
    assert stub.call_count == 0


def test_status_endpoint_forwards_transition_error_as_409(client: TestClient) -> None:
    import core_api.routers.order_actions as router_mod
    from core_api.services.order_lifecycle import OrderTransitionError

    stub = MagicMock(side_effect=OrderTransitionError(reason="forbidden_transition"))
    with patch.object(router_mod, "transition_order", stub):
        resp = client.patch(
            f"/api/v1/orders/{uuid.uuid4()}/status",
            headers=_auth("admin"),
            json={"new_status": "preparing"},
        )
    assert resp.status_code == 409
    assert "forbidden_transition" in resp.text


def test_status_endpoint_returns_404_for_not_found(client: TestClient) -> None:
    import core_api.routers.order_actions as router_mod
    from core_api.services.order_lifecycle import OrderTransitionError

    stub = MagicMock(side_effect=OrderTransitionError(reason="order_not_found"))
    with patch.object(router_mod, "transition_order", stub):
        resp = client.patch(
            f"/api/v1/orders/{uuid.uuid4()}/status",
            headers=_auth("admin"),
            json={"new_status": "preparing"},
        )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Cancel endpoint — customer own-order + RBAC
# ---------------------------------------------------------------------------

def _seed_order_for_user(user_id: uuid.UUID) -> uuid.UUID:
    from core_api.deps.database import SessionLocal
    from shared.enums import OrderStatus, OrderType, UserStatus
    from shared.models import LoyaltyAccount, Order, User

    with SessionLocal() as s:
        u = User(id=user_id, phone_hash=uuid.uuid4().hex, status=UserStatus.ACTIVE)
        s.add(u)
        s.flush()
        s.add(LoyaltyAccount(user_id=u.id, balance=0))
        order = Order(
            user_id=u.id,
            status=OrderStatus.PAID,
            type=OrderType.PICKUP,
            subtotal=0,
            discount_amount=0,
            points_used=0,
            delivery_fee=0,
            total=0,
            estimated_accrual=0,
        )
        s.add(order)
        s.commit()
        return order.id


def test_cancel_endpoint_customer_own_order_happy_path(client: TestClient) -> None:
    import core_api.routers.order_actions as router_mod

    user_id = uuid.uuid4()
    order_id = _seed_order_for_user(user_id)

    stub = MagicMock(return_value=_fake_order_response(order_id, "cancelled"))
    with patch.object(router_mod, "cancel_order", stub):
        resp = client.post(
            f"/api/v1/orders/{order_id}/cancel",
            headers=_auth("customer", user_id=user_id),
            json={"reason": "changed my mind"},
        )

    assert resp.status_code == 200, resp.text
    assert stub.call_count == 1
    all_args = list(stub.call_args.args) + list(stub.call_args.kwargs.values())
    assert "customer" in [str(x) for x in all_args]


def test_cancel_endpoint_customer_foreign_order_403(client: TestClient) -> None:
    """Customer B пытается отменить заказ customer A → 403, service не вызван."""
    import core_api.routers.order_actions as router_mod

    owner_id = uuid.uuid4()
    order_id = _seed_order_for_user(owner_id)

    stranger_id = uuid.uuid4()
    stub = MagicMock()
    with patch.object(router_mod, "cancel_order", stub):
        resp = client.post(
            f"/api/v1/orders/{order_id}/cancel",
            headers=_auth("customer", user_id=stranger_id),
            json={"reason": None},
        )

    assert resp.status_code == 403
    assert stub.call_count == 0


def test_cancel_endpoint_admin_allowed(client: TestClient) -> None:
    import core_api.routers.order_actions as router_mod

    order_id = _seed_order_for_user(uuid.uuid4())

    stub = MagicMock(return_value=_fake_order_response(order_id, "cancelled"))
    with patch.object(router_mod, "cancel_order", stub):
        resp = client.post(
            f"/api/v1/orders/{order_id}/cancel",
            headers=_auth("admin"),
            json={"reason": "admin decision"},
        )
    assert resp.status_code == 200
    all_args = list(stub.call_args.args) + list(stub.call_args.kwargs.values())
    assert "admin" in [str(x) for x in all_args]


@pytest.mark.parametrize("role", ["barista", "courier"])
def test_cancel_endpoint_rejects_barista_and_courier_with_403(
    client: TestClient, role: str
) -> None:
    """INV-010: только CUSTOMER и ADMIN могут вызывать cancel."""
    resp = client.post(
        f"/api/v1/orders/{uuid.uuid4()}/cancel",
        headers=_auth(role),
        json={"reason": None},
    )
    assert resp.status_code == 403


def test_cancel_endpoint_forwards_cancel_error_as_409(client: TestClient) -> None:
    import core_api.routers.order_actions as router_mod
    from core_api.services.order_cancel import OrderCancelError

    order_id = _seed_order_for_user(uuid.uuid4())
    stub = MagicMock(side_effect=OrderCancelError(reason="customer_cannot_cancel_in_this_status"))
    with patch.object(router_mod, "cancel_order", stub):
        resp = client.post(
            f"/api/v1/orders/{order_id}/cancel",
            headers=_auth("admin"),
            json={"reason": None},
        )
    assert resp.status_code == 409
    assert "customer_cannot_cancel_in_this_status" in resp.text


def test_cancel_endpoint_returns_404_for_not_found(client: TestClient) -> None:
    import core_api.routers.order_actions as router_mod
    from core_api.services.order_cancel import OrderCancelError

    stub = MagicMock(side_effect=OrderCancelError(reason="order_not_found"))
    with patch.object(router_mod, "cancel_order", stub):
        resp = client.post(
            f"/api/v1/orders/{uuid.uuid4()}/cancel",
            headers=_auth("admin"),
            json={"reason": None},
        )
    assert resp.status_code == 404
