"""HTTP-роуты заказов (PDD §7.1 item 2).

POST /api/v1/orders — создание заказа из Redis-корзины (201 / 400 / 409 / 422 / 401 / 403).
GET  /api/v1/orders/{order_id} — деталь заказа для polling confirmation_url
                                (200 / 404 foreign-or-unknown / 401 / 403).
"""

from __future__ import annotations

# START_MODULE_CONTRACT
#   PURPOSE: HTTP routes for order creation, read-only checkout estimate, and
#            detail under /api/v1/orders (customer surface). Order placement is
#            the single atomic flow of INV-004 (cart → inventory decrement +
#            order + items + payment + points).
#   SCOPE:   POST creates an order from the Redis cart and dispatches
#            payment-worker / sms-worker tasks. POST /estimate returns
#            server-owned checkout totals without writes. GET returns own-order
#            detail for confirmation_url polling.
#   DEPENDS: M-SHARED (models.Order, OrderItem, Payment), M-DATABASE,
#            core_api.services.checkout, services.delivery_addresses,
#            core_api.deps.{auth,database,redis}.
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §6.1, §6.2, §7.1,
#            §7.2 pricing, §7.3 address, §7.4 delivery fee, §7.5 time slot,
#            INV-002, INV-004 (atomic), INV-006 (stop-list/finite inventory),
#            INV-013 (own-order only), INV-014 (order_items immutable),
#            INV-016 (state-machine).
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   orders_router  - APIRouter("/api/v1/orders", tags=["orders"])
#   post_order          - POST /api/v1/orders
#   post_order_estimate - POST /api/v1/orders/estimate
#   get_order           - GET  /api/v1/orders/{order_id}
# END_MODULE_MAP

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core_api.deps import database as _db_dep
from core_api.deps import redis as _redis_dep
from core_api.deps.auth import get_current_user
from core_api.schemas.order import (
    CreateOrderRequest,
    OrderEstimateResponse,
    OrderItemResponse,
    OrderResponse,
)
from core_api.services.checkout import (
    EmptyCartError,
    InventoryInsufficientError,
    create_order,
    estimate_order,
)
from core_api.services.delivery_addresses import DeliveryAddressNotFound
from core_api.services.validators.exceptions import MinimumDeliveryAmountError
from shared.models import Order, OrderItem, Payment

orders_router = APIRouter(prefix="/api/v1/orders", tags=["orders"])


def _minimum_delivery_error_detail(exc: MinimumDeliveryAmountError) -> dict[str, int | str]:
    return {
        "code": "minimum_delivery_amount",
        "subtotal": int(exc.subtotal or 0),
        "min_delivery_amount": int(exc.min_amount or 0),
    }


# Обёртки: обращаемся к атрибутам модуля в момент вызова — чтобы тесты
# могли патчить core_api.deps.redis.get_redis / core_api.deps.database.get_session.
def _get_redis():
    yield from _redis_dep.get_redis()


def _get_session():
    # Поддерживаем оба паттерна тестов:
    # (1) app.dependency_overrides[get_db]   — новый пакет тестов (saved-addresses);
    # (2) patch("core_api.deps.database.get_session", ...) — существующий паттерн.
    from core_api.main import app

    override = app.dependency_overrides.get(_db_dep.get_session)
    if override is not None:
        yield from override()
        return
    yield from _db_dep.get_session()


# START_CONTRACT: post_order
#   PURPOSE: Create a new order from the customer's Redis cart, validate
#            stop-list / delivery / promocode / time slot, persist
#            Order+OrderItems+Payment in a single transaction, dispatch
#            Celery tasks to payment-worker and sms-worker.
#   INPUTS:  request: CreateOrderRequest (JSON), current_user, Session,
#            Redis client.
#   OUTPUTS: 201 OrderResponse; 400 empty cart; 404 unknown delivery
#            address (foreign or missing — INV-013 prevents 403 leak);
#            409 validator failure (stop-list / finite inventory / delivery /
#            promocode / time-slot); 422 schema validation.
#   SIDE_EFFECTS: Atomic DB writes (menu inventory decrement, orders,
#                 order_items, payment, points reservation) per INV-004;
#                 Celery dispatches to
#                 payment-worker (create_payment_intent) and sms-worker
#                 (send_order_notification); Redis cart cleared.
#   LINKS:   PDD §6.1, §6.2, §7.1–§7.5, INV-002, INV-004, INV-006,
#            INV-013, INV-014, INV-016, services.checkout.
# END_CONTRACT: post_order
@orders_router.post(
    "",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_order(
    request: CreateOrderRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(_get_session),
    redis_client=Depends(_get_redis),
) -> OrderResponse:
    """Создать заказ из текущей корзины пользователя."""
    try:
        return create_order(
            user_id=current_user["user_id"],
            request=request,
            redis_client=redis_client,
            db_session=db,
        )
    except EmptyCartError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except DeliveryAddressNotFound:
        # INV-013: чужой/неизвестный delivery_address_id → 404 (НЕ 403, иначе утечка ID).
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Address not found"
        )
    except MinimumDeliveryAmountError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_minimum_delivery_error_detail(exc),
        )
    except InventoryInsufficientError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        # Ошибки валидаторов (stop-list / delivery / promocode / time-slot) → 409
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


# START_CONTRACT: post_order_estimate
#   PURPOSE: Return server-owned checkout totals for the current cart using the
#            same validation/pricing path as order creation, but without
#            mutating DB rows or dispatching side effects.
#   INPUTS:  request: CreateOrderRequest (JSON), current_user, Session,
#            Redis client.
#   OUTPUTS: 200 OrderEstimateResponse; 400 empty cart; 404 unknown delivery
#            address; 409 validator/pricing failure; 422 schema validation.
#   SIDE_EFFECTS: Redis GET + DB SELECTs only. INV-013 — request may contain
#                 delivery address PII; do not log raw values.
#   LINKS:   PDD §7.2, §7.4, §7.5, INV-002, INV-004, INV-013, INV-014.
# END_CONTRACT: post_order_estimate
@orders_router.post("/estimate", response_model=OrderEstimateResponse)
def post_order_estimate(
    request: CreateOrderRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(_get_session),
    redis_client=Depends(_get_redis),
) -> OrderEstimateResponse:
    """Предварительная серверная оценка заказа без записи заказа."""
    try:
        return estimate_order(
            user_id=current_user["user_id"],
            request=request,
            redis_client=redis_client,
            db_session=db,
        )
    except EmptyCartError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except DeliveryAddressNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Address not found"
        )
    except MinimumDeliveryAmountError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_minimum_delivery_error_detail(exc),
        )
    except InventoryInsufficientError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


# START_CONTRACT: get_order
#   PURPOSE: Return own-order detail for confirmation_url polling.
#            Foreign / unknown order_id collapses to 404 to avoid leaking
#            existence (INV-013).
#   INPUTS:  order_id: UUID, current_user, Session.
#   OUTPUTS: 200 OrderResponse; 404 if not owned/missing.
#   SIDE_EFFECTS: none (read-only DB query).
#   LINKS:   PDD §6.1, §6.2, INV-002, INV-013, INV-014.
# END_CONTRACT: get_order
@orders_router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(_get_session),
) -> OrderResponse:
    """Деталь своего заказа. Чужой или несуществующий → 404 (INV-013)."""
    order = (
        db.query(Order)
        .filter(
            Order.id == order_id,
            Order.user_id == current_user["user_id"],
        )
        .first()
    )
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Order not found"
        )

    items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    payment = db.query(Payment).filter(Payment.order_id == order.id).first()

    items_resp = [OrderItemResponse.model_validate(oi) for oi in items]

    return OrderResponse(
        id=order.id,
        status=order.status,
        type=order.type,
        items=items_resp,
        subtotal=order.subtotal,
        discount_amount=order.discount_amount,
        points_used=order.points_used,
        delivery_fee=order.delivery_fee,
        total=order.total,
        estimated_accrual=order.estimated_accrual,
        confirmation_url=(payment.confirmation_url if payment is not None else None),
        requested_time=order.requested_time,
        estimated_ready_at=order.estimated_ready_at,
        cancelled_by=order.cancelled_by,
        cancelled_at=order.cancelled_at,
        created_at=order.created_at or datetime.now(tz=UTC),
    )
