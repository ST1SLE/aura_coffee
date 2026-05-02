"""RED-фаза: контракт `core_api.services.notification.send_order_notification`.

Pins PDD §6.1 (Order Lifecycle — notification matrix), §7.8 (SMS Delivery Chain),
§8.2 (SMS content), INV-013 (PII isolation), INV-016 (explicit transitions).

Все тесты ДОЛЖНЫ падать в RED (до реализации в `order-notifications-green`):
- импорт `core_api.services.notification` — внутри тел тестов (чтобы pytest
  мог собрать модуль даже без целевого модуля).
- ошибка `ImportError` или `AttributeError` — ожидаемый RED-отказ.
"""

from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from shared.enums import (
    NotificationChannel,
    NotificationStatus,
    NotificationType,
    OrderStatus,
    OrderType,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ─────────────────────────────────────────────
# Фабрики: User + UserProfile + Order
# ─────────────────────────────────────────────

def _make_user(db: "Session", *, preferred_language: str = "ru") -> tuple[object, object]:
    """Создаёт User + UserProfile c зашифрованным телефоном. Возвращает (user, profile)."""
    from core_api.settings import settings
    from core_api.utils.crypto import encrypt_phone, hash_phone
    from shared.models.user import User
    from shared.models.user_profile import UserProfile

    phone = "+79991234567"
    key = bytes.fromhex(settings.encryption_key)
    encrypted = encrypt_phone(phone, key)

    user = User(phone_hash=hash_phone(phone + uuid.uuid4().hex))
    db.add(user)
    db.flush()

    profile = UserProfile(
        user_id=user.id,
        phone=encrypted,
        display_name="Тест",
        preferred_language=preferred_language,
    )
    db.add(profile)
    db.flush()
    return user, profile


def _make_order(
    db: "Session",
    user_id: uuid.UUID,
    *,
    order_type: OrderType = OrderType.PICKUP,
    status: OrderStatus = OrderStatus.CREATED,
    order_id: uuid.UUID | None = None,
) -> object:
    """Создаёт минимально-валидный Order."""
    from shared.models.order import Order

    order = Order(
        id=order_id or uuid.uuid4(),
        user_id=user_id,
        type=order_type,
        status=status,
        subtotal=1000,
        discount_amount=0,
        points_used=0,
        delivery_fee=0,
        total=1000,
        estimated_accrual=0,
        auto_completed=False,
    )
    db.add(order)
    db.flush()
    return order


# ─────────────────────────────────────────────
# 2.x  Fixture smoke tests
# ─────────────────────────────────────────────


def test_make_order_fixture_smoke(db_session) -> None:
    """2.1 — фабрика make_order возвращает Order с UUID id и PICKUP type."""
    user, _ = _make_user(db_session)
    order = _make_order(db_session, user.id, order_type=OrderType.PICKUP)
    assert isinstance(order.id, uuid.UUID)
    assert order.type == OrderType.PICKUP


def test_fixture_returns_hex_string(db_session) -> None:
    """2.2 — зашифрованный phone_hex соответствует ^[0-9a-f]+$ и длиннее 24 символов."""
    _, profile = _make_user(db_session)
    encrypted_hex = profile.phone.hex() if isinstance(profile.phone, bytes) else profile.phone
    assert re.fullmatch(r"[0-9a-f]+", encrypted_hex)
    assert len(encrypted_hex) > 24


# ─────────────────────────────────────────────
# 3.x  IN_APP row tests
# ─────────────────────────────────────────────

SHORT_ID_CASES: list[tuple] = [
    # (new_status, order_type, cancelled_by, requires_sms)
    (OrderStatus.PAID, OrderType.PICKUP, None, True),
    (OrderStatus.PREPARING, OrderType.PICKUP, None, True),
    (OrderStatus.READY, OrderType.PICKUP, None, True),
    (OrderStatus.READY, OrderType.DELIVERY, None, True),
    (OrderStatus.IN_DELIVERY, OrderType.DELIVERY, None, False),
    (OrderStatus.COMPLETED, OrderType.PICKUP, None, False),
    (OrderStatus.COMPLETED, OrderType.DELIVERY, None, True),
    (OrderStatus.CANCELLED, OrderType.PICKUP, "customer", True),
    (OrderStatus.CANCELLED, OrderType.PICKUP, "admin", True),
]


def test_paid_writes_in_app_row_status_sent(db_session) -> None:
    """3.1 — IN_APP уведомление для PAID: status=SENT, bilingual, FK user/order."""
    from core_api.services.notification import send_order_notification
    from shared.models.notification import Notification

    user, _ = _make_user(db_session)
    order = _make_order(db_session, user.id, order_type=OrderType.PICKUP)

    send_order_notification(
        order_id=order.id,
        user_id=user.id,
        new_status=OrderStatus.PAID,
        db_session=db_session,
    )

    rows = (
        db_session.query(Notification)
        .filter(Notification.order_id == order.id, Notification.channel == NotificationChannel.IN_APP)
        .all()
    )
    assert len(rows) == 1
    n = rows[0]
    assert n.type == NotificationType.ORDER_STATUS_CHANGE
    assert n.status == NotificationStatus.SENT
    assert n.user_id == user.id
    assert n.order_id == order.id
    assert n.message_ru
    assert n.message_en
    assert n.message_ru != n.message_en


@pytest.mark.parametrize(
    "new_status,order_type,cancelled_by,_requires_sms",
    SHORT_ID_CASES,
    ids=[
        "paid-pickup",
        "preparing-pickup",
        "ready-pickup",
        "ready-delivery",
        "in-delivery",
        "completed-pickup",
        "completed-delivery",
        "cancelled-customer",
        "cancelled-admin",
    ],
)
def test_in_app_row_written_for_every_status_with_notification(
    db_session, new_status, order_type, cancelled_by, _requires_sms
) -> None:
    """3.2 — IN_APP-строка пишется для каждого из 9 §6.1-кейсов."""
    from core_api.services.notification import send_order_notification
    from shared.models.notification import Notification

    user, _ = _make_user(db_session)
    order = _make_order(db_session, user.id, order_type=order_type)

    with patch("core_api.services.notification.send_order_notification_sms", MagicMock()):
        send_order_notification(
            order_id=order.id,
            user_id=user.id,
            new_status=new_status,
            db_session=db_session,
            cancelled_by=cancelled_by,
        )

    rows = (
        db_session.query(Notification)
        .filter(Notification.order_id == order.id, Notification.channel == NotificationChannel.IN_APP)
        .all()
    )
    assert len(rows) == 1
    n = rows[0]
    assert n.type == NotificationType.ORDER_STATUS_CHANGE
    assert n.status == NotificationStatus.SENT
    assert n.message_ru and n.message_en


def test_in_app_row_text_matches_preferred_language_selection(db_session) -> None:
    """3.3 — оба поля message_ru/message_en заполнены; helper возвращает нужное."""
    from core_api.services.notification import (
        resolve_display_text,
        send_order_notification,
    )
    from shared.models.notification import Notification

    user_ru, _ = _make_user(db_session, preferred_language="ru")
    order_ru = _make_order(db_session, user_ru.id, order_type=OrderType.PICKUP)

    user_en, _ = _make_user(db_session, preferred_language="en")
    order_en = _make_order(db_session, user_en.id, order_type=OrderType.PICKUP)

    with patch("core_api.services.notification.send_order_notification_sms", MagicMock()):
        send_order_notification(
            order_id=order_ru.id,
            user_id=user_ru.id,
            new_status=OrderStatus.PAID,
            db_session=db_session,
        )
        send_order_notification(
            order_id=order_en.id,
            user_id=user_en.id,
            new_status=OrderStatus.PAID,
            db_session=db_session,
        )

    n_ru = (
        db_session.query(Notification)
        .filter(Notification.order_id == order_ru.id, Notification.channel == NotificationChannel.IN_APP)
        .one()
    )
    n_en = (
        db_session.query(Notification)
        .filter(Notification.order_id == order_en.id, Notification.channel == NotificationChannel.IN_APP)
        .one()
    )
    assert n_ru.message_ru and n_ru.message_en
    assert n_en.message_ru and n_en.message_en
    assert resolve_display_text(n_ru, "ru") == n_ru.message_ru
    assert resolve_display_text(n_en, "en") == n_en.message_en


# ─────────────────────────────────────────────
# 4.x  SMS row + dispatch tests
# ─────────────────────────────────────────────


def test_paid_writes_sms_row_status_pending(db_session) -> None:
    """4.1 — PAID → вторая строка channel=SMS, status=PENDING, bilingual."""
    from core_api.services.notification import send_order_notification
    from shared.models.notification import Notification

    user, _ = _make_user(db_session)
    order = _make_order(db_session, user.id)

    with patch("core_api.services.notification.send_order_notification_sms", MagicMock()):
        send_order_notification(
            order_id=order.id,
            user_id=user.id,
            new_status=OrderStatus.PAID,
            db_session=db_session,
        )

    sms_rows = (
        db_session.query(Notification)
        .filter(Notification.order_id == order.id, Notification.channel == NotificationChannel.SMS)
        .all()
    )
    assert len(sms_rows) == 1
    s = sms_rows[0]
    assert s.status == NotificationStatus.PENDING
    assert s.type == NotificationType.ORDER_STATUS_CHANGE
    assert s.message_ru and s.message_en


def test_in_delivery_does_not_write_sms_row(db_session) -> None:
    """4.2 — IN_DELIVERY (delivery) → только IN_APP, SMS не пишется."""
    from core_api.services.notification import send_order_notification
    from shared.models.notification import Notification

    user, _ = _make_user(db_session)
    order = _make_order(db_session, user.id, order_type=OrderType.DELIVERY)

    with patch("core_api.services.notification.send_order_notification_sms", MagicMock()) as mock_task:
        send_order_notification(
            order_id=order.id,
            user_id=user.id,
            new_status=OrderStatus.IN_DELIVERY,
            db_session=db_session,
        )

    rows = db_session.query(Notification).filter(Notification.order_id == order.id).all()
    assert {r.channel for r in rows} == {NotificationChannel.IN_APP}
    mock_task.delay.assert_not_called()


def test_completed_pickup_does_not_write_sms_row(db_session) -> None:
    """4.3 — COMPLETED (pickup) → только IN_APP."""
    from core_api.services.notification import send_order_notification
    from shared.models.notification import Notification

    user, _ = _make_user(db_session)
    order = _make_order(db_session, user.id, order_type=OrderType.PICKUP)

    with patch("core_api.services.notification.send_order_notification_sms", MagicMock()) as mock_task:
        send_order_notification(
            order_id=order.id,
            user_id=user.id,
            new_status=OrderStatus.COMPLETED,
            db_session=db_session,
        )

    rows = db_session.query(Notification).filter(Notification.order_id == order.id).all()
    assert {r.channel for r in rows} == {NotificationChannel.IN_APP}
    mock_task.delay.assert_not_called()


SMS_REQUIRED_CASES = [
    (OrderStatus.PAID, OrderType.PICKUP, None),
    (OrderStatus.PREPARING, OrderType.PICKUP, None),
    (OrderStatus.READY, OrderType.PICKUP, None),
    (OrderStatus.READY, OrderType.DELIVERY, None),
    (OrderStatus.COMPLETED, OrderType.DELIVERY, None),
    (OrderStatus.CANCELLED, OrderType.PICKUP, "customer"),
    (OrderStatus.CANCELLED, OrderType.PICKUP, "admin"),
]


@pytest.mark.parametrize(
    "new_status,order_type,cancelled_by",
    SMS_REQUIRED_CASES,
    ids=[
        "paid",
        "preparing",
        "ready-pickup",
        "ready-delivery",
        "completed-delivery",
        "cancelled-customer",
        "cancelled-admin",
    ],
)
def test_sms_required_cases_enqueue_celery_task(
    db_session, new_status, order_type, cancelled_by
) -> None:
    """4.4 — SMS-обязательные кейсы enqueue task с (notification_id, encrypted_phone_hex, message)."""
    from core_api.services.notification import send_order_notification
    from shared.models.notification import Notification

    user, profile = _make_user(db_session)
    order = _make_order(db_session, user.id, order_type=order_type)

    mock_task = MagicMock()
    with patch("core_api.services.notification.send_order_notification_sms", mock_task):
        send_order_notification(
            order_id=order.id,
            user_id=user.id,
            new_status=new_status,
            db_session=db_session,
            cancelled_by=cancelled_by,
        )

    assert mock_task.delay.call_count == 1
    args, kwargs = mock_task.delay.call_args
    # Разрешаем либо позиционные, либо именованные аргументы
    payload = list(args) + [kwargs.get("notification_id"), kwargs.get("encrypted_phone_hex"), kwargs.get("message")]
    non_none_payload = [x for x in payload if x is not None]
    assert len(non_none_payload) >= 3

    sms_row = (
        db_session.query(Notification)
        .filter(Notification.order_id == order.id, Notification.channel == NotificationChannel.SMS)
        .one()
    )
    # notification_id совпадает с id строки
    assert sms_row.id in non_none_payload
    # encrypted_phone_hex — hex стринга
    hex_strings = [x for x in non_none_payload if isinstance(x, str) and re.fullmatch(r"[0-9a-f]+", x)]
    assert hex_strings
    assert profile.phone.hex() in hex_strings
    # message — SMS-тело формата §8.2: '{status_text}. Заказ №{short_id}. Aura Coffee'
    messages = [x for x in non_none_payload if isinstance(x, str) and x not in hex_strings]
    assert messages
    msg = next(m for m in messages if m.endswith(". Aura Coffee"))
    assert f"Заказ №{order.id.hex[:8]}" in msg
    assert len(msg) <= 70


@pytest.mark.parametrize(
    "new_status,order_type",
    [
        (OrderStatus.IN_DELIVERY, OrderType.DELIVERY),
        (OrderStatus.COMPLETED, OrderType.PICKUP),
    ],
    ids=["in-delivery", "completed-pickup"],
)
def test_in_app_only_cases_do_not_enqueue_task(db_session, new_status, order_type) -> None:
    """4.5 — in-app-only кейсы не enqueue-ят Celery task."""
    from core_api.services.notification import send_order_notification

    user, _ = _make_user(db_session)
    order = _make_order(db_session, user.id, order_type=order_type)

    mock_task = MagicMock()
    with patch("core_api.services.notification.send_order_notification_sms", mock_task):
        send_order_notification(
            order_id=order.id,
            user_id=user.id,
            new_status=new_status,
            db_session=db_session,
        )

    mock_task.delay.assert_not_called()


def test_celery_task_is_dispatched_by_registered_name() -> None:
    """4.6 — service использует задачу, зарегистрированную как sms_worker.send_order_notification_sms."""
    from core_api.services import notification as notification_module

    task = notification_module.send_order_notification_sms
    assert getattr(task, "name", None) == "sms_worker.send_order_notification_sms"


def test_legacy_lifecycle_wrapper_uses_canonical_notification_service(db_session) -> None:
    """4.6a — старый lifecycle import path пишет rows и ставит зарегистрированную SMS task."""
    from core_api.services.order_notifications import send_order_notification
    from shared.models.notification import Notification

    user, profile = _make_user(db_session)
    order = _make_order(db_session, user.id, order_type=OrderType.PICKUP)

    mock_task = MagicMock()
    with patch("core_api.services.notification.send_order_notification_sms", mock_task):
        send_order_notification(order, OrderStatus.PREPARING, actor_role="barista")

    rows = (
        db_session.query(Notification)
        .filter(Notification.order_id == order.id)
        .all()
    )
    assert {row.channel for row in rows} == {
        NotificationChannel.IN_APP,
        NotificationChannel.SMS,
    }
    assert mock_task.delay.call_count == 1
    flat_args = list(mock_task.delay.call_args.args) + list(
        mock_task.delay.call_args.kwargs.values()
    )
    assert "+79991234567" not in " ".join(str(arg) for arg in flat_args)
    assert profile.phone.hex() in [arg for arg in flat_args if isinstance(arg, str)]


def test_plaintext_phone_never_passed_to_task(db_session) -> None:
    """4.7 (INV-013) — открытый телефон НЕ попадает в Celery-аргументы."""
    from core_api.services.notification import send_order_notification

    user, profile = _make_user(db_session)
    order = _make_order(db_session, user.id)

    mock_task = MagicMock()
    with patch("core_api.services.notification.send_order_notification_sms", mock_task):
        send_order_notification(
            order_id=order.id,
            user_id=user.id,
            new_status=OrderStatus.PAID,
            db_session=db_session,
        )

    args, kwargs = mock_task.delay.call_args
    all_args = list(args) + list(kwargs.values())
    for a in all_args:
        if isinstance(a, str):
            assert a != "+79991234567"
    # Хотя бы один аргумент должен быть hex-строкой
    assert any(isinstance(a, str) and re.fullmatch(r"[0-9a-f]+", a) for a in all_args)


def test_sms_row_committed_before_dispatch(db_session) -> None:
    """4.8 — SMS-строка видна в БД на момент вызова .delay()."""
    from core_api.services.notification import send_order_notification
    from shared.models.notification import Notification

    user, _ = _make_user(db_session)
    order = _make_order(db_session, user.id)

    captured: dict = {}

    def _side_effect(*args, **kwargs):
        # в момент вызова строка должна существовать
        ids = [a for a in list(args) + list(kwargs.values()) if isinstance(a, uuid.UUID)]
        captured["ids"] = ids
        captured["rows_at_dispatch"] = (
            db_session.query(Notification)
            .filter(Notification.channel == NotificationChannel.SMS)
            .all()
        )

    mock_task = MagicMock()
    mock_task.delay.side_effect = _side_effect

    with patch("core_api.services.notification.send_order_notification_sms", mock_task):
        send_order_notification(
            order_id=order.id,
            user_id=user.id,
            new_status=OrderStatus.PAID,
            db_session=db_session,
        )

    assert captured["rows_at_dispatch"], "SMS row must exist at dispatch time"
    row_ids = {r.id for r in captured["rows_at_dispatch"]}
    assert any(nid in row_ids for nid in captured["ids"])


# ─────────────────────────────────────────────
# 5.x  short_id + cancellation semantics
# ─────────────────────────────────────────────


def test_short_id_is_first_8_hex_chars_of_uuid(db_session) -> None:
    """5.1 — short_id = uuid.hex[:8]."""
    from core_api.services.notification import send_order_notification
    from shared.models.notification import Notification

    user, _ = _make_user(db_session)
    fixed = uuid.UUID("c0ffee11-1234-4567-89ab-cdefdeadbeef")
    order = _make_order(db_session, user.id, order_id=fixed)

    mock_task = MagicMock()
    with patch("core_api.services.notification.send_order_notification_sms", mock_task):
        send_order_notification(
            order_id=order.id,
            user_id=user.id,
            new_status=OrderStatus.PAID,
            db_session=db_session,
        )

    n = (
        db_session.query(Notification)
        .filter(Notification.order_id == order.id, Notification.channel == NotificationChannel.IN_APP)
        .one()
    )
    assert "c0ffee11" in n.message_ru
    assert "c0ffee11" in n.message_en

    args, kwargs = mock_task.delay.call_args
    all_str_args = [a for a in list(args) + list(kwargs.values()) if isinstance(a, str)]
    assert any("c0ffee11" in a for a in all_str_args)


def test_cancelled_by_customer_uses_refund_wording(db_session) -> None:
    """5.2 — cancelled_by='customer' → refund wording."""
    from core_api.services.notification import send_order_notification
    from shared.models.notification import Notification

    user, _ = _make_user(db_session)
    fixed = uuid.UUID("c0ffee11-1234-4567-89ab-cdefdeadbeef")
    order = _make_order(db_session, user.id, order_id=fixed)

    with patch("core_api.services.notification.send_order_notification_sms", MagicMock()):
        send_order_notification(
            order_id=order.id,
            user_id=user.id,
            new_status=OrderStatus.CANCELLED,
            db_session=db_session,
            cancelled_by="customer",
        )

    n = (
        db_session.query(Notification)
        .filter(Notification.order_id == order.id, Notification.channel == NotificationChannel.IN_APP)
        .one()
    )
    assert n.message_ru == "Заказ №c0ffee11 отменён, средства возвращены"


def test_cancelled_by_admin_uses_coffee_shop_wording(db_session) -> None:
    """5.3 — cancelled_by='admin' → coffee shop wording."""
    from core_api.services.notification import send_order_notification
    from shared.models.notification import Notification

    user, _ = _make_user(db_session)
    fixed = uuid.UUID("c0ffee11-1234-4567-89ab-cdefdeadbeef")
    order = _make_order(db_session, user.id, order_id=fixed)

    with patch("core_api.services.notification.send_order_notification_sms", MagicMock()):
        send_order_notification(
            order_id=order.id,
            user_id=user.id,
            new_status=OrderStatus.CANCELLED,
            db_session=db_session,
            cancelled_by="admin",
        )

    n = (
        db_session.query(Notification)
        .filter(Notification.order_id == order.id, Notification.channel == NotificationChannel.IN_APP)
        .one()
    )
    assert n.message_ru == "Заказ №c0ffee11 отменён кофейней"


def test_cancelled_without_cancelled_by_raises(db_session) -> None:
    """5.4 — CANCELLED без cancelled_by → ValueError, без записей в БД."""
    from core_api.services.notification import send_order_notification
    from shared.models.notification import Notification

    user, _ = _make_user(db_session)
    order = _make_order(db_session, user.id)

    with pytest.raises(ValueError):
        send_order_notification(
            order_id=order.id,
            user_id=user.id,
            new_status=OrderStatus.CANCELLED,
            db_session=db_session,
            cancelled_by=None,
        )

    rows = db_session.query(Notification).filter(Notification.order_id == order.id).all()
    assert rows == []


def test_unknown_transition_raises(db_session) -> None:
    """5.5 — new_status=CREATED (нет notification per §6.1) → ValueError, без записей."""
    from core_api.services.notification import send_order_notification
    from shared.models.notification import Notification

    user, _ = _make_user(db_session)
    order = _make_order(db_session, user.id)

    with pytest.raises(ValueError):
        send_order_notification(
            order_id=order.id,
            user_id=user.id,
            new_status=OrderStatus.CREATED,
            db_session=db_session,
        )

    rows = db_session.query(Notification).filter(Notification.order_id == order.id).all()
    assert rows == []
