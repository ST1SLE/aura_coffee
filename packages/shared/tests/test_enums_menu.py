"""RED: тесты для enum-ов меню в shared.enums.

Все тесты ДОЛЖНЫ падать с ImportError до добавления enum-ов в enums.py.
"""

import pytest


def test_category_type_values() -> None:
    from shared.enums import CategoryType

    members = {m.name: m.value for m in CategoryType}
    assert members == {
        "DRINK": "drink",
        "FOOD": "food",
        "MERCH": "merch",
        "MODIFIER": "modifier",
    }


def test_size_label_values() -> None:
    from shared.enums import SizeLabel

    members = {m.name: m.value for m in SizeLabel}
    assert members == {"S": "S", "M": "M", "L": "L"}


def test_menu_item_availability_values() -> None:
    from shared.enums import MenuItemAvailability

    members = {m.name: m.value for m in MenuItemAvailability}
    assert members == {
        "AVAILABLE": "available",
        "STOP_LIST": "stop_list",
        "ARCHIVED": "archived",
    }


def test_menu_media_type_values() -> None:
    from shared.enums import MenuMediaType

    members = {m.name: m.value for m in MenuMediaType}
    assert members == {
        "IMAGE": "image",
        "VIDEO": "video",
    }
