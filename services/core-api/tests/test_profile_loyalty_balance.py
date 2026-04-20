"""RED: тесты customer-loyalty-api — balance (PDD §3, §5.2, §7.1 Phase 5 item 2).

Все импорты целевых символов (`core_api.services.loyalty.get_balance`,
`core_api.schemas.loyalty.LoyaltyBalanceResponse`, `/api/v1/profile/loyalty`
route) выполняются ВНУТРИ тестов — в RED-фазе они ещё не существуют, и
import на модульном уровне сорвал бы сборку.

DB-тесты требуют PostgreSQL (db_session фикстура skip-ает на sqlite).
"""
from __future__ import annotations

from unittest.mock import patch

import fakeredis
import pytest
from fastapi.testclient import TestClient

from core_api.main import app
from shared.enums import LoyaltyTransactionType
from tests._factories.loyalty import (
    make_user_active,
    make_user_with_loyalty,
    seed_loyalty_transaction,
)
from tests._helpers.jwt import auth_headers_for_user


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def loyalty_client(db_session):
    """TestClient с get_db/get_session → db_session и fake redis."""
    fake_redis = fakeredis.FakeRedis()

    def _override_redis():
        yield fake_redis

    def _override_db():
        yield db_session

    with (
        patch("core_api.deps.redis.get_redis", side_effect=_override_redis),
        patch("core_api.deps.database.get_session", side_effect=_override_db),
        patch("core_api.deps.database.get_db", side_effect=_override_db),
    ):
        with TestClient(app) as c:
            yield c
    fake_redis.flushall()


# ===========================================================================
# 2.x — get_balance service tests
# ===========================================================================


def test_get_balance_symbol_absent() -> None:
    """2.1 — символ должен существовать (GREEN-таргет)."""
    from core_api.services.loyalty import get_balance  # noqa: F401

    assert callable(get_balance)


def test_get_balance_returns_account_balance_and_lifetime_from_accrual_only(
    db_session,
) -> None:
    """2.2 — lifetime_accrued считается только из ACCRUAL транзакций."""
    from core_api.services.loyalty import get_balance

    user, _ = make_user_with_loyalty(db_session, balance=500)
    # Три ACCRUAL — суммируются в lifetime
    seed_loyalty_transaction(
        db_session,
        user=user,
        type=LoyaltyTransactionType.ACCRUAL,
        amount=100,
        balance_after=100,
    )
    seed_loyalty_transaction(
        db_session,
        user=user,
        type=LoyaltyTransactionType.ACCRUAL,
        amount=200,
        balance_after=300,
    )
    seed_loyalty_transaction(
        db_session,
        user=user,
        type=LoyaltyTransactionType.ACCRUAL,
        amount=50,
        balance_after=350,
    )
    # REDEMPTION и REVERSAL не должны попасть в lifetime
    seed_loyalty_transaction(
        db_session,
        user=user,
        type=LoyaltyTransactionType.REDEMPTION,
        amount=-30,
        balance_after=320,
    )
    seed_loyalty_transaction(
        db_session,
        user=user,
        type=LoyaltyTransactionType.REVERSAL,
        amount=-50,
        balance_after=270,
    )
    db_session.commit()

    result = get_balance(user_id=user.id, db_session=db_session)
    assert result.balance == 500
    assert result.lifetime_accrued == 350


def test_get_balance_zero_for_new_user(db_session) -> None:
    """2.3 — новый пользователь (нет транзакций) → balance=0, lifetime=0."""
    from core_api.services.loyalty import get_balance

    user, _ = make_user_with_loyalty(db_session, balance=0)
    db_session.commit()

    result = get_balance(user_id=user.id, db_session=db_session)
    assert result.balance == 0
    assert result.lifetime_accrued == 0


def test_get_balance_raises_when_account_row_missing(db_session) -> None:
    """2.4 — отсутствующий loyalty_accounts row → LoyaltyAccountMissingError."""
    from core_api.services.loyalty import LoyaltyAccountMissingError, get_balance

    user = make_user_active(db_session)  # БЕЗ LoyaltyAccount
    db_session.commit()

    with pytest.raises(LoyaltyAccountMissingError):
        get_balance(user_id=user.id, db_session=db_session)


def test_get_balance_isolates_users(db_session) -> None:
    """2.5 — значения user B не просачиваются в ответ для user A (INV-010)."""
    from core_api.services.loyalty import get_balance

    user_a, _ = make_user_with_loyalty(db_session, balance=100)
    user_b, _ = make_user_with_loyalty(db_session, balance=9999)
    seed_loyalty_transaction(
        db_session,
        user=user_a,
        type=LoyaltyTransactionType.ACCRUAL,
        amount=100,
        balance_after=100,
    )
    seed_loyalty_transaction(
        db_session,
        user=user_b,
        type=LoyaltyTransactionType.ACCRUAL,
        amount=9999,
        balance_after=9999,
    )
    db_session.commit()

    result = get_balance(user_id=user_a.id, db_session=db_session)
    assert result.balance == 100
    assert result.lifetime_accrued == 100


# ===========================================================================
# 4.x — Pydantic schema tests (balance)
# ===========================================================================


def test_balance_schema_module_absent() -> None:
    """4.1 — модуль schemas.loyalty должен существовать с LoyaltyBalanceResponse."""
    from core_api.schemas.loyalty import LoyaltyBalanceResponse  # noqa: F401

    assert LoyaltyBalanceResponse is not None


def test_balance_schema_fields() -> None:
    """4.2 — LoyaltyBalanceResponse содержит balance + lifetime_accrued."""
    from core_api.schemas.loyalty import LoyaltyBalanceResponse

    instance = LoyaltyBalanceResponse(balance=500, lifetime_accrued=350)
    assert instance.balance == 500
    assert instance.lifetime_accrued == 350
    assert set(LoyaltyBalanceResponse.model_fields.keys()) == {
        "balance",
        "lifetime_accrued",
    }


# ===========================================================================
# 5.x — GET /api/v1/profile/loyalty router tests
# ===========================================================================


def test_balance_route_not_registered() -> None:
    """5.1 — GREEN target: ровно 1 маршрут GET /api/v1/profile/loyalty."""
    matches = [
        route
        for route in app.routes
        if "GET" in (getattr(route, "methods", set()) or set())
        and getattr(route, "path", "") == "/api/v1/profile/loyalty"
    ]
    assert len(matches) == 1, (
        f"Ожидался ровно 1 GET /api/v1/profile/loyalty, нашли {len(matches)}"
    )


def test_balance_requires_authorization(loyalty_client) -> None:
    """5.2 — без токена → 401."""
    response = loyalty_client.get("/api/v1/profile/loyalty")
    assert response.status_code == 401


def test_balance_rejects_admin(loyalty_client, admin_headers) -> None:
    """5.3 — admin → 403 (INV-010)."""
    response = loyalty_client.get("/api/v1/profile/loyalty", headers=admin_headers)
    assert response.status_code == 403


def test_balance_rejects_barista(loyalty_client, barista_headers) -> None:
    """5.4 — barista → 403."""
    response = loyalty_client.get("/api/v1/profile/loyalty", headers=barista_headers)
    assert response.status_code == 403


def test_balance_rejects_courier(loyalty_client, courier_headers) -> None:
    """5.5 — courier → 403."""
    response = loyalty_client.get("/api/v1/profile/loyalty", headers=courier_headers)
    assert response.status_code == 403


def test_balance_returns_balance_and_lifetime_for_customer(
    loyalty_client, db_session
) -> None:
    """5.6 — customer видит свой balance + lifetime_accrued."""
    user, _ = make_user_with_loyalty(db_session, balance=500)
    seed_loyalty_transaction(
        db_session,
        user=user,
        type=LoyaltyTransactionType.ACCRUAL,
        amount=100,
        balance_after=100,
    )
    seed_loyalty_transaction(
        db_session,
        user=user,
        type=LoyaltyTransactionType.ACCRUAL,
        amount=250,
        balance_after=350,
    )
    db_session.commit()

    headers = auth_headers_for_user(user.id, role="customer")
    response = loyalty_client.get("/api/v1/profile/loyalty", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"balance": 500, "lifetime_accrued": 350}
