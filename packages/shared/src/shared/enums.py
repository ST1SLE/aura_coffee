# START_MODULE_CONTRACT
#   PURPOSE: Canonical string-valued enums for every domain state machine in the
#            Aura Coffee system; values are the source of truth for INV-016
#            exhaustive transitions and must match PDD §6.x verbatim.
#   SCOPE:   Pure data types — no business logic, no IO. Imported by ORM models
#            in shared.models and by services (core-api, payment-worker, sms-worker)
#            wherever a status is read or written.
#   DEPENDS: stdlib enum only.
#   LINKS:   PDD §6.1 (OrderStatus), §6.2 (PaymentStatus, RefundStatus),
#            §6.3 (DeliveryAssignmentStatus), §6.4 (OTPStatus, UserStatus),
#            §3 (domain language for OrderType, StaffRole, CategoryType, etc.),
#            docs/development-plan.xml M-SHARED, INV-016.
#   ROLE:    TYPES
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   UserStatus                 - lifecycle of a User account (PDD §6.4)
#   OTPStatus                  - lifecycle of an OTP challenge (PDD §6.4)
#   StaffRole                  - admin/barista/courier role for StaffAccount
#   CategoryType               - menu category kind: drink/food/merch/modifier
#   MenuItemAvailability       - menu item availability state
#   MenuMediaType              - presentational menu media type: image/video
#   SizeLabel                  - size label S/M/L for SizeOption
#   OrderStatus                - lifecycle of an Order (PDD §6.1, INV-016)
#   OrderType                  - pickup vs delivery order kind (PDD §3)
#   PaymentStatus              - lifecycle of a Payment (PDD §6.2, INV-016)
#   RefundStatus               - lifecycle of a Refund (PDD §6.2)
#   NotificationChannel        - in_app or sms channel for Notification
#   NotificationType           - kind of notification (order status / OTP)
#   NotificationStatus         - delivery state of a Notification
#   LoyaltyTransactionType     - kind of loyalty ledger entry (PDD §5.2)
#   PromocodeDiscountType      - percent vs fixed_amount discount kind
#   DeliveryAssignmentStatus   - lifecycle of a DeliveryAssignment (PDD §6.3, INV-016)
# END_MODULE_MAP

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


class MenuMediaType(str, enum.Enum):
    IMAGE = "image"
    VIDEO = "video"


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
