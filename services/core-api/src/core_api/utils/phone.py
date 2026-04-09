import re

_PHONE_PATTERN = re.compile(r"^\+7\d{10}$")


def normalize_phone(phone: str) -> str:
    """Нормализация телефона в формат E.164 (+7XXXXXXXXXX)."""
    digits = re.sub(r"[\s\-\(\)]+", "", phone)

    if digits.startswith("8") and len(digits) == 11:
        digits = "+7" + digits[1:]
    elif digits.startswith("7") and len(digits) == 11:
        digits = "+" + digits
    elif not digits.startswith("+"):
        digits = "+" + digits

    if not _PHONE_PATTERN.match(digits):
        raise ValueError(f"Invalid phone number: {phone}")

    return digits
