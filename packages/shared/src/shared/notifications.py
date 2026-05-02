"""Pure order-status notification text helpers (PDD §6.1 / §8.2)."""

# START_MODULE_CONTRACT
#   PURPOSE: Shared, side-effect-free notification matrix for order-status
#            messages and SMS bodies. Core API and payment-worker both use this
#            module so notification wording and SMS-required decisions do not
#            drift across service boundaries.
#   SCOPE:   NotificationText, resolve_notification_text, build_sms_body.
#   DEPENDS: dataclasses, shared.enums.
#   LINKS:   docs/development-plan.xml M-SHARED, PDD §6.1, §7.8, §8.2,
#            INV-016.
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   NotificationText          - resolved bilingual message + SMS metadata
#   resolve_notification_text - lookup PDD §6.1 order-notification matrix
#   build_sms_body            - canonical short SMS body formatter
# END_MODULE_MAP

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from shared.enums import OrderStatus, OrderType

CancelledBy = Literal["customer", "admin", "payment"]


# START_CONTRACT: NotificationText
#   PURPOSE: Resolved notification text bundle: bilingual in-app/SMS row
#            messages, optional SMS-status phrases, and SMS-required flag.
#   INPUTS:  message_ru, message_en, sms_status_ru, sms_status_en, requires_sms.
#   OUTPUTS: frozen dataclass instance.
#   SIDE_EFFECTS: none.
# END_CONTRACT: NotificationText
@dataclass(frozen=True)
class NotificationText:
    message_ru: str
    message_en: str
    sms_status_ru: str | None
    sms_status_en: str | None
    requires_sms: bool


# Key: (new_status, order_type, cancelled_by).
# Value: (message_ru, message_en, sms_status_ru, sms_status_en, requires_sms).
# `{short_id}` is formatted by resolve_notification_text.
_MATRIX: dict[
    tuple[OrderStatus, OrderType | None, CancelledBy | None],
    tuple[str, str, str | None, str | None, bool],
] = {
    (OrderStatus.PAID, None, None): (
        "Заказ №{short_id} оплачен",
        "Order #{short_id} paid",
        "Оплачен",
        "Paid",
        True,
    ),
    (OrderStatus.PREPARING, None, None): (
        "Заказ №{short_id} готовится",
        "Order #{short_id} is being prepared",
        "Готовится",
        "Being prepared",
        True,
    ),
    (OrderStatus.READY, OrderType.PICKUP, None): (
        "Заказ №{short_id} готов, заберите",
        "Order #{short_id} is ready, please pick it up",
        "Готов, заберите",
        "Ready, pick up",
        True,
    ),
    (OrderStatus.READY, OrderType.DELIVERY, None): (
        "Заказ №{short_id} готов",
        "Order #{short_id} is ready",
        "Готов",
        "Ready",
        True,
    ),
    (OrderStatus.IN_DELIVERY, None, None): (
        "Курьер забрал заказ №{short_id}",
        "Courier picked up order #{short_id}",
        None,
        None,
        False,
    ),
    (OrderStatus.COMPLETED, OrderType.PICKUP, None): (
        "Заказ №{short_id} завершён",
        "Order #{short_id} completed",
        None,
        None,
        False,
    ),
    (OrderStatus.COMPLETED, OrderType.DELIVERY, None): (
        "Заказ №{short_id} доставлен",
        "Order #{short_id} delivered",
        "Доставлен",
        "Delivered",
        True,
    ),
    (OrderStatus.CANCELLED, None, "customer"): (
        "Заказ №{short_id} отменён, средства возвращены",
        "Order #{short_id} cancelled, funds refunded",
        "Отменён, средства возвращены",
        "Cancelled, funds refunded",
        True,
    ),
    (OrderStatus.CANCELLED, None, "admin"): (
        "Заказ №{short_id} отменён кофейней",
        "Order #{short_id} cancelled by the coffee shop",
        "Отменён кофейней",
        "Cancelled by the coffee shop",
        True,
    ),
    (OrderStatus.CANCELLED, None, "payment"): (
        "Платёж не прошёл. Заказ №{short_id} отменён",
        "Payment failed. Order #{short_id} canceled",
        "Платёж не прошёл",
        "Payment failed",
        True,
    ),
}

_TYPE_DEPENDENT_STATUSES = {OrderStatus.READY, OrderStatus.COMPLETED}


# START_CONTRACT: resolve_notification_text
#   PURPOSE: Look up the PDD §6.1 notification cell for an order status and
#            return formatted bilingual text. Unknown cells raise ValueError,
#            preserving INV-016.
#   INPUTS:  new_status: OrderStatus
#            order_type: OrderType
#            cancelled_by: customer | admin | payment | None
#            short_id: str
#   OUTPUTS: NotificationText.
#   SIDE_EFFECTS: none.
#   LINKS:   PDD §6.1, §7.8, INV-016.
# END_CONTRACT: resolve_notification_text
def resolve_notification_text(
    new_status: OrderStatus,
    order_type: OrderType,
    cancelled_by: CancelledBy | None,
    short_id: str,
) -> NotificationText:
    if new_status == OrderStatus.CANCELLED:
        if cancelled_by not in ("customer", "admin", "payment"):
            raise ValueError(
                "CANCELLED requires cancelled_by in "
                "('customer', 'admin', 'payment')"
            )
        key = (new_status, None, cancelled_by)
    elif new_status in _TYPE_DEPENDENT_STATUSES:
        key = (new_status, order_type, None)
    else:
        key = (new_status, None, None)

    entry = _MATRIX.get(key)
    if entry is None:
        raise ValueError(
            f"No notification defined for transition: "
            f"status={new_status}, order_type={order_type}, cancelled_by={cancelled_by}"
        )

    tpl_ru, tpl_en, sms_ru, sms_en, requires_sms = entry
    return NotificationText(
        message_ru=tpl_ru.format(short_id=short_id),
        message_en=tpl_en.format(short_id=short_id),
        sms_status_ru=sms_ru,
        sms_status_en=sms_en,
        requires_sms=requires_sms,
    )


# START_CONTRACT: build_sms_body
#   PURPOSE: Format the canonical short SMS body.
#   INPUTS:  status_text: str — localized status phrase
#            short_id: str — first 8 hex chars of order UUID.
#   OUTPUTS: str — `{status_text}. Заказ №{short_id}. Aura Coffee`.
#   SIDE_EFFECTS: none.
#   LINKS:   PDD §8.2.
# END_CONTRACT: build_sms_body
def build_sms_body(status_text: str, short_id: str) -> str:
    return f"{status_text}. Заказ №{short_id}. Aura Coffee"
