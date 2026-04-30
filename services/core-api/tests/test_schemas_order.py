"""RED: тесты Pydantic-схем Phase 3.

Покрывают:
- core_api.schemas.order — CreateOrderRequest, OrderItemResponse, OrderResponse,
  OrderListResponse, OrderStatusUpdate, CancelOrderRequest, RepeatOrderResult.
- core_api.schemas.shop_settings — ShopSettingsResponse.

Все импорты целевых схем выполняются ВНУТРИ тел тестов: на RED эти модули
ещё не существуют, и верхнеуровневый импорт сорвал бы сбор всего файла.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import BaseModel, ValidationError


# ---------------------------------------------------------------------------
# 7.1–7.2 Существование схем
# ---------------------------------------------------------------------------

def test_order_schemas_exist() -> None:
    from core_api.schemas.order import (
        CancelOrderRequest,
        CreateOrderRequest,
        OrderItemResponse,
        OrderListResponse,
        OrderResponse,
        OrderStatusUpdate,
        RepeatOrderResult,
    )

    for cls in (
        CancelOrderRequest,
        CreateOrderRequest,
        OrderItemResponse,
        OrderListResponse,
        OrderResponse,
        OrderStatusUpdate,
        RepeatOrderResult,
    ):
        assert issubclass(cls, BaseModel), f"{cls.__name__} должен быть BaseModel"


def test_shop_settings_schema_exists() -> None:
    from core_api.schemas.shop_settings import ShopSettingsResponse

    assert issubclass(ShopSettingsResponse, BaseModel)


# ---------------------------------------------------------------------------
# 7.3–7.6 CreateOrderRequest
# ---------------------------------------------------------------------------

def test_create_order_request_accepts_minimal_pickup() -> None:
    from shared.enums import OrderType
    from core_api.schemas.order import CreateOrderRequest

    req = CreateOrderRequest(type="pickup")
    assert req.type == OrderType.PICKUP
    assert req.points_to_use == 0
    assert req.delivery_address is None
    assert req.requested_time is None
    assert req.promocode_code is None


def test_create_order_request_rejects_unknown_type() -> None:
    from core_api.schemas.order import CreateOrderRequest

    with pytest.raises(ValidationError):
        CreateOrderRequest(type="takeaway")


def test_create_order_request_accepts_delivery_with_address() -> None:
    from shared.enums import OrderType
    from core_api.schemas.order import CreateOrderRequest

    payload = {
        "type": "delivery",
        "delivery_address": {
            "text": "Москва, Тверская 1",
            "lat": 55.7558,
            "lon": 37.6173,
            "apartment": "12",
            "entrance": "3",
            "floor": "4",
            "comment": "домофон не работает",
        },
    }
    req = CreateOrderRequest(**payload)
    assert req.type == OrderType.DELIVERY
    assert req.delivery_address is not None
    assert req.delivery_address.text == "Москва, Тверская 1"
    assert req.delivery_address.lat == 55.7558
    assert req.delivery_address.lon == 37.6173
    assert req.delivery_address.apartment == "12"
    assert req.delivery_address.entrance == "3"
    assert req.delivery_address.floor == "4"
    assert req.delivery_address.comment == "домофон не работает"


def test_create_order_request_rejects_negative_points_to_use() -> None:
    from core_api.schemas.order import CreateOrderRequest

    with pytest.raises(ValidationError):
        CreateOrderRequest(type="pickup", points_to_use=-1)


# ---------------------------------------------------------------------------
# 7.7 OrderItemResponse
# ---------------------------------------------------------------------------

def test_order_item_response_round_trip_from_namespace() -> None:
    from core_api.schemas.order import OrderItemResponse

    ns = SimpleNamespace(
        menu_item_name_ru="Латте",
        menu_item_name_en="Latte",
        size_label="M",
        unit_price=35000,
        modifiers_snapshot=[
            {"modifier_id": str(uuid4()), "name_ru": "Сироп", "name_en": "Syrup", "price": 5000}
        ],
        quantity=2,
        line_total=80000,
    )
    resp = OrderItemResponse.model_validate(ns)
    assert resp.menu_item_name_ru == "Латте"
    assert resp.menu_item_name_en == "Latte"
    assert resp.size_label == "M"
    assert resp.unit_price == 35000
    assert resp.quantity == 2
    assert resp.line_total == 80000
    assert isinstance(resp.modifiers_snapshot, list)
    assert resp.modifiers_snapshot[0]["name_ru"] == "Сироп"


# ---------------------------------------------------------------------------
# 7.8 OrderResponse
# ---------------------------------------------------------------------------

def test_order_response_round_trip_from_namespace() -> None:
    from core_api.schemas.order import OrderResponse

    order_id = uuid4()
    now = datetime.now(UTC)
    ns = SimpleNamespace(
        id=order_id,
        status="created",
        type="pickup",
        items=[],
        subtotal=35000,
        discount_amount=0,
        points_used=0,
        delivery_fee=0,
        total=35000,
        estimated_accrual=1750,
        confirmation_url=None,
        requested_time=None,
        estimated_ready_at=None,
        cancelled_by=None,
        cancelled_at=None,
        created_at=now,
    )
    resp = OrderResponse.model_validate(ns)
    assert resp.id == order_id
    assert resp.total == 35000
    assert resp.estimated_accrual == 1750
    assert resp.items == []


# ---------------------------------------------------------------------------
# 7.9 OrderListResponse
# ---------------------------------------------------------------------------

def test_order_list_response_schema() -> None:
    from core_api.schemas.order import OrderListResponse

    resp = OrderListResponse(items=[], total_count=0, page=1, per_page=20)
    assert resp.total_count == 0
    assert resp.page == 1
    assert resp.per_page == 20
    assert resp.items == []


# ---------------------------------------------------------------------------
# 7.10 OrderStatusUpdate
# ---------------------------------------------------------------------------

def test_order_status_update_schema() -> None:
    from shared.enums import OrderStatus
    from core_api.schemas.order import OrderStatusUpdate

    upd = OrderStatusUpdate(new_status="preparing")
    assert upd.new_status == OrderStatus.PREPARING


# ---------------------------------------------------------------------------
# 7.11 CancelOrderRequest
# ---------------------------------------------------------------------------

def test_cancel_order_request_schema() -> None:
    from core_api.schemas.order import CancelOrderRequest

    default_req = CancelOrderRequest()
    assert default_req.reason is None

    with_reason = CancelOrderRequest(reason="клиент передумал")
    assert with_reason.reason == "клиент передумал"


# ---------------------------------------------------------------------------
# 7.12 RepeatOrderResult
# ---------------------------------------------------------------------------

def test_repeat_order_result_schema() -> None:
    from core_api.schemas.order import RepeatOrderResult

    resp = RepeatOrderResult(
        added_to_cart=3,
        skipped=[{"name": "Латте", "reason": "stop_list"}],
    )
    assert resp.added_to_cart == 3
    assert len(resp.skipped) == 1
    skipped_item = resp.skipped[0]
    name = getattr(skipped_item, "name", None) or skipped_item["name"]
    reason = getattr(skipped_item, "reason", None) or skipped_item["reason"]
    assert name == "Латте"
    assert reason == "stop_list"


# ---------------------------------------------------------------------------
# 7.13 ShopSettingsResponse
# ---------------------------------------------------------------------------

def test_shop_settings_response_round_trip() -> None:
    from core_api.schemas.shop_settings import ShopSettingsResponse

    now = datetime.now(UTC)
    ns = SimpleNamespace(
        shop_lat=55.7558,
        shop_lon=37.6173,
        delivery_radius_km=5,
        min_delivery_amount=50000,
        free_delivery_threshold=150000,
        delivery_fee=20000,
        loyalty_percent=5,
        default_prep_time_minutes=15,
        estimated_delivery_time_minutes=30,
        auto_close_minutes=10,
        working_hours={
            "mon": {"open": "08:00", "close": "22:00"},
            "tue": {"open": "08:00", "close": "22:00"},
            "wed": {"open": "08:00", "close": "22:00"},
            "thu": {"open": "08:00", "close": "22:00"},
            "fri": {"open": "08:00", "close": "22:00"},
            "sat": {"open": "08:00", "close": "22:00"},
            "sun": {"open": "08:00", "close": "22:00"},
        },
        updated_at=now,
    )
    resp = ShopSettingsResponse.model_validate(ns)
    assert float(resp.shop_lat) == 55.7558
    assert float(resp.shop_lon) == 37.6173
    assert int(resp.delivery_radius_km) == 5
    assert resp.min_delivery_amount == 50000
    assert resp.free_delivery_threshold == 150000
    assert resp.delivery_fee == 20000
    assert resp.loyalty_percent == 5
    assert resp.default_prep_time_minutes == 15
    assert resp.estimated_delivery_time_minutes == 30
    assert resp.auto_close_minutes == 10
    assert set(resp.working_hours.keys()) == {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
