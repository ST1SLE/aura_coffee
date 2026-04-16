"""RED: smoke test для публичной поверхности пакета core_api.services.validators.

Проверяет, что GREEN-код шлёт правильный `__init__.py` (re-export пяти
публичных валидаторов) и что `validators/exceptions.py` определяет пять
domain-классов ошибок, которые наследуются от общей базы ValidationError.
"""
from __future__ import annotations


def test_validators_package_exports_public_names() -> None:
    from core_api.services.validators import (
        validate_delivery_address,
        validate_min_delivery_amount,
        validate_promocode,
        validate_stop_list,
        validate_time_slot,
    )

    assert callable(validate_stop_list)
    assert callable(validate_time_slot)
    assert callable(validate_delivery_address)
    assert callable(validate_min_delivery_amount)
    assert callable(validate_promocode)


def test_validators_exceptions_module_exports_error_classes() -> None:
    from core_api.services.validators.exceptions import (
        DeliveryRadiusError,
        MinimumDeliveryAmountError,
        PromocodeValidationError,
        StopListError,
        TimeSlotValidationError,
    )

    assert issubclass(StopListError, Exception)
    assert issubclass(PromocodeValidationError, Exception)
    assert issubclass(MinimumDeliveryAmountError, Exception)
    assert issubclass(DeliveryRadiusError, Exception)
    assert issubclass(TimeSlotValidationError, Exception)


def test_validators_exceptions_share_base_class() -> None:
    """Общая база ValidationError для catch-all в router-слое."""
    from core_api.services.validators.exceptions import (
        DeliveryRadiusError,
        MinimumDeliveryAmountError,
        PromocodeValidationError,
        StopListError,
        TimeSlotValidationError,
        ValidationError,
    )

    assert issubclass(StopListError, ValidationError)
    assert issubclass(PromocodeValidationError, ValidationError)
    assert issubclass(MinimumDeliveryAmountError, ValidationError)
    assert issubclass(DeliveryRadiusError, ValidationError)
    assert issubclass(TimeSlotValidationError, ValidationError)
