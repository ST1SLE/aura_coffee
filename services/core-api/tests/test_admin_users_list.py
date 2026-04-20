"""RED: тесты staff-scoped листинга пользователей (admin-users-api, PDD §6.5, §7.1 item 2).

Импорты target-символов (list_users и router под /api/v1/admin/users)
выполняются ВНУТРИ тел тестов: в RED-фазе они отсутствуют, и импорт
на уровне модуля сорвал бы всю сборку файла.

БД-тесты требуют PostgreSQL (db_session фикстура skip-ается на sqlite).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import fakeredis
import pytest
from fastapi.testclient import TestClient

from core_api.main import app
from shared.enums import UserStatus
from tests._factories.admin_users import (
    make_user_with_loyalty_and_profile,
    make_user_with_profile,
    seed_admin_users_across_statuses,
)


@pytest.fixture
def admin_users_client(db_session):
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
# 2.x — list_users service tests
# ===========================================================================


def test_list_users_symbol_absent() -> None:
    """2.1 — символ list_users должен существовать после GREEN."""
    from core_api.services.admin_users import list_users  # noqa: F401

    assert callable(list_users)


def test_list_users_status_all_includes_every_status_and_tombstones(db_session) -> None:
    """2.2 — status='all' возвращает все UserStatus + tombstoned пользователей."""
    from core_api.services.admin_users import list_users

    seeded = seed_admin_users_across_statuses(
        db_session,
        counts={
            UserStatus.ACTIVE: 1,
            UserStatus.BLOCKED: 1,
            UserStatus.PENDING_VERIFICATION: 1,
            UserStatus.DELETED: 1,
        },
    )
    # Tombstoned ACTIVE
    tombstoned = make_user_with_profile(
        db_session,
        status=UserStatus.ACTIVE,
        display_name="Tombstoned",
        deleted_at=datetime.now(tz=UTC),
    )
    db_session.commit()

    result = list_users(
        db=db_session,
        status="all",
        search=None,
        page=1,
        per_page=50,
    )

    returned_ids = {item.id for item in result.items}
    for ids in seeded.values():
        for uid in ids:
            assert uid in returned_ids
    assert tombstoned.id in returned_ids


def test_list_users_status_active_excludes_tombstones(db_session) -> None:
    """2.3 — status='active' исключает tombstoned users и BLOCKED."""
    from core_api.services.admin_users import list_users

    active1 = make_user_with_profile(db_session, status=UserStatus.ACTIVE, display_name="A1")
    active2 = make_user_with_profile(db_session, status=UserStatus.ACTIVE, display_name="A2")
    make_user_with_profile(
        db_session,
        status=UserStatus.ACTIVE,
        display_name="Tombstoned",
        deleted_at=datetime.now(tz=UTC),
    )
    make_user_with_profile(db_session, status=UserStatus.BLOCKED, display_name="B1")
    db_session.commit()

    result = list_users(
        db=db_session,
        status="active",
        search=None,
        page=1,
        per_page=50,
    )

    ids = {item.id for item in result.items}
    assert ids == {active1.id, active2.id}
    assert len(result.items) == 2


def test_list_users_status_blocked_filters_exact(db_session) -> None:
    """2.4 — status='blocked' возвращает только BLOCKED."""
    from core_api.services.admin_users import list_users

    seed_admin_users_across_statuses(
        db_session,
        counts={
            UserStatus.ACTIVE: 1,
            UserStatus.BLOCKED: 2,
            UserStatus.PENDING_VERIFICATION: 1,
            UserStatus.DELETED: 1,
        },
    )
    db_session.commit()

    result = list_users(
        db=db_session,
        status="blocked",
        search=None,
        page=1,
        per_page=50,
    )

    assert result.total_count == 2
    for item in result.items:
        assert item.status == "blocked"


def test_list_users_status_pending_verification_filters_exact(db_session) -> None:
    """2.5 — status='pending_verification' возвращает только PENDING_VERIFICATION."""
    from core_api.services.admin_users import list_users

    seed_admin_users_across_statuses(
        db_session,
        counts={
            UserStatus.ACTIVE: 1,
            UserStatus.BLOCKED: 1,
            UserStatus.PENDING_VERIFICATION: 3,
        },
    )
    db_session.commit()

    result = list_users(
        db=db_session,
        status="pending_verification",
        search=None,
        page=1,
        per_page=50,
    )

    assert result.total_count == 3
    for item in result.items:
        assert item.status == "pending_verification"


def test_list_users_status_deleted_returns_deleted_and_tombstones(db_session) -> None:
    """2.6 — status='deleted' возвращает DELETED и tombstoned пользователей."""
    from core_api.services.admin_users import list_users

    deleted_user = make_user_with_profile(
        db_session, status=UserStatus.DELETED, display_name="D1"
    )
    tombstoned = make_user_with_profile(
        db_session,
        status=UserStatus.ACTIVE,
        display_name="Tombstoned",
        deleted_at=datetime.now(tz=UTC),
    )
    db_session.commit()

    result = list_users(
        db=db_session,
        status="deleted",
        search=None,
        page=1,
        per_page=50,
    )

    ids = {item.id for item in result.items}
    assert deleted_user.id in ids
    assert tombstoned.id in ids


def test_list_users_search_prefix_matches_display_name_case_insensitively(
    db_session,
) -> None:
    """2.7 — search='ali' находит 'Alice' и 'alicia', не находит 'Bob'."""
    from core_api.services.admin_users import list_users

    alice = make_user_with_profile(
        db_session, status=UserStatus.ACTIVE, display_name="Alice"
    )
    alicia = make_user_with_profile(
        db_session, status=UserStatus.ACTIVE, display_name="alicia"
    )
    make_user_with_profile(db_session, status=UserStatus.ACTIVE, display_name="Bob")
    db_session.commit()

    result = list_users(
        db=db_session,
        status="all",
        search="ali",
        page=1,
        per_page=50,
    )

    ids = {item.id for item in result.items}
    assert alice.id in ids
    assert alicia.id in ids
    assert len(result.items) == 2


def test_list_users_search_does_not_match_phone_hash_fragment(db_session) -> None:
    """2.8 — INV-013: search НЕ должен обходить display_name и матчить phone_hash."""
    from core_api.services.admin_users import list_users

    # phone_hash начинается на "abcdef..." — 64 hex chars
    make_user_with_profile(
        db_session,
        status=UserStatus.ACTIVE,
        display_name="Valery",
        phone_hash="abcdef" + "0" * 58,
    )
    db_session.commit()

    result = list_users(
        db=db_session,
        status="all",
        search="abc",
        page=1,
        per_page=50,
    )

    # Поиск "abc" не должен найти Valery через phone_hash
    assert len(result.items) == 0


def test_list_users_pagination_page_2_slices_rows_and_reports_total(db_session) -> None:
    """2.9 — page=2, per_page=10 → 10 rows, total_count=25."""
    from core_api.services.admin_users import list_users

    for i in range(25):
        make_user_with_profile(
            db_session,
            status=UserStatus.ACTIVE,
            display_name=f"u{i:02d}",
            created_at=datetime.now(tz=UTC) - timedelta(minutes=25 - i),
        )
    db_session.commit()

    result = list_users(
        db=db_session,
        status="all",
        search=None,
        page=2,
        per_page=10,
    )

    assert result.total_count == 25
    assert len(result.items) == 10
    assert result.page == 2
    assert result.per_page == 10


def test_list_users_sort_is_created_at_desc(db_session) -> None:
    """2.10 — сортировка по users.created_at DESC."""
    from core_api.services.admin_users import list_users

    t1 = datetime(2026, 4, 1, 12, 0, tzinfo=UTC)
    t2 = datetime(2026, 4, 1, 13, 0, tzinfo=UTC)
    t3 = datetime(2026, 4, 1, 14, 0, tzinfo=UTC)

    u1 = make_user_with_profile(
        db_session, status=UserStatus.ACTIVE, display_name="u1", created_at=t1
    )
    u2 = make_user_with_profile(
        db_session, status=UserStatus.ACTIVE, display_name="u2", created_at=t2
    )
    u3 = make_user_with_profile(
        db_session, status=UserStatus.ACTIVE, display_name="u3", created_at=t3
    )
    db_session.commit()

    result = list_users(
        db=db_session,
        status="all",
        search=None,
        page=1,
        per_page=50,
    )

    returned_ids = [item.id for item in result.items]
    # Самый свежий (u3) → первый
    assert returned_ids[:3] == [u3.id, u2.id, u1.id]


def test_list_users_loyalty_balance_coalesces_to_zero_when_account_absent(
    db_session,
) -> None:
    """2.11 — у ACTIVE-user без LoyaltyAccount loyalty_balance == 0."""
    from core_api.services.admin_users import list_users

    user = make_user_with_profile(
        db_session, status=UserStatus.ACTIVE, display_name="NoLoyalty"
    )
    db_session.commit()

    result = list_users(
        db=db_session,
        status="active",
        search=None,
        page=1,
        per_page=50,
    )

    items_by_id = {item.id: item for item in result.items}
    assert user.id in items_by_id
    assert items_by_id[user.id].loyalty_balance == 0


def test_list_users_summary_has_no_phone_or_phone_hash_fields(db_session) -> None:
    """2.12 — UserSummary НЕ выставляет phone / phone_hash (INV-013)."""
    from core_api.services.admin_users import list_users

    make_user_with_loyalty_and_profile(
        db_session,
        balance=100,
        status=UserStatus.ACTIVE,
        display_name="UserX",
    )
    db_session.commit()

    result = list_users(
        db=db_session,
        status="active",
        search=None,
        page=1,
        per_page=50,
    )

    assert len(result.items) >= 1
    item = result.items[0]
    assert hasattr(item, "phone") is False
    assert hasattr(item, "phone_hash") is False
    dumped = item.model_dump()
    assert "phone" not in dumped
    assert "phone_hash" not in dumped


# ===========================================================================
# 7.9–7.12 — route-level RBAC for GET /api/v1/admin/users
# ===========================================================================


def test_admin_users_list_rejects_no_auth_route_level(admin_users_client) -> None:
    """7.9 — GET /api/v1/admin/users без токена → 401."""
    response = admin_users_client.get("/api/v1/admin/users")
    assert response.status_code == 401


def test_admin_users_list_rejects_barista(admin_users_client, barista_headers) -> None:
    """7.10 — barista → 403 (INV-010)."""
    response = admin_users_client.get("/api/v1/admin/users", headers=barista_headers)
    assert response.status_code == 403


def test_admin_users_list_rejects_courier(admin_users_client, courier_headers) -> None:
    """7.11 — courier → 403 (INV-010)."""
    response = admin_users_client.get("/api/v1/admin/users", headers=courier_headers)
    assert response.status_code == 403


def test_admin_users_list_rejects_customer(admin_users_client, customer_headers) -> None:
    """7.12 — customer → 403 (INV-010)."""
    response = admin_users_client.get("/api/v1/admin/users", headers=customer_headers)
    assert response.status_code == 403


# ===========================================================================
# Route registration guard
# ===========================================================================


def test_admin_users_list_route_registered() -> None:
    """GET /api/v1/admin/users должен быть зарегистрирован ровно один раз (GREEN target)."""
    matches = []
    for route in app.routes:
        methods = getattr(route, "methods", set()) or set()
        path = getattr(route, "path", "")
        if "GET" in methods and path == "/api/v1/admin/users":
            matches.append(route)

    assert len(matches) == 1, (
        f"Ожидался ровно 1 GET /api/v1/admin/users, нашли {len(matches)}"
    )
