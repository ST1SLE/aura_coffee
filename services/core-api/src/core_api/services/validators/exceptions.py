"""Domain-level ошибки валидаторов заказа и прайсинга.

Поднимаются валидаторами и pure-функциями прайсинга; конвертируются в HTTP
(400/409) на уровне роутера в отдельном change.
"""
from __future__ import annotations


class ValidationError(Exception):
    """База для всех доменных ошибок валидации заказа/прайсинга."""


class StopListError(ValidationError):
    """Позиция недоступна (stop-list) — INV-006."""

    def __init__(self, message: str, *, item_id: int | None = None) -> None:
        super().__init__(message)
        self.item_id = item_id


class PromocodeValidationError(ValidationError):
    """Промокод не прошёл проверки — PDD §5.2."""


class MinimumDeliveryAmountError(ValidationError):
    """Сумма заказа ниже min_delivery_amount — PDD §7.4 шаг 1, INV-009."""


class DeliveryRadiusError(ValidationError):
    """Адрес вне delivery_radius_km — PDD §7.3 шаг 3, INV-008."""


class TimeSlotValidationError(ValidationError):
    """Временной слот невалиден — PDD §7.5."""
