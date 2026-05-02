"""Account deletion/anonymization tests (PDD §6.5, INV-013, INV-016)."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import fakeredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from core_api.deps.database import get_db, get_session
from core_api.deps.redis import get_redis
from core_api.main import app
from core_api.routers.admin_users import _get_redis as admin_get_redis
from core_api.routers.admin_users import _get_session as admin_get_session
from core_api.services.auth import AuthService
from shared.enums import OrderStatus, OrderType, PaymentStatus, UserStatus
from shared.models.delivery_address import DeliveryAddress
from shared.models.loyalty_account import LoyaltyAccount
from shared.models.order import Order
from shared.models.payment import Payment
from shared.models.user import User
from shared.models.user_profile import UserProfile
from tests._factories.admin_users import make_user_with_loyalty_and_profile
from tests._factories.orders import seed_orders_across_statuses


@pytest.fixture
def account_deletion_client(db_session: Session):
    fake_redis = fakeredis.FakeRedis()

    def _override_db():
        yield db_session

    def _override_redis():
        yield fake_redis

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_session] = _override_db
    app.dependency_overrides[get_redis] = _override_redis
    app.dependency_overrides[admin_get_session] = _override_db
    app.dependency_overrides[admin_get_redis] = _override_redis
    with TestClient(app) as client:
        client.fake_redis = fake_redis
        yield client
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(get_redis, None)
    app.dependency_overrides.pop(admin_get_session, None)
    app.dependency_overrides.pop(admin_get_redis, None)
    fake_redis.flushall()


@pytest.fixture
def cancellation_side_effects():
    with (
        patch("core_api.services.order_cancel.send_order_notification") as notify,
        patch(
            "core_api.services.order_cancel.celery_app.send_task",
            new_callable=MagicMock,
        ) as send_task,
    ):
        yield notify, send_task


def _customer_headers(
    client: TestClient,
    user_id: uuid.UUID,
) -> tuple[dict[str, str], str, str]:
    pair = AuthService(client.fake_redis).issue_tokens(user_id)
    return {"Authorization": f"Bearer {pair.access_token}"}, pair.access_token, pair.refresh_token


def _add_address(session: Session, user_id: uuid.UUID, address_text: str) -> None:
    session.add(
        DeliveryAddress(
            user_id=user_id,
            label="Home",
            address_text=address_text,
            lat=55.7558,
            lon=37.6173,
            apartment="42",
            entrance="1",
            floor="7",
            comment="leave at door",
            is_default=True,
        )
    )
    session.flush()


def _add_payments(session: Session, orders: list[Order]) -> None:
    for order in orders:
        session.add(
            Payment(
                order_id=order.id,
                amount=order.total,
                status=PaymentStatus.SUCCEEDED,
                yukassa_payment_id=f"pay_{order.id.hex[:24]}",
                idempotency_key=f"idem_{order.id.hex[:24]}",
            )
        )
    session.flush()


def test_customer_delete_tombstones_removes_pii_revokes_sessions_and_logs_redacted(
    account_deletion_client,
    db_session: Session,
    cancellation_side_effects,
    grace_logs,
) -> None:
    user, account = make_user_with_loyalty_and_profile(
        db_session,
        status=UserStatus.ACTIVE,
        display_name="Sensitive Name",
        balance=375,
        phone_hash="a" * 64,
    )
    _add_address(db_session, user.id, "Secret Street 123")
    db_session.commit()
    headers, access_token, refresh_token = _customer_headers(
        account_deletion_client, user.id
    )

    response = account_deletion_client.delete("/api/v1/profile", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "deleted"
    assert response.json()["cancelled_orders_count"] == 0
    assert response.json()["pii_rows_removed"] == 2
    assert account_deletion_client.fake_redis.get(f"session:{refresh_token}") is None

    db_session.expire_all()
    deleted_user = db_session.get(User, user.id)
    assert deleted_user.status == UserStatus.DELETED
    assert deleted_user.deleted_at is not None
    assert deleted_user.phone_hash != "a" * 64
    assert len(deleted_user.phone_hash) == 64
    assert db_session.get(UserProfile, user.id) is None
    assert (
        db_session.query(DeliveryAddress)
        .filter(DeliveryAddress.user_id == user.id)
        .count()
        == 0
    )
    assert db_session.get(LoyaltyAccount, user.id).balance == 0
    assert account.balance == 0

    grace_logs.assert_trajectory(
        ("profile.delete", "BLOCK_AUTH_VERIFY"),
        ("profile.delete", "BLOCK_TX_BEGIN"),
        ("profile.delete", "BLOCK_STATE_TRANSITION"),
        ("profile.delete", "BLOCK_TX_COMMIT"),
    )
    assert grace_logs.beliefs(status="MISMATCH") == []
    joined_logs = "\n".join(grace_logs.lines)
    for forbidden in (
        "Sensitive Name",
        "Secret Street 123",
        access_token,
        refresh_token,
        "a" * 64,
    ):
        assert forbidden not in joined_logs


def test_customer_delete_cancels_active_orders_and_enqueues_refunds(
    account_deletion_client,
    db_session: Session,
    cancellation_side_effects,
    grace_logs,
) -> None:
    _, send_task = cancellation_side_effects
    user, _ = make_user_with_loyalty_and_profile(
        db_session,
        status=UserStatus.ACTIVE,
        display_name="Delete With Orders",
        balance=0,
    )
    seeded = seed_orders_across_statuses(
        db_session,
        user=user,
        counts={
            (OrderStatus.PAID, OrderType.PICKUP): 1,
            (OrderStatus.PREPARING, OrderType.PICKUP): 1,
            (OrderStatus.READY, OrderType.PICKUP): 1,
        },
    )
    orders = db_session.query(Order).filter(Order.user_id == user.id).all()
    _add_payments(db_session, orders)
    db_session.commit()
    headers, _, _ = _customer_headers(account_deletion_client, user.id)

    response = account_deletion_client.delete("/api/v1/profile", headers=headers)

    assert response.status_code == 200
    assert response.json()["cancelled_orders_count"] == 3
    for order_id in [
        order_id
        for bucket in seeded.order_ids_by_bucket.values()
        for order_id in bucket
    ]:
        assert db_session.get(Order, order_id).status == OrderStatus.CANCELLED
    assert send_task.call_count == 3
    grace_logs.assert_trajectory(
        ("orders.cancel", "BLOCK_TX_BEGIN"),
        ("orders.cancel", "BLOCK_STATE_TRANSITION"),
        ("orders.cancel", "BLOCK_TX_COMMIT"),
        ("profile.delete", "BLOCK_TX_BEGIN"),
        ("profile.delete", "BLOCK_STATE_TRANSITION"),
        ("profile.delete", "BLOCK_TX_COMMIT"),
    )
    assert grace_logs.beliefs(status="MISMATCH") == []


def test_admin_delete_blocked_user_tombstones_and_revokes_sessions(
    account_deletion_client,
    admin_headers,
    db_session: Session,
    cancellation_side_effects,
    grace_logs,
) -> None:
    user, _ = make_user_with_loyalty_and_profile(
        db_session,
        status=UserStatus.BLOCKED,
        display_name="Blocked Sensitive",
        balance=120,
    )
    _add_address(db_session, user.id, "Blocked Secret Address")
    db_session.commit()
    pair = AuthService(account_deletion_client.fake_redis).issue_tokens(user.id)

    response = account_deletion_client.delete(
        f"/api/v1/admin/users/{user.id}",
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "deleted"
    assert account_deletion_client.fake_redis.get(f"session:{pair.refresh_token}") is None
    db_session.expire_all()
    assert db_session.get(User, user.id).status == UserStatus.DELETED
    assert db_session.get(UserProfile, user.id) is None
    assert (
        db_session.query(DeliveryAddress)
        .filter(DeliveryAddress.user_id == user.id)
        .count()
        == 0
    )
    assert db_session.get(LoyaltyAccount, user.id).balance == 0
    grace_logs.assert_trajectory(
        ("admin.users.delete", "BLOCK_AUTH_VERIFY"),
        ("admin.users.delete", "BLOCK_TX_BEGIN"),
        ("admin.users.delete", "BLOCK_STATE_TRANSITION"),
        ("admin.users.delete", "BLOCK_TX_COMMIT"),
    )
    assert grace_logs.beliefs(status="MISMATCH") == []
    joined_logs = "\n".join(grace_logs.lines)
    assert "Blocked Sensitive" not in joined_logs
    assert "Blocked Secret Address" not in joined_logs
    assert pair.refresh_token not in joined_logs


def test_admin_delete_active_user_returns_409(
    account_deletion_client,
    admin_headers,
    db_session: Session,
    cancellation_side_effects,
) -> None:
    user, _ = make_user_with_loyalty_and_profile(
        db_session,
        status=UserStatus.ACTIVE,
        display_name="Still Active",
        balance=0,
    )
    db_session.commit()

    response = account_deletion_client.delete(
        f"/api/v1/admin/users/{user.id}",
        headers=admin_headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "invalid_user_state"
    db_session.expire_all()
    assert db_session.get(User, user.id).status == UserStatus.ACTIVE


def test_delete_rejects_in_delivery_order_without_tombstoning(
    account_deletion_client,
    db_session: Session,
    cancellation_side_effects,
) -> None:
    user, _ = make_user_with_loyalty_and_profile(
        db_session,
        status=UserStatus.ACTIVE,
        display_name="Delivery Active",
        balance=0,
    )
    seed_orders_across_statuses(
        db_session,
        user=user,
        counts={(OrderStatus.IN_DELIVERY, OrderType.DELIVERY): 1},
    )
    db_session.commit()
    headers, _, _ = _customer_headers(account_deletion_client, user.id)

    response = account_deletion_client.delete("/api/v1/profile", headers=headers)

    assert response.status_code == 409
    assert response.json()["detail"] == "active_order_not_deletable"
    db_session.expire_all()
    assert db_session.get(User, user.id).status == UserStatus.ACTIVE
    assert db_session.get(UserProfile, user.id) is not None


def test_deleted_user_cannot_refresh_or_mutate_after_delete(
    account_deletion_client,
    db_session: Session,
    cancellation_side_effects,
) -> None:
    user, _ = make_user_with_loyalty_and_profile(
        db_session,
        status=UserStatus.ACTIVE,
        display_name="Delete Then Block",
        balance=0,
    )
    db_session.commit()
    headers, access_token, refresh_token = _customer_headers(
        account_deletion_client, user.id
    )

    delete_response = account_deletion_client.delete(
        "/api/v1/profile",
        headers=headers,
    )
    assert delete_response.status_code == 200

    refresh_response = account_deletion_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_response.status_code == 401

    mutate_response = account_deletion_client.patch(
        "/api/v1/profile",
        json={"display_name": "Should Not Work"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert mutate_response.status_code == 401
