"""RED: HTTP-тесты курьерского роутера `core_api.routers.courier`.

Покрывают регистрацию маршрутов, запись в RBAC-матрице (только COURIER),
ролевую изоляцию (403 для customer / barista / admin) и прокидывание
доменных ошибок сервиса в HTTP-коды.

Импорты целевых модулей — внутри тестов: в RED-цикле модуля нет.
"""
from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient


def _jwt_secret() -> str:
    """Секрет из env, чтобы совпадал с `settings.jwt_secret_key` в рантайме."""
    return os.environ.get("JWT_SECRET_KEY", "test-secret")


def _make_token(role: str, user_id: uuid.UUID | None = None) -> str:
    uid = user_id or uuid.uuid4()
    payload = {
        "sub": str(uid),
        "role": role,
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(seconds=900),
    }
    return pyjwt.encode(payload, _jwt_secret(), algorithm="HS256")


def _auth(role: str, user_id: uuid.UUID | None = None) -> dict[str, str]:
    return {"Authorization": f"Bearer {_make_token(role, user_id)}"}


@pytest.fixture
def client() -> TestClient:
    from core_api.main import app

    return TestClient(app)


# ---------------------------------------------------------------------------
# 3.1 — import probe
# ---------------------------------------------------------------------------

def test_courier_router_module_exists() -> None:
    from core_api.routers.courier import router  # noqa: F401


# ---------------------------------------------------------------------------
# 3.2 — main.app регистрирует все 5 курьерских маршрутов
# ---------------------------------------------------------------------------

def test_main_registers_courier_router() -> None:
    from core_api.main import app

    patterns = {
        (path, method)
        for route in app.router.routes
        if hasattr(route, "methods") and hasattr(route, "path")
        for path in [route.path]
        for method in route.methods
    }

    expected = {
        ("/api/v1/courier/assignments/available", "GET"),
        ("/api/v1/courier/assignments/mine", "GET"),
        ("/api/v1/courier/assignments/{assignment_id}/take", "POST"),
        ("/api/v1/courier/assignments/{assignment_id}/pickup", "POST"),
        ("/api/v1/courier/assignments/{assignment_id}/deliver", "POST"),
    }
    missing = expected - patterns
    assert not missing, f"Не зарегистрированы маршруты: {missing}"


# ---------------------------------------------------------------------------
# 3.3 — RBAC матрица содержит ровно {COURIER}
# ---------------------------------------------------------------------------

def test_rbac_matrix_has_courier_entries() -> None:
    from core_api.rbac_matrix import COURIER, ROUTE_MATRIX

    expected_paths = [
        ("GET", "/api/v1/courier/assignments/available"),
        ("GET", "/api/v1/courier/assignments/mine"),
        ("POST", "/api/v1/courier/assignments/{assignment_id}/take"),
        ("POST", "/api/v1/courier/assignments/{assignment_id}/pickup"),
        ("POST", "/api/v1/courier/assignments/{assignment_id}/deliver"),
    ]
    for method, path in expected_paths:
        assert (method, path) in ROUTE_MATRIX, (
            f"RBAC matrix missing {method} {path}"
        )
        assert ROUTE_MATRIX[(method, path)] == {COURIER}, (
            f"Expected {{COURIER}} for {method} {path}, "
            f"got {ROUTE_MATRIX[(method, path)]}"
        )


# ---------------------------------------------------------------------------
# 3.4–3.8 — параметризованные RBAC-тесты на 403
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("role", ["customer", "barista", "admin"])
def test_available_endpoint_rejects_non_courier_with_403(
    client: TestClient, role: str
) -> None:
    resp = client.get(
        "/api/v1/courier/assignments/available", headers=_auth(role)
    )
    assert resp.status_code == 403


@pytest.mark.parametrize("role", ["customer", "barista", "admin"])
def test_mine_endpoint_rejects_non_courier_with_403(
    client: TestClient, role: str
) -> None:
    resp = client.get(
        "/api/v1/courier/assignments/mine", headers=_auth(role)
    )
    assert resp.status_code == 403


@pytest.mark.parametrize("role", ["customer", "barista", "admin"])
def test_take_endpoint_rejects_non_courier_with_403(
    client: TestClient, role: str
) -> None:
    resp = client.post(
        f"/api/v1/courier/assignments/{uuid.uuid4()}/take",
        headers=_auth(role),
    )
    assert resp.status_code == 403


@pytest.mark.parametrize("role", ["customer", "barista", "admin"])
def test_pickup_endpoint_rejects_non_courier_with_403(
    client: TestClient, role: str
) -> None:
    resp = client.post(
        f"/api/v1/courier/assignments/{uuid.uuid4()}/pickup",
        headers=_auth(role),
    )
    assert resp.status_code == 403


@pytest.mark.parametrize("role", ["customer", "barista", "admin"])
def test_deliver_endpoint_rejects_non_courier_with_403(
    client: TestClient, role: str
) -> None:
    resp = client.post(
        f"/api/v1/courier/assignments/{uuid.uuid4()}/deliver",
        headers=_auth(role),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 3.9 — take → 409 при AssignmentAlreadyTakenError
# ---------------------------------------------------------------------------

def test_take_endpoint_forwards_already_taken_as_409(client: TestClient) -> None:
    import core_api.routers.courier as router_mod
    from core_api.services.delivery_assignment import AssignmentAlreadyTakenError

    stub = MagicMock(side_effect=AssignmentAlreadyTakenError())
    with patch.object(router_mod, "take_assignment", stub):
        resp = client.post(
            f"/api/v1/courier/assignments/{uuid.uuid4()}/take",
            headers=_auth("courier"),
        )
    assert resp.status_code == 409
    assert "already_taken" in resp.text


# ---------------------------------------------------------------------------
# 3.10 — pickup → 403 при not_owner
# ---------------------------------------------------------------------------

def test_pickup_endpoint_forwards_not_owner_as_403(client: TestClient) -> None:
    import core_api.routers.courier as router_mod
    from core_api.services.delivery_assignment import AssignmentTransitionError

    stub = MagicMock(side_effect=AssignmentTransitionError(reason="not_owner"))
    with patch.object(router_mod, "pickup_assignment", stub):
        resp = client.post(
            f"/api/v1/courier/assignments/{uuid.uuid4()}/pickup",
            headers=_auth("courier"),
        )
    assert resp.status_code == 403
    assert "not_owner" in resp.text


# ---------------------------------------------------------------------------
# 3.11 — deliver → 409 при forbidden_transition
# ---------------------------------------------------------------------------

def test_deliver_endpoint_forwards_forbidden_transition_as_409(
    client: TestClient,
) -> None:
    import core_api.routers.courier as router_mod
    from core_api.services.delivery_assignment import AssignmentTransitionError

    stub = MagicMock(
        side_effect=AssignmentTransitionError(reason="forbidden_transition")
    )
    with patch.object(router_mod, "deliver_assignment", stub):
        resp = client.post(
            f"/api/v1/courier/assignments/{uuid.uuid4()}/deliver",
            headers=_auth("courier"),
        )
    assert resp.status_code == 409
    assert "forbidden_transition" in resp.text


# ---------------------------------------------------------------------------
# 3.12 — assignment_not_found → 404
# ---------------------------------------------------------------------------

def test_assignment_not_found_returns_404(client: TestClient) -> None:
    import core_api.routers.courier as router_mod
    from core_api.services.delivery_assignment import AssignmentTransitionError

    stub = MagicMock(
        side_effect=AssignmentTransitionError(reason="assignment_not_found")
    )
    with patch.object(router_mod, "take_assignment", stub):
        resp = client.post(
            f"/api/v1/courier/assignments/{uuid.uuid4()}/take",
            headers=_auth("courier"),
        )
    assert resp.status_code == 404
    assert "assignment_not_found" in resp.text


# ---------------------------------------------------------------------------
# 3.13 — available → JSON-список верхнего уровня
# ---------------------------------------------------------------------------

def test_available_endpoint_returns_json_list(client: TestClient) -> None:
    import core_api.routers.courier as router_mod

    fake_row = {
        "id": str(uuid.uuid4()),
        "order_id": str(uuid.uuid4()),
        "total": 50000,
        "requested_time": None,
        "delivery_address_snapshot": None,
    }
    stub = MagicMock(return_value=[fake_row])
    with patch.object(router_mod, "list_available_for_courier", stub):
        resp = client.get(
            "/api/v1/courier/assignments/available",
            headers=_auth("courier"),
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, list), f"Expected top-level list, got: {type(body)}"
    assert len(body) == 1
