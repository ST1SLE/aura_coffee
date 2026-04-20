"""Фабричные функции для Promocode (используется admin-promocodes тестами).

make_promocode — одна запись с sensible defaults.
seed_promocodes_across_states — четыре бакета (inactive/active/expired/exhausted)
для тестов фильтрации list-эндпоинта.
"""
from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from shared.enums import PromocodeDiscountType
from shared.models.promocode import Promocode


def _rand_code(prefix: str = "TEST") -> str:
    # короткий суффикс, чтобы не нарваться на unique-collision между тестами
    return f"{prefix}{secrets.token_hex(4).upper()}"


def make_promocode(session: Session, **overrides: Any) -> Promocode:
    """Создаёт Promocode с дефолтами: PERCENT 10%, без valid_*, is_active=False.

    Всё можно переопределить через kwargs.
    """
    defaults: dict[str, Any] = {
        "id": uuid.uuid4(),
        "code": _rand_code(),
        "discount_type": PromocodeDiscountType.PERCENT,
        "discount_value": 10,
        "min_order_amount": 0,
        "valid_from": None,
        "valid_until": None,
        "max_uses": None,
        "max_uses_per_user": None,
        "current_uses": 0,
        "is_active": False,
    }
    defaults.update(overrides)
    # code всегда в upper — имитируем серверную канонизацию для тестовых данных
    defaults["code"] = str(defaults["code"]).upper()
    promo = Promocode(**defaults)
    session.add(promo)
    session.flush()
    return promo


def seed_promocodes_across_states(
    session: Session,
    now: datetime | None = None,
) -> dict[str, list[uuid.UUID]]:
    """Сеет по одному промокоду в каждом из 4-х computed-state бакетов.

    Возвращает {'inactive': [...], 'active': [...], 'expired': [...], 'exhausted': [...]}.
    """
    if now is None:
        now = datetime.now(UTC)
    past = now - timedelta(days=1)
    future = now + timedelta(days=7)

    inactive = make_promocode(
        session,
        code=_rand_code("INACT"),
        is_active=False,
        valid_until=future,
    )
    active = make_promocode(
        session,
        code=_rand_code("ACT"),
        is_active=True,
        valid_from=past,
        valid_until=future,
        max_uses=10,
        current_uses=0,
    )
    expired = make_promocode(
        session,
        code=_rand_code("EXP"),
        is_active=True,
        valid_from=past - timedelta(days=30),
        valid_until=past,
        max_uses=10,
        current_uses=0,
    )
    exhausted = make_promocode(
        session,
        code=_rand_code("EXH"),
        is_active=True,
        valid_from=past,
        valid_until=future,
        max_uses=5,
        current_uses=5,
    )

    session.commit()
    return {
        "inactive": [inactive.id],
        "active": [active.id],
        "expired": [expired.id],
        "exhausted": [exhausted.id],
    }
