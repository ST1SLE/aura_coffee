from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from shared.models.user import User  # noqa: E402
from shared.models.user_profile import UserProfile  # noqa: E402
from shared.models.loyalty_account import LoyaltyAccount  # noqa: E402
from shared.models.staff_account import StaffAccount  # noqa: E402
from shared.models.menu import Category, MenuItem, Modifier, SizeOption  # noqa: E402

# Phase 3: Order & Payment
from shared.models.shop_settings import ShopSettings  # noqa: E402
from shared.models.promocode import Promocode  # noqa: E402
from shared.models.order import Order  # noqa: E402
from shared.models.order_item import OrderItem  # noqa: E402
from shared.models.payment import Payment  # noqa: E402
from shared.models.refund import Refund  # noqa: E402
from shared.models.loyalty_transaction import LoyaltyTransaction  # noqa: E402
from shared.models.promocode_usage import PromocodeUsage  # noqa: E402
from shared.models.notification import Notification  # noqa: E402

# Phase 4: Delivery
from shared.models.delivery_assignment import DeliveryAssignment  # noqa: E402

__all__ = [
    "Base",
    "User",
    "UserProfile",
    "LoyaltyAccount",
    "StaffAccount",
    "Category",
    "MenuItem",
    "Modifier",
    "SizeOption",
    "ShopSettings",
    "Order",
    "OrderItem",
    "Payment",
    "Refund",
    "LoyaltyTransaction",
    "Promocode",
    "PromocodeUsage",
    "Notification",
    "DeliveryAssignment",
]
