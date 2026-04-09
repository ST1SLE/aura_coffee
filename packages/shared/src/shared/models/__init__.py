from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from shared.models.user import User  # noqa: E402
from shared.models.user_profile import UserProfile  # noqa: E402
from shared.models.loyalty_account import LoyaltyAccount  # noqa: E402
from shared.models.staff_account import StaffAccount  # noqa: E402

__all__ = ["Base", "User", "UserProfile", "LoyaltyAccount", "StaffAccount"]
