import pytest

from core_api.utils.phone import normalize_phone


class TestNormalizePhone:
    def test_valid_plus7(self) -> None:
        assert normalize_phone("+79161234567") == "+79161234567"

    def test_valid_8_prefix(self) -> None:
        assert normalize_phone("89161234567") == "+79161234567"

    def test_valid_7_prefix_no_plus(self) -> None:
        assert normalize_phone("79161234567") == "+79161234567"

    def test_with_spaces_and_dashes(self) -> None:
        assert normalize_phone("+7 916 123-45-67") == "+79161234567"

    def test_with_parens(self) -> None:
        assert normalize_phone("+7(916)1234567") == "+79161234567"

    def test_invalid_short(self) -> None:
        with pytest.raises(ValueError):
            normalize_phone("12345")

    def test_invalid_non_russian(self) -> None:
        with pytest.raises(ValueError):
            normalize_phone("+14155551234")

    def test_invalid_too_long(self) -> None:
        with pytest.raises(ValueError):
            normalize_phone("+791612345678")
