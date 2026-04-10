import enum


class UserStatus(str, enum.Enum):
    PENDING_VERIFICATION = "pending_verification"
    ACTIVE = "active"
    BLOCKED = "blocked"
    DELETED = "deleted"


class OTPStatus(str, enum.Enum):
    CREATED = "created"
    SENT = "sent"
    VERIFIED = "verified"
    EXPIRED = "expired"
    FAILED = "failed"


class StaffRole(str, enum.Enum):
    ADMIN = "admin"
    BARISTA = "barista"
    COURIER = "courier"


# Menu

class CategoryType(str, enum.Enum):
    DRINK = "drink"
    FOOD = "food"
    MERCH = "merch"
    MODIFIER = "modifier"


class MenuItemAvailability(str, enum.Enum):
    AVAILABLE = "available"
    STOP_LIST = "stop_list"
    ARCHIVED = "archived"


class SizeLabel(str, enum.Enum):
    S = "S"
    M = "M"
    L = "L"
