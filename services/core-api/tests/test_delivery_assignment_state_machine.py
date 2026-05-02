"""RED: тесты state machine Delivery Assignment (PDD §6.3, INV-010, INV-016).

Покрывают allow-list переходов, forbidden-пары, ownership checks (INV-010),
precondition на order.status для `pickup_assignment`.

Импорты целевого сервиса — ВНУТРИ тестов: в RED-цикле `delivery_assignment`
не существует, сбор файла не должен падать.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Seeding helpers
# ---------------------------------------------------------------------------

def _fresh_session() -> Session:
    from core_api.deps.database import SessionLocal

    return SessionLocal()


def _seed_user(db: Session) -> uuid.UUID:
    from shared.enums import UserStatus
    from shared.models import User

    u = User(phone_hash=uuid.uuid4().hex, status=UserStatus.ACTIVE)
    db.add(u)
    db.flush()
    return u.id


def _seed_loyalty(db: Session, uid: uuid.UUID, balance: int = 0) -> None:
    from shared.models import LoyaltyAccount

    db.add(LoyaltyAccount(user_id=uid, balance=balance))
    db.flush()


def _seed_courier(db: Session) -> uuid.UUID:
    from shared.enums import StaffRole
    from shared.models import StaffAccount

    sa = StaffAccount(
        login=f"courier_{uuid.uuid4().hex[:8]}",
        password_hash="x" * 32,
        role=StaffRole.COURIER,
        display_name="Test Courier",
        is_active=True,
    )
    db.add(sa)
    db.flush()
    return sa.id


def _seed_order(
    db: Session,
    *,
    status: str = "preparing",
    order_type: str = "delivery",
    total: int = 50000,
    delivery_fee: int = 0,
    user_id: uuid.UUID | None = None,
) -> uuid.UUID:
    from shared.enums import OrderStatus, OrderType
    from shared.models import Order

    uid = user_id or _seed_user(db)
    _seed_loyalty(db, uid)
    o = Order(
        user_id=uid,
        status=OrderStatus(status),
        type=OrderType(order_type),
        subtotal=total,
        discount_amount=0,
        points_used=0,
        delivery_fee=delivery_fee,
        total=total,
        estimated_accrual=0,
    )
    db.add(o)
    db.flush()
    return o.id


def _seed_assignment(
    db: Session,
    *,
    status: str,
    order_id: uuid.UUID | None = None,
    courier_id: uuid.UUID | None = None,
    order_status: str = "preparing",
    order_type: str = "delivery",
) -> uuid.UUID:
    from shared.enums import DeliveryAssignmentStatus
    from shared.models import DeliveryAssignment

    if order_id is None:
        order_id = _seed_order(db, status=order_status, order_type=order_type)

    a = DeliveryAssignment(
        order_id=order_id,
        courier_id=courier_id,
        status=DeliveryAssignmentStatus(status),
    )
    db.add(a)
    db.flush()
    return a.id


@pytest.fixture
def db(db_session: Session) -> Session:
    yield db_session


@pytest.fixture
def notify_mock(monkeypatch):
    """Подмена send_order_notification — общий стиль с другими lifecycle-тестами."""
    import sys
    import types

    mod_name = "core_api.services.order_notifications"
    if mod_name not in sys.modules:
        sys.modules[mod_name] = types.ModuleType(mod_name)
    mock = MagicMock()
    monkeypatch.setattr(
        sys.modules[mod_name], "send_order_notification", mock, raising=False
    )
    try:
        import core_api.services.order_lifecycle as sut_ol  # noqa: F401
        monkeypatch.setattr(sut_ol, "send_order_notification", mock, raising=False)
    except ModuleNotFoundError:
        pass
    try:
        import core_api.services.delivery_assignment as sut_da  # noqa: F401
        monkeypatch.setattr(sut_da, "send_order_notification", mock, raising=False)
    except ModuleNotFoundError:
        pass
    return mock


@pytest.fixture
def bridge_mock(monkeypatch):
    """Подмена transition_order_bridge внутри delivery_assignment.

    По умолчанию — no-op, который двигает order.status по паре (src,dst).
    Тесты могут override'нуть на raise.
    """
    import sys
    import types

    ol_name = "core_api.services.order_lifecycle"
    if ol_name not in sys.modules:
        sys.modules[ol_name] = types.ModuleType(ol_name)

    def _bridge(order_id, new_status, actor_role, db_session):
        from shared.models import Order

        order = db_session.get(Order, order_id)
        if order is not None:
            order.status = new_status
            db_session.flush()
        return order

    mock = MagicMock(side_effect=_bridge)
    monkeypatch.setattr(
        sys.modules[ol_name], "transition_order_bridge", mock, raising=False
    )
    try:
        import core_api.services.delivery_assignment as sut
        monkeypatch.setattr(sut, "transition_order_bridge", mock, raising=False)
    except ModuleNotFoundError:
        pass
    return mock


# ---------------------------------------------------------------------------
# 1.1 — import probe
# ---------------------------------------------------------------------------

def test_delivery_assignment_module_exists() -> None:
    from core_api.services.delivery_assignment import (  # noqa: F401
        AssignmentAlreadyTakenError,
        AssignmentTransitionError,
        cancel_assignment_for_order,
        deliver_assignment,
        list_available_for_courier,
        pickup_assignment,
        take_assignment,
    )


# ---------------------------------------------------------------------------
# 1.2 — take happy path
# ---------------------------------------------------------------------------

def test_take_assignment_awaiting_to_assigned_happy_path(
    db: Session, notify_mock: MagicMock, grace_logs
) -> None:
    from core_api.services.delivery_assignment import take_assignment
    from shared.enums import DeliveryAssignmentStatus
    from shared.models import DeliveryAssignment

    cid = _seed_courier(db)
    aid = _seed_assignment(
        db, status="awaiting_courier", order_status="ready"
    )
    db.commit()

    take_assignment(aid, cid, db)

    a = db.get(DeliveryAssignment, aid)
    assert a.status == DeliveryAssignmentStatus.COURIER_ASSIGNED
    assert a.courier_id == cid
    assert a.assigned_at is not None
    grace_logs.assert_trajectory(
        ("delivery.accept", "BLOCK_STATE_TRANSITION"),
    )
    assert grace_logs.beliefs(status="MISMATCH") == []


# ---------------------------------------------------------------------------
# 1.3 — pickup happy path (bridge mocked)
# ---------------------------------------------------------------------------

def test_pickup_assignment_assigned_to_picked_up_happy_path(
    db: Session, notify_mock: MagicMock, bridge_mock: MagicMock, grace_logs
) -> None:
    from core_api.services.delivery_assignment import pickup_assignment
    from shared.enums import DeliveryAssignmentStatus
    from shared.models import DeliveryAssignment

    cid = _seed_courier(db)
    oid = _seed_order(db, status="ready", order_type="delivery")
    aid = _seed_assignment(
        db, status="courier_assigned", order_id=oid, courier_id=cid
    )

    pickup_assignment(aid, cid, db)

    a = db.get(DeliveryAssignment, aid)
    assert a.status == DeliveryAssignmentStatus.PICKED_UP
    assert a.picked_up_at is not None
    grace_logs.assert_trajectory(
        ("delivery.pickup", "BLOCK_STATE_TRANSITION"),
    )
    assert grace_logs.beliefs(status="MISMATCH") == []


# ---------------------------------------------------------------------------
# 1.4 — deliver happy path (bridge mocked)
# ---------------------------------------------------------------------------

def test_deliver_assignment_picked_up_to_delivered_happy_path(
    db: Session, notify_mock: MagicMock, bridge_mock: MagicMock, grace_logs
) -> None:
    from core_api.services.delivery_assignment import deliver_assignment
    from shared.enums import DeliveryAssignmentStatus
    from shared.models import DeliveryAssignment

    cid = _seed_courier(db)
    oid = _seed_order(db, status="in_delivery", order_type="delivery")
    aid = _seed_assignment(
        db, status="picked_up", order_id=oid, courier_id=cid
    )

    deliver_assignment(aid, cid, db)

    a = db.get(DeliveryAssignment, aid)
    assert a.status == DeliveryAssignmentStatus.DELIVERED
    assert a.delivered_at is not None
    grace_logs.assert_trajectory(
        ("delivery.deliver", "BLOCK_STATE_TRANSITION"),
    )
    assert grace_logs.beliefs(status="MISMATCH") == []


# ---------------------------------------------------------------------------
# 1.5 — cancel_assignment_for_order from AWAITING_COURIER
# ---------------------------------------------------------------------------

def test_cancel_assignment_for_order_awaiting_to_cancelled(
    db: Session, notify_mock: MagicMock
) -> None:
    from core_api.services.delivery_assignment import cancel_assignment_for_order
    from shared.enums import DeliveryAssignmentStatus
    from shared.models import DeliveryAssignment

    oid = _seed_order(db, status="preparing", order_type="delivery")
    aid = _seed_assignment(db, status="awaiting_courier", order_id=oid)

    result = cancel_assignment_for_order(oid, db)

    assert result is not None
    a = db.get(DeliveryAssignment, aid)
    assert a.status == DeliveryAssignmentStatus.CANCELLED
    assert a.cancelled_at is not None


# ---------------------------------------------------------------------------
# 1.6 — cancel_assignment_for_order from COURIER_ASSIGNED
# ---------------------------------------------------------------------------

def test_cancel_assignment_for_order_assigned_to_cancelled(
    db: Session, notify_mock: MagicMock
) -> None:
    from core_api.services.delivery_assignment import cancel_assignment_for_order
    from shared.enums import DeliveryAssignmentStatus
    from shared.models import DeliveryAssignment

    cid = _seed_courier(db)
    oid = _seed_order(db, status="preparing", order_type="delivery")
    aid = _seed_assignment(
        db, status="courier_assigned", order_id=oid, courier_id=cid
    )

    result = cancel_assignment_for_order(oid, db)

    assert result is not None
    a = db.get(DeliveryAssignment, aid)
    assert a.status == DeliveryAssignmentStatus.CANCELLED
    assert a.cancelled_at is not None


# ---------------------------------------------------------------------------
# 1.7 — cancel_assignment_for_order on PICKED_UP is no-op
# ---------------------------------------------------------------------------

def test_cancel_assignment_for_order_picked_up_is_noop(
    db: Session, notify_mock: MagicMock
) -> None:
    from core_api.services.delivery_assignment import cancel_assignment_for_order
    from shared.enums import DeliveryAssignmentStatus
    from shared.models import DeliveryAssignment

    cid = _seed_courier(db)
    oid = _seed_order(db, status="in_delivery", order_type="delivery")
    aid = _seed_assignment(
        db, status="picked_up", order_id=oid, courier_id=cid
    )

    result = cancel_assignment_for_order(oid, db)

    assert result is None
    a = db.get(DeliveryAssignment, aid)
    assert a.status == DeliveryAssignmentStatus.PICKED_UP


# ---------------------------------------------------------------------------
# 1.8 — cancel_assignment_for_order when no assignment
# ---------------------------------------------------------------------------

def test_cancel_assignment_for_order_when_no_assignment_returns_none(
    db: Session, notify_mock: MagicMock
) -> None:
    from core_api.services.delivery_assignment import cancel_assignment_for_order

    oid = _seed_order(db, status="preparing", order_type="pickup")
    # Никакого DeliveryAssignment не сидируем.

    result = cancel_assignment_for_order(oid, db)
    assert result is None


# ---------------------------------------------------------------------------
# 1.9 — take on non-AWAITING raises forbidden_transition
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "non_awaiting_status",
    ["courier_assigned", "picked_up", "delivered", "cancelled"],
)
def test_take_assignment_on_non_awaiting_raises_forbidden_transition(
    db: Session, notify_mock: MagicMock, non_awaiting_status: str
) -> None:
    from core_api.services.delivery_assignment import (
        AssignmentTransitionError,
        take_assignment,
    )

    cid = _seed_courier(db)
    # Для «not-yet-terminal» статусов нужен валидный order.status.
    order_status_map = {
        "courier_assigned": "preparing",
        "picked_up": "in_delivery",
        "delivered": "completed",
        "cancelled": "cancelled",
    }
    order_status = order_status_map[non_awaiting_status]
    aid = _seed_assignment(
        db,
        status=non_awaiting_status,
        courier_id=cid if non_awaiting_status != "cancelled" else None,
        order_status=order_status,
    )
    other_courier = _seed_courier(db)
    with pytest.raises(AssignmentTransitionError) as ei:
        take_assignment(aid, other_courier, db)
    assert ei.value.reason == "forbidden_transition"


# ---------------------------------------------------------------------------
# 1.9b — take requires parent order READY
# ---------------------------------------------------------------------------

def test_take_assignment_awaiting_preparing_order_raises_order_not_ready(
    db: Session, notify_mock: MagicMock
) -> None:
    from core_api.services.delivery_assignment import (
        AssignmentTransitionError,
        take_assignment,
    )
    from shared.enums import DeliveryAssignmentStatus
    from shared.models import DeliveryAssignment

    cid = _seed_courier(db)
    aid = _seed_assignment(
        db, status="awaiting_courier", order_status="preparing"
    )
    db.commit()

    with pytest.raises(AssignmentTransitionError) as ei:
        take_assignment(aid, cid, db)

    assert ei.value.reason == "order_not_ready"
    a = db.get(DeliveryAssignment, aid)
    assert a.status == DeliveryAssignmentStatus.AWAITING_COURIER
    assert a.courier_id is None


# ---------------------------------------------------------------------------
# 1.10 — pickup on forbidden src raises forbidden_transition
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "bad_src",
    ["awaiting_courier", "picked_up", "delivered", "cancelled"],
)
def test_forbidden_pickup_transitions(
    db: Session,
    notify_mock: MagicMock,
    bridge_mock: MagicMock,
    bad_src: str,
) -> None:
    from core_api.services.delivery_assignment import (
        AssignmentTransitionError,
        pickup_assignment,
    )

    cid = _seed_courier(db)
    order_status_map = {
        "awaiting_courier": "preparing",
        "picked_up": "in_delivery",
        "delivered": "completed",
        "cancelled": "cancelled",
    }
    aid = _seed_assignment(
        db,
        status=bad_src,
        courier_id=cid,
        order_status=order_status_map[bad_src],
    )

    with pytest.raises(AssignmentTransitionError) as ei:
        pickup_assignment(aid, cid, db)
    assert ei.value.reason == "forbidden_transition"


# ---------------------------------------------------------------------------
# 1.11 — deliver on forbidden src raises forbidden_transition
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "bad_src",
    ["awaiting_courier", "courier_assigned", "delivered", "cancelled"],
)
def test_forbidden_deliver_transitions(
    db: Session,
    notify_mock: MagicMock,
    bridge_mock: MagicMock,
    bad_src: str,
) -> None:
    from core_api.services.delivery_assignment import (
        AssignmentTransitionError,
        deliver_assignment,
    )

    cid = _seed_courier(db)
    order_status_map = {
        "awaiting_courier": "preparing",
        "courier_assigned": "preparing",
        "delivered": "completed",
        "cancelled": "cancelled",
    }
    aid = _seed_assignment(
        db,
        status=bad_src,
        courier_id=cid,
        order_status=order_status_map[bad_src],
    )

    with pytest.raises(AssignmentTransitionError) as ei:
        deliver_assignment(aid, cid, db)
    assert ei.value.reason == "forbidden_transition"


# ---------------------------------------------------------------------------
# 1.12 — pickup ownership mismatch
# ---------------------------------------------------------------------------

def test_pickup_ownership_mismatch_raises_not_owner(
    db: Session, notify_mock: MagicMock, bridge_mock: MagicMock
) -> None:
    from core_api.services.delivery_assignment import (
        AssignmentTransitionError,
        pickup_assignment,
    )
    from shared.enums import DeliveryAssignmentStatus
    from shared.models import DeliveryAssignment

    c1 = _seed_courier(db)
    c2 = _seed_courier(db)
    oid = _seed_order(db, status="ready", order_type="delivery")
    aid = _seed_assignment(
        db, status="courier_assigned", order_id=oid, courier_id=c1
    )

    with pytest.raises(AssignmentTransitionError) as ei:
        pickup_assignment(aid, c2, db)
    assert ei.value.reason == "not_owner"
    a = db.get(DeliveryAssignment, aid)
    assert a.status == DeliveryAssignmentStatus.COURIER_ASSIGNED


# ---------------------------------------------------------------------------
# 1.13 — deliver ownership mismatch
# ---------------------------------------------------------------------------

def test_deliver_ownership_mismatch_raises_not_owner(
    db: Session, notify_mock: MagicMock, bridge_mock: MagicMock
) -> None:
    from core_api.services.delivery_assignment import (
        AssignmentTransitionError,
        deliver_assignment,
    )
    from shared.enums import DeliveryAssignmentStatus
    from shared.models import DeliveryAssignment

    c1 = _seed_courier(db)
    c2 = _seed_courier(db)
    oid = _seed_order(db, status="in_delivery", order_type="delivery")
    aid = _seed_assignment(
        db, status="picked_up", order_id=oid, courier_id=c1
    )

    with pytest.raises(AssignmentTransitionError) as ei:
        deliver_assignment(aid, c2, db)
    assert ei.value.reason == "not_owner"
    a = db.get(DeliveryAssignment, aid)
    assert a.status == DeliveryAssignmentStatus.PICKED_UP


# ---------------------------------------------------------------------------
# 1.14 — pickup requires order.status == READY
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "order_status",
    ["paid", "preparing", "in_delivery"],
)
def test_pickup_requires_order_ready(
    db: Session,
    notify_mock: MagicMock,
    bridge_mock: MagicMock,
    order_status: str,
) -> None:
    from core_api.services.delivery_assignment import (
        AssignmentTransitionError,
        pickup_assignment,
    )
    from shared.enums import DeliveryAssignmentStatus
    from shared.models import DeliveryAssignment

    cid = _seed_courier(db)
    oid = _seed_order(db, status=order_status, order_type="delivery")
    aid = _seed_assignment(
        db, status="courier_assigned", order_id=oid, courier_id=cid
    )

    with pytest.raises(AssignmentTransitionError) as ei:
        pickup_assignment(aid, cid, db)
    assert ei.value.reason == "order_not_ready"
    a = db.get(DeliveryAssignment, aid)
    assert a.status == DeliveryAssignmentStatus.COURIER_ASSIGNED


# ---------------------------------------------------------------------------
# 1.15 — assignment not found
# ---------------------------------------------------------------------------

def test_assignment_not_found_raises(
    db: Session, notify_mock: MagicMock
) -> None:
    from core_api.services.delivery_assignment import (
        AssignmentTransitionError,
        take_assignment,
    )

    cid = _seed_courier(db)
    with pytest.raises(AssignmentTransitionError) as ei:
        take_assignment(uuid.uuid4(), cid, db)
    assert ei.value.reason == "assignment_not_found"


# ---------------------------------------------------------------------------
# 1.16 — list_available_for_courier returns only READY + AWAITING
# ---------------------------------------------------------------------------

def test_list_available_for_courier_returns_only_ready_awaiting_and_redacts_pii(
    db: Session, notify_mock: MagicMock
) -> None:
    from core_api.services.delivery_assignment import list_available_for_courier
    from shared.models import Order

    c1 = _seed_courier(db)
    oid_aw = _seed_order(db, status="ready", order_type="delivery", total=77000)
    oid_preparing = _seed_order(
        db, status="preparing", order_type="delivery", total=66000
    )
    oid_ca = _seed_order(db, status="preparing", order_type="delivery", total=88000)
    oid_dv = _seed_order(db, status="completed", order_type="delivery", total=99000)
    db.get(Order, oid_aw).delivery_address_snapshot = {
        "address_line": "Full street 10",
        "apartment": "42",
        "floor": "7",
        "comment": "Call on arrival",
    }
    aid_aw = _seed_assignment(db, status="awaiting_courier", order_id=oid_aw)
    aid_preparing = _seed_assignment(
        db, status="awaiting_courier", order_id=oid_preparing
    )
    aid_ca = _seed_assignment(
        db, status="courier_assigned", order_id=oid_ca, courier_id=c1
    )
    aid_dv = _seed_assignment(
        db, status="delivered", order_id=oid_dv, courier_id=c1
    )

    rows = list_available_for_courier(db)

    # Тест инспектирует row как объект-вью или mapping. Принимаем обе формы.
    def _get(obj, key):
        if hasattr(obj, key):
            return getattr(obj, key)
        return obj[key]

    rows_by_id = {_get(row, "id"): row for row in rows}
    assert aid_aw in rows_by_id
    assert aid_preparing not in rows_by_id
    assert aid_ca not in rows_by_id
    assert aid_dv not in rows_by_id

    row = rows_by_id[aid_aw]
    assert _get(row, "id") == aid_aw
    assert _get(row, "order_id") == oid_aw
    assert _get(row, "status") == "AWAITING_COURIER"
    assert _get(row, "total") == 77000
    assert _get(row, "delivery_address") == {}
    row_text = str(row)
    assert "Full street 10" not in row_text
    assert "Call on arrival" not in row_text
