"""RED: тесты customer-loyalty-api — transactions feed (PDD §3, §5.2, §7.1 Phase 5 item 2).

Все импорты целевых символов выполняются ВНУТРИ тестов — RED-фаза их ещё
не содержит. DB-тесты требуют PostgreSQL (db_session skip-ает на sqlite).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import fakeredis
import pytest
from fastapi.testclient import TestClient

from core_api.main import app
from shared.enums import LoyaltyTransactionType
from tests._factories.loyalty import (
    make_user_with_loyalty,
    seed_loyalty_transaction,
    seed_n_transactions,
)
from tests._helpers.jwt import auth_headers_for_user


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def loyalty_client(db_session):
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
# 3.x — list_transactions service tests
# ===========================================================================


def test_list_transactions_symbol_absent() -> None:
    """3.1 — символ должен существовать (GREEN-target)."""
    from core_api.services.loyalty import list_transactions  # noqa: F401

    assert callable(list_transactions)


def test_list_transactions_sorts_created_at_desc(db_session) -> None:
    """3.2 — items отсортированы created_at DESC."""
    from core_api.services.loyalty import list_transactions

    user, _ = make_user_with_loyalty(db_session, balance=0)
    t0 = datetime.now(tz=UTC) - timedelta(hours=1)
    t1 = seed_loyalty_transaction(
        db_session,
        user=user,
        type=LoyaltyTransactionType.ACCRUAL,
        amount=10,
        balance_after=10,
        created_at=t0,
    )
    t2 = seed_loyalty_transaction(
        db_session,
        user=user,
        type=LoyaltyTransactionType.ACCRUAL,
        amount=10,
        balance_after=20,
        created_at=t0 + timedelta(minutes=1),
    )
    t3 = seed_loyalty_transaction(
        db_session,
        user=user,
        type=LoyaltyTransactionType.ACCRUAL,
        amount=10,
        balance_after=30,
        created_at=t0 + timedelta(minutes=2),
    )
    db_session.commit()

    result = list_transactions(
        user_id=user.id, page=1, per_page=20, db_session=db_session
    )
    assert [item.id for item in result.items] == [t3.id, t2.id, t1.id]


def test_list_transactions_pagination_slice_and_total(db_session) -> None:
    """3.3 — page=2, per_page=10 возвращает срез DESC-ранг 11..20."""
    from core_api.services.loyalty import list_transactions

    user, _ = make_user_with_loyalty(db_session, balance=0)
    seeded = seed_n_transactions(db_session, user=user, count=25)
    db_session.commit()

    result = list_transactions(
        user_id=user.id, page=2, per_page=10, db_session=db_session
    )
    assert result.total == 25
    assert len(result.items) == 10
    assert result.page == 2
    assert result.per_page == 10
    # seeded.ids — ASC по created_at; DESC-rank 11..20 = срез ASC rank 6..15 (0-indexed 5..14)
    desc_ids = list(reversed(seeded.ids))
    assert [item.id for item in result.items] == desc_ids[10:20]


def test_list_transactions_contains_all_four_types(db_session) -> None:
    """3.4 — в ответе представлены все 4 типа транзакций."""
    from core_api.services.loyalty import list_transactions

    user, _ = make_user_with_loyalty(db_session, balance=0)
    for idx, tx_type in enumerate(
        [
            LoyaltyTransactionType.ACCRUAL,
            LoyaltyTransactionType.REDEMPTION,
            LoyaltyTransactionType.REVERSAL,
            LoyaltyTransactionType.ADMIN_ADJUSTMENT,
        ]
    ):
        seed_loyalty_transaction(
            db_session,
            user=user,
            type=tx_type,
            amount=-10 if tx_type == LoyaltyTransactionType.REDEMPTION else 10,
            balance_after=idx * 10,
        )
    db_session.commit()

    result = list_transactions(
        user_id=user.id, page=1, per_page=20, db_session=db_session
    )
    types = {item.type for item in result.items}
    assert types == {
        LoyaltyTransactionType.ACCRUAL,
        LoyaltyTransactionType.REDEMPTION,
        LoyaltyTransactionType.REVERSAL,
        LoyaltyTransactionType.ADMIN_ADJUSTMENT,
    }


def test_list_transactions_admin_adjustment_has_null_order_id(db_session) -> None:
    """3.5 — ADMIN_ADJUSTMENT транзакция отдаётся с order_id=None."""
    from core_api.services.loyalty import list_transactions

    user, _ = make_user_with_loyalty(db_session, balance=0)
    seed_loyalty_transaction(
        db_session,
        user=user,
        type=LoyaltyTransactionType.ADMIN_ADJUSTMENT,
        amount=100,
        balance_after=100,
        order_id=None,
    )
    db_session.commit()

    result = list_transactions(
        user_id=user.id, page=1, per_page=20, db_session=db_session
    )
    assert len(result.items) == 1
    assert result.items[0].order_id is None


def test_list_transactions_empty_history(db_session) -> None:
    """3.6 — пустая история → total=0, items=[]."""
    from core_api.services.loyalty import list_transactions

    user, _ = make_user_with_loyalty(db_session, balance=0)
    db_session.commit()

    result = list_transactions(
        user_id=user.id, page=1, per_page=20, db_session=db_session
    )
    assert result.total == 0
    assert result.items == []


def test_list_transactions_isolates_users(db_session) -> None:
    """3.7 — user A видит только свои транзакции (INV-010)."""
    from core_api.services.loyalty import list_transactions

    user_a, _ = make_user_with_loyalty(db_session, balance=0)
    user_b, _ = make_user_with_loyalty(db_session, balance=0)
    a_seed = seed_n_transactions(db_session, user=user_a, count=2)
    b_seed = seed_n_transactions(db_session, user=user_b, count=3)
    db_session.commit()

    result = list_transactions(
        user_id=user_a.id, page=1, per_page=20, db_session=db_session
    )
    assert result.total == 2
    returned = {item.id for item in result.items}
    assert returned.issubset(set(a_seed.ids))
    assert returned.isdisjoint(set(b_seed.ids))


# ===========================================================================
# 4.x — Pydantic schema tests (transactions)
# ===========================================================================


def test_transaction_schema_module_absent() -> None:
    """4.3 — импорт LoyaltyTransactionResponse / LoyaltyTransactionListResponse."""
    from core_api.schemas.loyalty import (  # noqa: F401
        LoyaltyTransactionListResponse,
        LoyaltyTransactionResponse,
    )

    assert LoyaltyTransactionResponse is not None
    assert LoyaltyTransactionListResponse is not None


def test_transaction_schema_has_required_fields() -> None:
    """4.4 — LoyaltyTransactionResponse содержит ожидаемые поля."""
    from core_api.schemas.loyalty import LoyaltyTransactionResponse

    assert set(LoyaltyTransactionResponse.model_fields.keys()) >= {
        "id",
        "type",
        "amount",
        "balance_after",
        "order_id",
        "description",
        "created_at",
    }


def test_transaction_list_schema_has_required_fields() -> None:
    """4.5 — LoyaltyTransactionListResponse содержит items/page/per_page/total."""
    from core_api.schemas.loyalty import LoyaltyTransactionListResponse

    assert set(LoyaltyTransactionListResponse.model_fields.keys()) >= {
        "items",
        "page",
        "per_page",
        "total",
    }


# ===========================================================================
# 6.x — GET /api/v1/profile/loyalty/transactions router tests
# ===========================================================================


def test_transactions_route_not_registered() -> None:
    """6.1 — GREEN target: ровно 1 маршрут."""
    matches = [
        route
        for route in app.routes
        if "GET" in (getattr(route, "methods", set()) or set())
        and getattr(route, "path", "") == "/api/v1/profile/loyalty/transactions"
    ]
    assert len(matches) == 1, (
        f"Ожидался ровно 1 GET /api/v1/profile/loyalty/transactions, нашли {len(matches)}"
    )


def test_transactions_requires_authorization(loyalty_client) -> None:
    """6.2 — без токена → 401."""
    response = loyalty_client.get("/api/v1/profile/loyalty/transactions")
    assert response.status_code == 401


def test_transactions_rejects_admin(loyalty_client, admin_headers) -> None:
    """6.3a — admin → 403."""
    response = loyalty_client.get(
        "/api/v1/profile/loyalty/transactions", headers=admin_headers
    )
    assert response.status_code == 403


def test_transactions_rejects_barista(loyalty_client, barista_headers) -> None:
    """6.3b — barista → 403."""
    response = loyalty_client.get(
        "/api/v1/profile/loyalty/transactions", headers=barista_headers
    )
    assert response.status_code == 403


def test_transactions_rejects_courier(loyalty_client, courier_headers) -> None:
    """6.3c — courier → 403."""
    response = loyalty_client.get(
        "/api/v1/profile/loyalty/transactions", headers=courier_headers
    )
    assert response.status_code == 403


def test_transactions_rejects_per_page_over_100(loyalty_client, db_session) -> None:
    """6.4 — per_page=101 → 422."""
    user, _ = make_user_with_loyalty(db_session, balance=0)
    db_session.commit()
    headers = auth_headers_for_user(user.id, role="customer")
    response = loyalty_client.get(
        "/api/v1/profile/loyalty/transactions?per_page=101", headers=headers
    )
    assert response.status_code == 422


def test_transactions_returns_items_sorted_desc_with_pagination(
    loyalty_client, db_session
) -> None:
    """6.5 — page=2, per_page=10 → срез DESC-rank 11..20."""
    user, _ = make_user_with_loyalty(db_session, balance=0)
    seeded = seed_n_transactions(db_session, user=user, count=25)
    db_session.commit()

    headers = auth_headers_for_user(user.id, role="customer")
    response = loyalty_client.get(
        "/api/v1/profile/loyalty/transactions?page=2&per_page=10", headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 25
    assert body["page"] == 2
    assert body["per_page"] == 10
    assert len(body["items"]) == 10
    desc_ids = [str(i) for i in reversed(seeded.ids)]
    assert [item["id"] for item in body["items"]] == desc_ids[10:20]


def test_transactions_body_contains_all_four_types(loyalty_client, db_session) -> None:
    """6.6 — все 4 типа транзакций представлены в ответе."""
    user, _ = make_user_with_loyalty(db_session, balance=0)
    for idx, tx_type in enumerate(
        [
            LoyaltyTransactionType.ACCRUAL,
            LoyaltyTransactionType.REDEMPTION,
            LoyaltyTransactionType.REVERSAL,
            LoyaltyTransactionType.ADMIN_ADJUSTMENT,
        ]
    ):
        seed_loyalty_transaction(
            db_session,
            user=user,
            type=tx_type,
            amount=-10 if tx_type == LoyaltyTransactionType.REDEMPTION else 10,
            balance_after=idx * 10,
        )
    db_session.commit()

    headers = auth_headers_for_user(user.id, role="customer")
    response = loyalty_client.get(
        "/api/v1/profile/loyalty/transactions", headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    types = {item["type"] for item in body["items"]}
    assert types == {"accrual", "redemption", "reversal", "admin_adjustment"}


def test_transactions_admin_adjustment_order_id_is_null(
    loyalty_client, db_session
) -> None:
    """6.7 — order_id=null для ADMIN_ADJUSTMENT."""
    user, _ = make_user_with_loyalty(db_session, balance=0)
    seed_loyalty_transaction(
        db_session,
        user=user,
        type=LoyaltyTransactionType.ADMIN_ADJUSTMENT,
        amount=100,
        balance_after=100,
        order_id=None,
    )
    db_session.commit()

    headers = auth_headers_for_user(user.id, role="customer")
    response = loyalty_client.get(
        "/api/v1/profile/loyalty/transactions", headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["order_id"] is None


def test_transactions_empty_history_returns_empty_list(
    loyalty_client, db_session
) -> None:
    """6.8 — пустая история → total=0, items=[]."""
    user, _ = make_user_with_loyalty(db_session, balance=0)
    db_session.commit()

    headers = auth_headers_for_user(user.id, role="customer")
    response = loyalty_client.get(
        "/api/v1/profile/loyalty/transactions", headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["items"] == []
