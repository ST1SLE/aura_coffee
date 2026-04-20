"""RED: тесты adjust_loyalty сервиса + route POST /api/v1/admin/users/{id}/loyalty/adjust.

INV-004: баланс + транзакция в одной БД-транзакции с SELECT … FOR UPDATE.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import fakeredis
import pytest
from fastapi.testclient import TestClient

from core_api.main import app
from shared.enums import LoyaltyTransactionType, UserStatus
from shared.models.loyalty_account import LoyaltyAccount
from shared.models.loyalty_transaction import LoyaltyTransaction
from tests._factories.admin_users import (
    make_user_with_loyalty_and_profile,
    make_user_with_profile,
)


@pytest.fixture
def admin_users_client(db_session):
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
# 6.x — adjust_loyalty service tests
# ===========================================================================


def test_adjust_loyalty_symbol_absent() -> None:
    """6.1 — символ adjust_loyalty должен существовать после GREEN."""
    from core_api.services.admin_users import adjust_loyalty  # noqa: F401

    assert callable(adjust_loyalty)


def test_insufficient_balance_error_symbol_absent() -> None:
    """6.2 — domain error InsufficientBalanceError должен экспортироваться."""
    from core_api.services.admin_users import InsufficientBalanceError  # noqa: F401

    assert issubclass(InsufficientBalanceError, Exception)


def test_adjust_loyalty_positive_delta_credits_and_creates_admin_adjustment_transaction(
    db_session,
) -> None:
    """6.3 — positive delta → balance растёт, запись LoyaltyTransaction(ADMIN_ADJUSTMENT)."""
    from core_api.services.admin_users import adjust_loyalty

    user, _ = make_user_with_loyalty_and_profile(
        db_session, balance=100, status=UserStatus.ACTIVE, display_name="U"
    )
    db_session.commit()

    response = adjust_loyalty(
        db=db_session, user_id=user.id, delta=500, reason="credit"
    )

    assert response.new_balance == 600
    assert response.delta == 500

    account = db_session.get(LoyaltyAccount, user.id)
    assert account.balance == 600

    txs = (
        db_session.query(LoyaltyTransaction)
        .filter(LoyaltyTransaction.user_id == user.id)
        .all()
    )
    assert len(txs) == 1
    tx = txs[0]
    assert tx.type == LoyaltyTransactionType.ADMIN_ADJUSTMENT
    assert tx.amount == 500
    assert tx.balance_after == 600
    assert tx.description == "credit"
    assert tx.order_id is None


def test_adjust_loyalty_negative_delta_debits_balance(db_session) -> None:
    """6.4 — negative delta → balance снижается, amount negative."""
    from core_api.services.admin_users import adjust_loyalty

    user, _ = make_user_with_loyalty_and_profile(
        db_session, balance=500, status=UserStatus.ACTIVE, display_name="U"
    )
    db_session.commit()

    response = adjust_loyalty(
        db=db_session, user_id=user.id, delta=-200, reason="chargeback"
    )

    assert response.new_balance == 300
    assert response.delta == -200

    account = db_session.get(LoyaltyAccount, user.id)
    assert account.balance == 300

    tx = (
        db_session.query(LoyaltyTransaction)
        .filter(LoyaltyTransaction.user_id == user.id)
        .one()
    )
    assert tx.amount == -200


def test_adjust_loyalty_insufficient_balance_raises_and_rolls_back(db_session) -> None:
    """6.5 — INV-004: недостаточно баланса → raise + никаких изменений в БД."""
    from core_api.services.admin_users import (
        InsufficientBalanceError,
        adjust_loyalty,
    )

    user, _ = make_user_with_loyalty_and_profile(
        db_session, balance=100, status=UserStatus.ACTIVE, display_name="U"
    )
    db_session.commit()

    with pytest.raises(InsufficientBalanceError):
        adjust_loyalty(db=db_session, user_id=user.id, delta=-200, reason="oops")

    db_session.expire_all()
    account = db_session.get(LoyaltyAccount, user.id)
    assert account.balance == 100

    txs = (
        db_session.query(LoyaltyTransaction)
        .filter(LoyaltyTransaction.user_id == user.id)
        .all()
    )
    assert len(txs) == 0


def test_adjust_loyalty_blocked_user_is_accepted(db_session) -> None:
    """6.6 — BLOCKED user принимается (вернуть баллы до unblock)."""
    from core_api.services.admin_users import adjust_loyalty

    user, _ = make_user_with_loyalty_and_profile(
        db_session, balance=100, status=UserStatus.BLOCKED, display_name="B"
    )
    db_session.commit()

    response = adjust_loyalty(
        db=db_session, user_id=user.id, delta=200, reason="refund before unblock"
    )

    assert response.new_balance == 300


def test_adjust_loyalty_pending_verification_raises_invalid_state(db_session) -> None:
    """6.7 — PENDING_VERIFICATION → InvalidUserStateError."""
    from core_api.services.admin_users import InvalidUserStateError, adjust_loyalty

    user, _ = make_user_with_loyalty_and_profile(
        db_session, balance=0, status=UserStatus.PENDING_VERIFICATION, display_name="P"
    )
    db_session.commit()

    with pytest.raises(InvalidUserStateError):
        adjust_loyalty(db=db_session, user_id=user.id, delta=100, reason="x")


def test_adjust_loyalty_deleted_raises_invalid_state(db_session) -> None:
    """6.8 — DELETED → InvalidUserStateError."""
    from core_api.services.admin_users import InvalidUserStateError, adjust_loyalty

    user, _ = make_user_with_loyalty_and_profile(
        db_session, balance=0, status=UserStatus.DELETED, display_name="D"
    )
    db_session.commit()

    with pytest.raises(InvalidUserStateError):
        adjust_loyalty(db=db_session, user_id=user.id, delta=100, reason="x")


def test_adjust_loyalty_tombstone_raises_invalid_state(db_session) -> None:
    """6.9 — tombstoned user → InvalidUserStateError."""
    from core_api.services.admin_users import InvalidUserStateError, adjust_loyalty

    user, _ = make_user_with_loyalty_and_profile(
        db_session,
        balance=0,
        status=UserStatus.ACTIVE,
        display_name="T",
        deleted_at=datetime.now(tz=UTC),
    )
    db_session.commit()

    with pytest.raises(InvalidUserStateError):
        adjust_loyalty(db=db_session, user_id=user.id, delta=100, reason="x")


def test_adjust_loyalty_schema_rejects_delta_zero() -> None:
    """6.10 — LoyaltyAdjustRequest отклоняет delta=0."""
    import pydantic

    from core_api.schemas.admin_users import LoyaltyAdjustRequest

    with pytest.raises(pydantic.ValidationError):
        LoyaltyAdjustRequest(delta=0, reason="x")


def test_adjust_loyalty_schema_rejects_empty_reason() -> None:
    """6.11 — LoyaltyAdjustRequest отклоняет reason=''."""
    import pydantic

    from core_api.schemas.admin_users import LoyaltyAdjustRequest

    with pytest.raises(pydantic.ValidationError):
        LoyaltyAdjustRequest(delta=10, reason="")


def test_adjust_loyalty_schema_rejects_reason_longer_than_500() -> None:
    """6.12 — LoyaltyAdjustRequest отклоняет reason > 500 chars."""
    import pydantic

    from core_api.schemas.admin_users import LoyaltyAdjustRequest

    with pytest.raises(pydantic.ValidationError):
        LoyaltyAdjustRequest(delta=10, reason="x" * 501)


# ===========================================================================
# 6.13–6.21 — POST /api/v1/admin/users/{user_id}/loyalty/adjust router tests
# ===========================================================================


def test_adjust_loyalty_route_registered() -> None:
    """6.13 — POST /api/v1/admin/users/{user_id}/loyalty/adjust регистрируется."""
    matches = []
    for route in app.routes:
        methods = getattr(route, "methods", set()) or set()
        path = getattr(route, "path", "")
        if (
            "POST" in methods
            and path == "/api/v1/admin/users/{user_id}/loyalty/adjust"
        ):
            matches.append(route)

    assert len(matches) == 1, (
        f"Ожидался ровно 1 POST /api/v1/admin/users/{{user_id}}/loyalty/adjust, "
        f"нашли {len(matches)}"
    )


def test_adjust_loyalty_route_rejects_no_auth(admin_users_client) -> None:
    """6.14 — без Authorization header → 401."""
    response = admin_users_client.post(
        f"/api/v1/admin/users/{uuid.uuid4()}/loyalty/adjust",
        json={"delta": 10, "reason": "x"},
    )
    assert response.status_code == 401


@pytest.mark.parametrize(
    "role_fixture",
    ["barista_headers", "courier_headers", "customer_headers"],
)
def test_adjust_loyalty_route_rejects_non_admin_roles(
    admin_users_client, request, role_fixture
) -> None:
    """6.15 — не-ADMIN роли → 403 (INV-010)."""
    headers = request.getfixturevalue(role_fixture)
    response = admin_users_client.post(
        f"/api/v1/admin/users/{uuid.uuid4()}/loyalty/adjust",
        json={"delta": 10, "reason": "x"},
        headers=headers,
    )
    assert response.status_code == 403


def test_adjust_loyalty_route_happy_path_returns_200(
    admin_users_client, admin_headers, db_session
) -> None:
    """6.16 — ADMIN delta=500 → 200, new_balance=600, transaction_id - valid UUID."""
    user, _ = make_user_with_loyalty_and_profile(
        db_session, balance=100, status=UserStatus.ACTIVE, display_name="U"
    )
    db_session.commit()

    response = admin_users_client.post(
        f"/api/v1/admin/users/{user.id}/loyalty/adjust",
        json={"delta": 500, "reason": "service credit"},
        headers=admin_headers,
    )
    assert response.status_code == 200

    body = response.json()
    assert body["new_balance"] == 600
    assert body["delta"] == 500
    # transaction_id валидный UUID
    uuid.UUID(body["transaction_id"])


def test_adjust_loyalty_route_422_on_delta_zero(
    admin_users_client, admin_headers, db_session
) -> None:
    """6.17 — delta=0 → 422."""
    user = make_user_with_profile(
        db_session, status=UserStatus.ACTIVE, display_name="U"
    )
    db_session.commit()

    response = admin_users_client.post(
        f"/api/v1/admin/users/{user.id}/loyalty/adjust",
        json={"delta": 0, "reason": "x"},
        headers=admin_headers,
    )
    assert response.status_code == 422


def test_adjust_loyalty_route_422_on_empty_reason(
    admin_users_client, admin_headers, db_session
) -> None:
    """6.18 — reason='' → 422."""
    user = make_user_with_profile(
        db_session, status=UserStatus.ACTIVE, display_name="U"
    )
    db_session.commit()

    response = admin_users_client.post(
        f"/api/v1/admin/users/{user.id}/loyalty/adjust",
        json={"delta": 10, "reason": ""},
        headers=admin_headers,
    )
    assert response.status_code == 422


def test_adjust_loyalty_route_422_on_long_reason(
    admin_users_client, admin_headers, db_session
) -> None:
    """6.19 — reason > 500 chars → 422."""
    user = make_user_with_profile(
        db_session, status=UserStatus.ACTIVE, display_name="U"
    )
    db_session.commit()

    response = admin_users_client.post(
        f"/api/v1/admin/users/{user.id}/loyalty/adjust",
        json={"delta": 10, "reason": "x" * 501},
        headers=admin_headers,
    )
    assert response.status_code == 422


def test_adjust_loyalty_route_422_on_insufficient_balance(
    admin_users_client, admin_headers, db_session
) -> None:
    """6.20 — balance=100, delta=-200 → 422 + detail insufficient_balance."""
    user, _ = make_user_with_loyalty_and_profile(
        db_session, balance=100, status=UserStatus.ACTIVE, display_name="U"
    )
    db_session.commit()

    response = admin_users_client.post(
        f"/api/v1/admin/users/{user.id}/loyalty/adjust",
        json={"delta": -200, "reason": "x"},
        headers=admin_headers,
    )
    assert response.status_code == 422
    body = response.json()
    # detail может быть строкой или dict-ом — проверяем, что упоминается
    detail_text = str(body.get("detail", ""))
    assert "insufficient_balance" in detail_text


def test_adjust_loyalty_route_409_on_deleted_user(
    admin_users_client, admin_headers, db_session
) -> None:
    """6.21 — tombstoned user → 409."""
    user, _ = make_user_with_loyalty_and_profile(
        db_session,
        balance=0,
        status=UserStatus.ACTIVE,
        display_name="T",
        deleted_at=datetime.now(tz=UTC),
    )
    db_session.commit()

    response = admin_users_client.post(
        f"/api/v1/admin/users/{user.id}/loyalty/adjust",
        json={"delta": 10, "reason": "x"},
        headers=admin_headers,
    )
    assert response.status_code == 409
