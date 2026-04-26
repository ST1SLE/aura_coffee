# START_MODULE_CONTRACT
#   PURPOSE: Define the SQLAlchemy DeclarativeBase shared by every ORM model
#            and re-export the concrete model classes so callers can do
#            `from shared.models import Order, Payment, ...` without
#            knowing the per-file layout.
#   SCOPE:   Aggregator + DeclarativeBase root only — no business logic, no IO.
#            Each individual ORM class lives in its own module file.
#   DEPENDS: SQLAlchemy 2.x DeclarativeBase; the per-entity modules in this
#            package (user, user_profile, delivery_address, loyalty_account,
#            staff_account, menu, shop_settings, promocode, order, order_item,
#            payment, refund, loyalty_transaction, promocode_usage,
#            notification, delivery_assignment).
#   LINKS:   PDD §5.2 (data model), docs/development-plan.xml M-SHARED,
#            INV-013 (PII isolation), INV-014 (order_items immutability),
#            INV-016 (state-machine exhaustiveness).
#   ROLE:    TYPES
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   Base                - SQLAlchemy DeclarativeBase shared by every ORM class
#   User                - users table (PDD §5.2, §6.4 lifecycle)
#   UserProfile         - PII-bearing profile (INV-013, separate row from User)
#   DeliveryAddress     - saved customer address with default uniqueness index
#   LoyaltyAccount      - per-user points balance (PDD §5.2)
#   StaffAccount        - admin/barista/courier login record
#   Category            - menu category (PDD §5.2)
#   MenuItem            - sellable menu item
#   Modifier            - menu item modifier
#   SizeOption          - size+price option attached to MenuItem
#   ShopSettings        - singleton row of shop-wide settings
#   Order               - order header (PDD §5.2, §6.1)
#   OrderItem           - immutable order line snapshot (INV-014, PDD §7.7)
#   Payment             - 1:1 YuKassa payment for an Order (PDD §6.2)
#   Refund              - YuKassa refund linked to Payment (PDD §6.2)
#   LoyaltyTransaction  - points ledger entry (PDD §5.2)
#   Promocode           - promotional code definition
#   PromocodeUsage      - per-order record that a promocode was applied
#   Notification        - in-app/SMS notification log
#   DeliveryAssignment  - courier↔order assignment (PDD §6.3, INV-016)
# END_MODULE_MAP

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from shared.models.user import User  # noqa: E402
from shared.models.user_profile import UserProfile  # noqa: E402
from shared.models.delivery_address import DeliveryAddress  # noqa: E402
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
    "DeliveryAddress",
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
