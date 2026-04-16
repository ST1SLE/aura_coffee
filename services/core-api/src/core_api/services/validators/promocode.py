"""Promocode validator — PDD §5.2 «Примечания», INV-011.

validate_promocode(code, user_id, subtotal, db_session) → Promocode | raises.

Запускает 7-шаговую проверочную цепочку; все нарушения — PromocodeValidationError.
Атомарность (INV-004) — забота checkout-оркестратора; здесь только чтение.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from shared.models.promocode import Promocode
from shared.models.promocode_usage import PromocodeUsage

from .exceptions import PromocodeValidationError


def validate_promocode(
    code: str,
    user_id: uuid.UUID,
    subtotal: int,
    db_session: Session,
) -> Promocode:
    """Возвращает валидный Promocode ORM-инстанс или поднимает PromocodeValidationError."""
    promo = db_session.query(Promocode).filter(Promocode.code == code).first()
    if promo is None:
        raise PromocodeValidationError(f"Unknown promocode: {code}")

    if not promo.is_active:
        raise PromocodeValidationError("Promocode is inactive")

    now = datetime.now(UTC)
    if promo.valid_from is not None and now < promo.valid_from:
        raise PromocodeValidationError("Promocode is not yet valid")
    if promo.valid_until is not None and now > promo.valid_until:
        raise PromocodeValidationError("Promocode has expired")

    if promo.max_uses is not None and promo.current_uses >= promo.max_uses:
        raise PromocodeValidationError("Global quota exhausted")

    if promo.max_uses_per_user is not None:
        count = (
            db_session.query(PromocodeUsage)
            .filter(
                PromocodeUsage.promocode_id == promo.id,
                PromocodeUsage.user_id == user_id,
            )
            .count()
        )
        if count >= promo.max_uses_per_user:
            raise PromocodeValidationError("Per-user quota exhausted")

    min_order_amount = int(promo.min_order_amount or 0)
    if subtotal < min_order_amount:
        raise PromocodeValidationError(
            f"subtotal {subtotal} below min_order_amount {min_order_amount}",
        )

    return promo
