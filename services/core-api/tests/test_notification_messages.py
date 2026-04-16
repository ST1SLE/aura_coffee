"""RED-фаза: замороженная матрица текстов уведомлений (PDD §6.1, §8.2).

Здесь пинтуются ДОСЛОВНО:
- IN_APP-тексты (RU/EN) — «дружелюбный» формат, включает «Заказ №{short_id} ...»
- SMS status_text (RU/EN) — короткая фраза без reference на заказ, которую
  build_sms_body оборачивает по §8.2: "{status_text}. Заказ №{short_id}. Aura Coffee"
- requires_sms — флаг необходимости отправки SMS по §6.1.

Такое разделение необходимо: §8.2 требует SMS ≤ 70 символов, и дублирование
«Заказ №{short_id}» делает это недостижимым для длинных статусов (например,
`CANCELLED, customer`).
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from shared.enums import OrderStatus, OrderType


@dataclass(frozen=True)
class Case:
    new_status: OrderStatus
    order_type: OrderType
    cancelled_by: str | None
    # IN_APP (включает short_id в фразу)
    message_ru: str
    message_en: str
    # SMS status_text (короткая статус-фраза; build_sms_body добавит short_id и суффикс)
    sms_status_ru: str | None
    sms_status_en: str | None
    requires_sms: bool


MATRIX: list[Case] = [
    Case(OrderStatus.PAID, OrderType.PICKUP, None,
         "Заказ №{short_id} оплачен", "Order #{short_id} paid",
         "Оплачен", "Paid", True),
    Case(OrderStatus.PREPARING, OrderType.PICKUP, None,
         "Заказ №{short_id} готовится", "Order #{short_id} is being prepared",
         "Готовится", "Being prepared", True),
    Case(OrderStatus.READY, OrderType.PICKUP, None,
         "Заказ №{short_id} готов, заберите", "Order #{short_id} is ready, please pick it up",
         "Готов, заберите", "Ready, pick up", True),
    Case(OrderStatus.READY, OrderType.DELIVERY, None,
         "Заказ №{short_id} готов", "Order #{short_id} is ready",
         "Готов", "Ready", True),
    Case(OrderStatus.IN_DELIVERY, OrderType.DELIVERY, None,
         "Курьер забрал заказ №{short_id}", "Courier picked up order #{short_id}",
         None, None, False),
    Case(OrderStatus.COMPLETED, OrderType.PICKUP, None,
         "Заказ №{short_id} завершён", "Order #{short_id} completed",
         None, None, False),
    Case(OrderStatus.COMPLETED, OrderType.DELIVERY, None,
         "Заказ №{short_id} доставлен", "Order #{short_id} delivered",
         "Доставлен", "Delivered", True),
    Case(OrderStatus.CANCELLED, OrderType.PICKUP, "customer",
         "Заказ №{short_id} отменён, средства возвращены",
         "Order #{short_id} cancelled, funds refunded",
         "Отменён, средства возвращены", "Cancelled, funds refunded", True),
    Case(OrderStatus.CANCELLED, OrderType.PICKUP, "admin",
         "Заказ №{short_id} отменён кофейней",
         "Order #{short_id} cancelled by the coffee shop",
         "Отменён кофейней", "Cancelled by the coffee shop", True),
]

IDS = [
    "paid", "preparing", "ready-pickup", "ready-delivery",
    "in-delivery", "completed-pickup", "completed-delivery",
    "cancelled-customer", "cancelled-admin",
]

SHORT_ID = "c0ffee11"


def test_matrix_has_nine_cases() -> None:
    """7.1 — матрица покрывает 9 §6.1-кейсов."""
    assert len(MATRIX) == 9


@pytest.mark.parametrize("case", MATRIX, ids=IDS)
def test_resolve_notification_text_returns_frozen_ru(case: Case) -> None:
    """7.2 — IN_APP message_ru совпадает с PDD §6.1 + short_id."""
    from core_api.services.notification import resolve_notification_text

    result = resolve_notification_text(
        new_status=case.new_status,
        order_type=case.order_type,
        cancelled_by=case.cancelled_by,
        short_id=SHORT_ID,
    )
    expected = case.message_ru.format(short_id=SHORT_ID)
    assert result.message_ru == expected


@pytest.mark.parametrize("case", MATRIX, ids=IDS)
def test_resolve_notification_text_returns_frozen_en(case: Case) -> None:
    """7.3 — IN_APP message_en совпадает с зафиксированным EN-вариантом."""
    from core_api.services.notification import resolve_notification_text

    result = resolve_notification_text(
        new_status=case.new_status,
        order_type=case.order_type,
        cancelled_by=case.cancelled_by,
        short_id=SHORT_ID,
    )
    expected = case.message_en.format(short_id=SHORT_ID)
    assert result.message_en == expected
    assert result.message_ru != result.message_en


@pytest.mark.parametrize("case", MATRIX, ids=IDS)
def test_resolve_notification_text_requires_sms_flag(case: Case) -> None:
    """7.4 — requires_sms соответствует матрице §6.1."""
    from core_api.services.notification import resolve_notification_text

    result = resolve_notification_text(
        new_status=case.new_status,
        order_type=case.order_type,
        cancelled_by=case.cancelled_by,
        short_id=SHORT_ID,
    )
    assert result.requires_sms is case.requires_sms


@pytest.mark.parametrize("case", MATRIX, ids=IDS)
def test_resolve_notification_text_returns_sms_status(case: Case) -> None:
    """7.4b — resolve возвращает sms_status_ru/en для SMS-кейсов, None иначе."""
    from core_api.services.notification import resolve_notification_text

    result = resolve_notification_text(
        new_status=case.new_status,
        order_type=case.order_type,
        cancelled_by=case.cancelled_by,
        short_id=SHORT_ID,
    )
    assert result.sms_status_ru == case.sms_status_ru
    assert result.sms_status_en == case.sms_status_en


@pytest.mark.parametrize(
    "case",
    [c for c in MATRIX if c.requires_sms],
    ids=[i for c, i in zip(MATRIX, IDS, strict=True) if c.requires_sms],
)
def test_sms_body_length_is_within_one_cyrillic_segment(case: Case) -> None:
    """7.5 — длина SMS-тела ≤ 70 символов (§8.2, 1 кириллический сегмент)."""
    from core_api.services.notification import build_sms_body

    short_id = "abcdef01"  # полная длина 8 hex
    assert case.sms_status_ru is not None
    body = build_sms_body(status_text=case.sms_status_ru, short_id=short_id)
    assert len(body) <= 70, f"{case!r}: len={len(body)} body={body!r}"
    assert body.endswith(". Aura Coffee")
    assert f"Заказ №{short_id}" in body


def test_sms_body_substitutes_short_id() -> None:
    """7.6 — формат «{status_text}. Заказ №{short_id}. Aura Coffee»."""
    from core_api.services.notification import build_sms_body

    body = build_sms_body(status_text="Оплачен", short_id="c0ffee11")
    assert body == "Оплачен. Заказ №c0ffee11. Aura Coffee"
