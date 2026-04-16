"""RED: тесты валидатора промокодов (PDD §5.2 Промокоды, INV-011).

Контракт `validate_promocode(code, user_id, subtotal, db_session) → Promocode | raises`:
- Неизвестный code → raise PromocodeValidationError.
- is_active=False → raise.
- valid_from > now ИЛИ valid_until < now → raise.
- current_uses >= max_uses → raise.
- COUNT(promocode_usages WHERE (user_id, promocode_id)) >= max_uses_per_user → raise.
- subtotal < min_order_amount → raise.
- Всё ок → return Promocode ORM-инстанс.

Happy-path и базовые негативные сценарии; интеграция в checkout — следующий change.

Тесты per-user quota seeds User + Order + PromocodeUsage (FK RESTRICT на User/Order).
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest


def _make_user(db_session):
    """Минимальный User для PromocodeUsage.user_id FK."""
    from shared.enums import UserStatus
    from shared.models.user import User

    phone = str(uuid.uuid4())
    phone_hash = hashlib.sha256(phone.encode()).hexdigest()
    user = User(phone_hash=phone_hash, status=UserStatus.ACTIVE)
    db_session.add(user)
    db_session.flush()
    return user


def _make_promocode(db_session, **overrides):
    from shared.enums import PromocodeDiscountType
    from shared.models.promocode import Promocode

    code = overrides.pop("code", f"RED{uuid.uuid4().hex[:8].upper()}")
    defaults = dict(
        code=code,
        discount_type=PromocodeDiscountType.PERCENT,
        discount_value=10,
        min_order_amount=0,
        valid_from=None,
        valid_until=None,
        max_uses=None,
        max_uses_per_user=None,
        current_uses=0,
        is_active=True,
    )
    defaults.update(overrides)
    promo = Promocode(**defaults)
    db_session.add(promo)
    db_session.flush()
    return promo


def _make_order(db_session, user_id):
    """Минимальный Order для PromocodeUsage.order_id FK."""
    from shared.enums import OrderStatus, OrderType
    from shared.models.order import Order

    order = Order(
        user_id=user_id,
        status=OrderStatus.CREATED,
        type=OrderType.PICKUP,
        subtotal=10000,
        total=10000,
    )
    db_session.add(order)
    db_session.flush()
    return order


def _make_promocode_usage(db_session, promocode_id, user_id, order_id):
    from shared.models.promocode_usage import PromocodeUsage

    usage = PromocodeUsage(
        promocode_id=promocode_id,
        user_id=user_id,
        order_id=order_id,
    )
    db_session.add(usage)
    db_session.flush()
    return usage


# ---------------------------------------------------------------------------


def test_validate_promocode_unknown_code_raises(db_session) -> None:
    from core_api.services.validators import validate_promocode
    from core_api.services.validators.exceptions import PromocodeValidationError

    with pytest.raises(PromocodeValidationError):
        validate_promocode("WRONG_CODE_XYZ", uuid.uuid4(), 100000, db_session)


def test_validate_promocode_inactive_raises(db_session) -> None:
    from core_api.services.validators import validate_promocode
    from core_api.services.validators.exceptions import PromocodeValidationError

    promo = _make_promocode(db_session, is_active=False)
    user = _make_user(db_session)
    db_session.commit()

    with pytest.raises(PromocodeValidationError):
        validate_promocode(promo.code, user.id, 100000, db_session)


def test_validate_promocode_valid_from_future_raises(db_session) -> None:
    from core_api.services.validators import validate_promocode
    from core_api.services.validators.exceptions import PromocodeValidationError

    future = datetime.now(UTC) + timedelta(hours=1)
    promo = _make_promocode(db_session, valid_from=future)
    user = _make_user(db_session)
    db_session.commit()

    with pytest.raises(PromocodeValidationError):
        validate_promocode(promo.code, user.id, 100000, db_session)


def test_validate_promocode_valid_until_past_raises(db_session) -> None:
    from core_api.services.validators import validate_promocode
    from core_api.services.validators.exceptions import PromocodeValidationError

    past = datetime.now(UTC) - timedelta(hours=1)
    promo = _make_promocode(db_session, valid_until=past)
    user = _make_user(db_session)
    db_session.commit()

    with pytest.raises(PromocodeValidationError):
        validate_promocode(promo.code, user.id, 100000, db_session)


def test_validate_promocode_global_quota_exhausted_raises(db_session) -> None:
    from core_api.services.validators import validate_promocode
    from core_api.services.validators.exceptions import PromocodeValidationError

    promo = _make_promocode(db_session, max_uses=5, current_uses=5)
    user = _make_user(db_session)
    db_session.commit()

    with pytest.raises(PromocodeValidationError):
        validate_promocode(promo.code, user.id, 100000, db_session)


def test_validate_promocode_per_user_quota_exhausted_raises(db_session) -> None:
    from core_api.services.validators import validate_promocode
    from core_api.services.validators.exceptions import PromocodeValidationError

    promo = _make_promocode(db_session, max_uses_per_user=2)
    user = _make_user(db_session)
    order1 = _make_order(db_session, user.id)
    order2 = _make_order(db_session, user.id)
    _make_promocode_usage(db_session, promo.id, user.id, order1.id)
    _make_promocode_usage(db_session, promo.id, user.id, order2.id)
    db_session.commit()

    with pytest.raises(PromocodeValidationError):
        validate_promocode(promo.code, user.id, 100000, db_session)


def test_validate_promocode_subtotal_below_min_order_amount_raises(db_session) -> None:
    from core_api.services.validators import validate_promocode
    from core_api.services.validators.exceptions import PromocodeValidationError

    promo = _make_promocode(db_session, min_order_amount=150000)
    user = _make_user(db_session)
    db_session.commit()

    with pytest.raises(PromocodeValidationError):
        validate_promocode(promo.code, user.id, 100000, db_session)


def test_validate_promocode_happy_path_returns_promocode(db_session) -> None:
    from core_api.services.validators import validate_promocode

    promo = _make_promocode(
        db_session,
        code="HAPPY10",
        discount_value=10,
        min_order_amount=50000,
    )
    user = _make_user(db_session)
    db_session.commit()

    result = validate_promocode("HAPPY10", user.id, 100000, db_session)
    assert result.code == "HAPPY10"
    assert result.discount_value == 10
