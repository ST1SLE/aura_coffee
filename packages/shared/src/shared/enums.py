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


# Phase 3: Order & Payment

class OrderStatus(str, enum.Enum):
    CREATED = "created"
    PAID = "paid"
    PREPARING = "preparing"
    READY = "ready"
    IN_DELIVERY = "in_delivery"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class OrderType(str, enum.Enum):
    PICKUP = "pickup"
    DELIVERY = "delivery"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    SUCCEEDED = "succeeded"
    PAYMENT_FAILED = "payment_failed"
    REFUND_PENDING = "refund_pending"
    REFUNDED = "refunded"
    REFUND_FAILED = "refund_failed"


class RefundStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class NotificationChannel(str, enum.Enum):
    IN_APP = "in_app"
    SMS = "sms"


class NotificationType(str, enum.Enum):
    ORDER_STATUS_CHANGE = "order_status_change"
    OTP = "otp"


class NotificationStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class LoyaltyTransactionType(str, enum.Enum):
    ACCRUAL = "accrual"
    REDEMPTION = "redemption"
    REVERSAL = "reversal"
    RESERVATION = "reservation"
    ADMIN_ADJUSTMENT = "admin_adjustment"


class PromocodeDiscountType(str, enum.Enum):
    PERCENT = "percent"
    FIXED_AMOUNT = "fixed_amount"


# Phase 4: Delivery Assignment Lifecycle (PDD §6.3)

class DeliveryAssignmentStatus(str, enum.Enum):
    AWAITING_COURIER = "awaiting_courier"
    COURIER_ASSIGNED = "courier_assigned"
    PICKED_UP = "picked_up"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
