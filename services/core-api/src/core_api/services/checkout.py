# START_MODULE_CONTRACT
#   PURPOSE: Atomic Cart → Order checkout — orchestrates validators, pricing
#            chain, and persistence of orders/order_items/payments/loyalty/
#            promocode_usage in a single DB transaction. Drives Order initial
#            state (CREATED or PAID for zero-total) per PDD §6.1.
#   SCOPE:   create_order and estimate_order entry-points + injectable
#            validator/enqueue stubs (patched by tests), pricing helpers
#            (subtotal, promo, loyalty, delivery_fee, total, accrual), Redis
#            cart read, snapshotting.
#   DEPENDS: M-SHARED (Order, OrderItem, Payment, LoyaltyAccount/Transaction,
#            Promocode/PromocodeUsage, ShopSettings, MenuItem), M-DATABASE,
#            celery_app, services.delivery_addresses, services.validators
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §6.1, §7.2, INV-002,
#            INV-004, INV-006, INV-008, INV-009, INV-011, INV-013, INV-014, INV-016
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   EmptyCartError              - raised when Redis cart is missing or empty
#   InventoryInsufficientError  - raised when finite stock cannot satisfy cart
#   validate_stop_list          - INV-006 stub (test-patchable)
#   validate_time_slot          - working-hours validator stub
#   validate_delivery_address   - delegates to validators.delivery (Haversine)
#   validate_min_delivery_amount- INV-009 stub (test-patchable)
#   validate_promocode          - INV-011 stub (test-patchable)
#   geocode_address             - yandex-maps stub (NotImplementedError here)
#   load_saved_address          - ownership-checked DeliveryAddress lookup
#   compute_subtotal            - server-side subtotal from current DB prices
#   apply_promocode             - PERCENT/FIXED discount application
#   apply_loyalty_points        - cap & subtract points
#   compute_delivery_fee        - delivery fee resolver (stub here)
#   compute_order_total         - max(0, subtotal-discount-points+fee)
#   compute_estimated_accrual   - ShopSettings-based loyalty accrual estimate
#   enqueue_payment_task        - dispatch payment_worker.create_payment Celery task
#   estimate_order              - read-only server-owned checkout estimate
#   create_order                - main atomic checkout flow
# END_MODULE_MAP
"""Cart → Order checkout service (PDD §7.1 item 1, §7.2, §6.1).

Сервис конвертации корзины в заказ. Порядок шагов:
  1) чтение Redis-корзины,
  2) валидаторы (stop-list / time-slot / delivery / promocode) ДО любых записей,
  3) pricing chain §7.2 (subtotal → promo → loyalty → fee → total → accrual),
  4) атомарные записи (orders + order_items + payments + опц. loyalty_tx + promo_usage),
  5) post-commit побочные эффекты (Celery enqueue или удаление Redis-корзины).

Валидаторы и enqueue_payment_task — стабы: их тела лежат в sibling-капабилити
`order-pricing-validation` / `payment-yukassa`. Тесты патчат их по пути
`core_api.services.checkout.<name>`.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from core_api import celery_app as _celery_mod
from core_api.schemas.order import (
    CreateOrderRequest,
    OrderEstimateResponse,
    OrderItemResponse,
    OrderResponse,
)
from core_api.services import pricing as _pricing
from core_api.services.delivery_addresses import DeliveryAddressNotFound
from core_api.services.validators.delivery import (
    validate_min_delivery_amount as _validate_min_delivery_amount,
)
from core_api.services.validators.promocode import (
    validate_promocode as _validate_promocode,
)
from core_api.services.validators.stop_list import (
    validate_stop_list as _validate_stop_list,
)
from core_api.services.validators.working_hours import (
    validate_time_slot as _validate_time_slot,
)
from shared.enums import (
    LoyaltyTransactionType,
    OrderStatus,
    OrderType,
    PaymentStatus,
    PromocodeDiscountType,
)
from shared.models import (
    DeliveryAddress,
    LoyaltyAccount,
    LoyaltyTransaction,
    Order,
    OrderItem,
    Payment,
    Promocode,
    PromocodeUsage,
    ShopSettings,
)
from shared.models.menu import MenuItem, Modifier, SizeOption

from shared.grace.logging import get_grace_logger

# Модуль-уровневая ссылка — тесты патчат `sut.celery_app.send_task`.
celery_app = _celery_mod.celery_app
_grace_log = get_grace_logger("CoreApi")


# START_CONTRACT: EmptyCartError
#   PURPOSE: Raised when checkout reads an empty/missing Redis cart — router
#            translates to HTTP 400.
#   INPUTS:  message: str
#   OUTPUTS: Exception instance.
#   SIDE_EFFECTS: none
# END_CONTRACT: EmptyCartError
class EmptyCartError(Exception):
    """Пустая корзина — отображается в HTTP 400."""


# START_CONTRACT: InventoryInsufficientError
#   PURPOSE: Raised when checkout cannot satisfy finite MenuItem inventory for
#            the aggregated cart quantity; routers map it to HTTP 409.
#   INPUTS:  message: str
#   OUTPUTS: Exception instance.
#   SIDE_EFFECTS: none
#   LINKS:   PDD §7.1, INV-004, INV-014
# END_CONTRACT: InventoryInsufficientError
class InventoryInsufficientError(Exception):
    """Недостаточно конечного остатка для оформления корзины."""


# ---------------------------------------------------------------------------
# Стабы валидаторов (owned by `order-pricing-validation`)
# ---------------------------------------------------------------------------


# START_CONTRACT: validate_stop_list
#   PURPOSE: Reject checkout if any cart line references an unavailable
#            (stop-listed/archived) menu item. Adapter keeps this module
#            symbol test-patchable while delegating to the real validator.
#   INPUTS:  cart_items: list[dict] — raw Redis cart lines
#            db_session: Session
#   OUTPUTS: None
#   SIDE_EFFECTS: none in the stub; raises validation error in real impl.
#   LINKS:   PDD §7.1, INV-006
# END_CONTRACT: validate_stop_list
def validate_stop_list(cart_items: list[dict], db_session: Session) -> None:
    """Проверка stop-list через `core_api.services.validators.stop_list`."""
    _validate_stop_list(cart_items, db_session)


# START_CONTRACT: validate_time_slot
#   PURPOSE: Reject checkout outside shop working hours and return the
#            estimated ready timestamp.
#   INPUTS:  requested_time: datetime | None
#            shop_settings: ShopSettings
#            order_type: OrderType
#   OUTPUTS: datetime
#   SIDE_EFFECTS: none.
#   LINKS:   PDD §7.5
# END_CONTRACT: validate_time_slot
def validate_time_slot(
    requested_time: datetime | None,
    shop_settings: Any,
    order_type: OrderType = OrderType.PICKUP,
) -> datetime:
    """Проверка рабочих часов через `validators.working_hours`."""
    return _validate_time_slot(requested_time, order_type, shop_settings)


# START_CONTRACT: validate_delivery_address
#   PURPOSE: Server-side Haversine distance check against ShopSettings radius
#            (INV-008). Delegates to validators.delivery so this module symbol
#            stays test-patchable.
#   INPUTS:  lat: float, lon: float, shop_settings: ShopSettings
#   OUTPUTS: None
#   SIDE_EFFECTS: raises validation error if outside radius.
#   LINKS:   PDD §7.3, INV-008
# END_CONTRACT: validate_delivery_address
def validate_delivery_address(lat: float, lon: float, shop_settings: Any) -> None:
    """Серверная Haversine-проверка (INV-008).

    Реальная реализация — в `core_api.services.validators.delivery`. Тесты
    патчат этот модульный символ — потому импорт делегируем внутри.
    """
    from core_api.services.validators.delivery import (
        validate_delivery_address as _validate,
    )

    _validate(lat, lon, shop_settings)


# START_CONTRACT: validate_min_delivery_amount
#   PURPOSE: Reject delivery checkout below ShopSettings.min_delivery_amount.
#   INPUTS:  subtotal: int, shop_settings: ShopSettings
#   OUTPUTS: None
#   SIDE_EFFECTS: none; raises MinimumDeliveryAmountError.
#   LINKS:   PDD §7.4, INV-009
# END_CONTRACT: validate_min_delivery_amount
def validate_min_delivery_amount(subtotal: int, shop_settings: Any) -> None:
    """Проверка минимальной суммы доставки через validators.delivery."""
    _validate_min_delivery_amount(subtotal, shop_settings)


# START_CONTRACT: validate_promocode
#   PURPOSE: Resolve a promocode by code with quota / time / per-user checks.
#   INPUTS:  code: str, user_id: UUID, subtotal: int, db_session: Session
#   OUTPUTS: Promocode
#   SIDE_EFFECTS: DB SELECTs only.
#   LINKS:   PDD §6.6, INV-011
# END_CONTRACT: validate_promocode
def validate_promocode(
    code: str,
    user_id: uuid.UUID,
    subtotal: int,
    db_session: Session,
) -> Any:
    """Проверка промокода через validators.promocode."""
    return _validate_promocode(code, user_id, subtotal, db_session)


# ---------------------------------------------------------------------------
# Saved-address helpers (PDD §3, §5.2)
# ---------------------------------------------------------------------------


# START_CONTRACT: geocode_address
#   PURPOSE: Inline-address geocoder shim — actual lookup is owned by the
#            yandex-maps proxy. Saved-address path skips this.
#   INPUTS:  address_text: str
#   OUTPUTS: (lat, lon) tuple — never returned here.
#   SIDE_EFFECTS: raises NotImplementedError in this module.
# END_CONTRACT: geocode_address
def geocode_address(address_text: str) -> tuple[float, float]:
    """Стаб: геокодинг (owned by `yandex-maps-proxy`).

    Для saved-address пути не вызывается — у строки уже есть lat/lon.
    """
    raise NotImplementedError("geocode_address is owned by yandex-maps-proxy")


# START_CONTRACT: load_saved_address
#   PURPOSE: Fetch a DeliveryAddress by id with ownership filter — INV-013
#            keeps cross-tenant probing impossible (foreign id → 404).
#   INPUTS:  address_id: UUID, user_id: UUID, db_session: Session
#   OUTPUTS: DeliveryAddress
#   SIDE_EFFECTS: DB SELECT only; raises DeliveryAddressNotFound when
#                 missing or owned by another user.
#   LINKS:   PDD §7.3, INV-013
# END_CONTRACT: load_saved_address
def load_saved_address(
    address_id: uuid.UUID, user_id: uuid.UUID, db_session: Session
) -> DeliveryAddress:
    """Достаёт DeliveryAddress по id с ownership-фильтром (INV-013).

    Чужой/неизвестный → DeliveryAddressNotFound (HTTP 404, не 403).
    """
    stmt = select(DeliveryAddress).where(
        DeliveryAddress.id == address_id,
        DeliveryAddress.user_id == user_id,
    )
    row = db_session.execute(stmt).scalar_one_or_none()
    if row is None:
        raise DeliveryAddressNotFound(str(address_id))
    return row


def _build_snapshot_from_saved(addr: DeliveryAddress) -> dict:
    """JSONB-снимок сохранённого адреса (INV-014, форма ≡ inline-пути)."""
    snap: dict[str, Any] = {
        "text": addr.address_text,
        "lat": addr.lat,
        "lon": addr.lon,
    }
    for key in ("apartment", "entrance", "floor", "comment"):
        value = getattr(addr, key)
        if value is not None:
            snap[key] = value
    return snap


# ---------------------------------------------------------------------------
# Pricing chain (PDD §7.2)
# ---------------------------------------------------------------------------


# START_CONTRACT: compute_subtotal
#   PURPOSE: Sum cart lines using current DB prices — INV-014 forbids trusting
#            client-supplied prices, all monetary inputs come from menu rows.
#   INPUTS:  cart_items: list[dict], db_session: Session
#   OUTPUTS: int — subtotal in kopecks (≥ 0).
#   SIDE_EFFECTS: DB SELECTs only.
#   LINKS:   PDD §7.2, INV-014
# END_CONTRACT: compute_subtotal
def compute_subtotal(cart_items: list[dict], db_session: Session) -> int:
    """Сумма позиций корзины по актуальным ценам из БД (INV-014)."""
    total = 0
    for line in cart_items:
        menu_item = db_session.get(MenuItem, line["menu_item_id"])
        unit_price = menu_item.base_price if menu_item is not None else 0
        size_option_id = line.get("size_option_id")
        if size_option_id:
            size = db_session.get(SizeOption, size_option_id)
            if size is not None:
                unit_price = size.price
        for mod_id in line.get("modifier_ids") or []:
            mod = db_session.get(Modifier, mod_id)
            if mod is not None:
                unit_price += mod.price
        total += unit_price * int(line.get("quantity", 0))
    return total


# START_CONTRACT: apply_promocode
#   PURPOSE: Apply PERCENT or FIXED_AMOUNT discount; result capped at subtotal.
#   INPUTS:  subtotal: int, promocode: Any | None
#   OUTPUTS: (discount: int, amount_after: int)
#   SIDE_EFFECTS: none (pure).
#   LINKS:   PDD §7.2, INV-011
# END_CONTRACT: apply_promocode
def apply_promocode(subtotal: int, promocode: Any) -> tuple[int, int]:
    """Возвращает (discount, amount_after). При None промокоде — (0, subtotal)."""
    if promocode is None:
        return (0, subtotal)
    if promocode.discount_type == PromocodeDiscountType.PERCENT:
        discount = subtotal * int(promocode.discount_value) // 100
    else:
        discount = int(promocode.discount_value)
    if discount > subtotal:
        discount = subtotal
    return (discount, subtotal - discount)


# START_CONTRACT: apply_loyalty_points
#   PURPOSE: Cap points usage by min(requested, balance, amount); return the
#            applied amount and the residual amount to charge.
#   INPUTS:  amount: int, points_to_use: int, account: Any (LoyaltyAccount-like)
#   OUTPUTS: (points_applied: int, amount_after: int)
#   SIDE_EFFECTS: none (pure).
#   LINKS:   PDD §7.2
# END_CONTRACT: apply_loyalty_points
def apply_loyalty_points(amount: int, points_to_use: int, account: Any) -> tuple[int, int]:
    """Возвращает (points_applied, amount_after)."""
    if points_to_use <= 0:
        return (0, amount)
    balance = getattr(account, "balance", 0) or 0
    applied = min(int(points_to_use), int(balance), int(amount))
    if applied <= 0:
        return (0, amount)
    return (applied, amount - applied)


# START_CONTRACT: compute_delivery_fee
#   PURPOSE: Resolve delivery fee for the order using ShopSettings.
#   INPUTS:  amount: int (subtotal-based), request: CreateOrderRequest,
#            shop_settings: ShopSettings | None
#   OUTPUTS: int — delivery fee in kopecks.
#   SIDE_EFFECTS: none.
#   LINKS:   PDD §7.4, INV-009
# END_CONTRACT: compute_delivery_fee
def compute_delivery_fee(
    amount: int,
    request: CreateOrderRequest,
    shop_settings: Any | None = None,
) -> int:
    """Стоимость доставки через `services.pricing`, 0 для pickup."""
    if request.type != OrderType.DELIVERY:
        return 0
    return _pricing.compute_delivery_fee(amount, shop_settings)


# START_CONTRACT: compute_order_total
#   PURPOSE: Final amount = max(0, subtotal - discount - points_applied + fee).
#   INPUTS:  subtotal, discount, points_applied, delivery_fee: int
#   OUTPUTS: int — total in kopecks (≥ 0).
#   SIDE_EFFECTS: none.
#   LINKS:   PDD §7.2
# END_CONTRACT: compute_order_total
def compute_order_total(
    subtotal: int, discount: int, points_applied: int, delivery_fee: int
) -> int:
    """Итоговая сумма заказа (не ниже нуля)."""
    total = subtotal - discount - points_applied + delivery_fee
    return max(total, 0)


# START_CONTRACT: compute_estimated_accrual
#   PURPOSE: Estimate loyalty accrual surfaced to the user pre-payment using
#            ShopSettings.loyalty_percent. Real accrual fires at COMPLETED.
#   INPUTS:  after_points: int, account: Any, shop_settings: ShopSettings
#   OUTPUTS: int — points (≥ 0).
#   SIDE_EFFECTS: none.
#   LINKS:   INV-003
# END_CONTRACT: compute_estimated_accrual
def compute_estimated_accrual(
    after_points: int,
    account: Any,
    shop_settings: Any,
) -> int:
    """Оценочное начисление баллов по ShopSettings.loyalty_percent."""
    del account
    return _pricing.compute_estimated_accrual(
        int(after_points),
        int(shop_settings.loyalty_percent),
    )


# ---------------------------------------------------------------------------
# Celery enqueue (стаб — owned by `payment-yukassa`)
# ---------------------------------------------------------------------------


# START_CONTRACT: enqueue_payment_task
#   PURPOSE: Hand the order off to payment_worker via Celery for YuKassa intent
#            creation. Tests patch celery_app on the module.
#   INPUTS:  order_id: UUID, amount: int (kopecks), idempotency_key: str
#   OUTPUTS: None
#   SIDE_EFFECTS: dispatch to Celery queue 'payments' — payment_worker.tasks.create_payment.
#   LINKS:   PDD §6.2 (PaymentLifecycle)
# END_CONTRACT: enqueue_payment_task
def enqueue_payment_task(
    order_id: uuid.UUID, amount: int, idempotency_key: str
) -> None:
    """Ставит задачу payment_worker.tasks.create_payment в очередь Celery.

    Fake-backend (`YUKASSA_BACKEND=fake`) сам дошлёт webhook → Order → PAID.
    """
    celery_app.send_task(
        "payment_worker.tasks.create_payment",
        kwargs={
            "order_id": str(order_id),
            "amount_kopecks": int(amount),
            "idempotency_key": idempotency_key,
        },
        queue="payments",
    )


# ---------------------------------------------------------------------------
# Основная функция
# ---------------------------------------------------------------------------


def _read_cart(redis_client: Any, user_id: uuid.UUID) -> list[dict]:
    raw = redis_client.get(f"cart:{user_id}")
    if raw is None:
        raise EmptyCartError("Корзина пуста")
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    payload = json.loads(raw)
    items = payload.get("items") or []
    if not items:
        raise EmptyCartError("Корзина пуста")
    return items


def _aggregate_cart_quantities(cart_items: list[dict]) -> dict[int, int]:
    quantities: dict[int, int] = {}
    for line in cart_items:
        item_id = int(line["menu_item_id"])
        quantity = int(line.get("quantity", 0))
        if quantity <= 0:
            raise InventoryInsufficientError("invalid cart quantity")
        quantities[item_id] = quantities.get(item_id, 0) + quantity
    return quantities


def _lock_finite_inventory_rows(
    cart_items: list[dict], db_session: Session
) -> tuple[dict[int, int], dict[int, MenuItem]]:
    quantities = _aggregate_cart_quantities(cart_items)
    if not quantities:
        return quantities, {}

    stmt = (
        select(MenuItem)
        .where(
            MenuItem.id.in_(list(quantities)),
            MenuItem.inventory_quantity.is_not(None),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    finite_items = {
        item.id: item
        for item in db_session.execute(stmt).scalars().all()
    }
    for item_id, item in finite_items.items():
        requested = quantities[item_id]
        if item.inventory_quantity is not None and item.inventory_quantity < requested:
            raise InventoryInsufficientError("inventory_insufficient")
    return quantities, finite_items


def _decrement_finite_inventory(
    quantities: dict[int, int],
    finite_items: dict[int, MenuItem],
    db_session: Session,
) -> None:
    for item_id, item in finite_items.items():
        current = int(item.inventory_quantity or 0)
        item.inventory_quantity = current - quantities[item_id]
    if finite_items:
        db_session.flush()


def _validate_finite_inventory_available(
    cart_items: list[dict],
    db_session: Session,
) -> None:
    quantities = _aggregate_cart_quantities(cart_items)
    if not quantities:
        return

    stmt = select(MenuItem).where(
        MenuItem.id.in_(list(quantities)),
        MenuItem.inventory_quantity.is_not(None),
    )
    finite_items = {
        item.id: item
        for item in db_session.execute(stmt).scalars().all()
    }
    for item_id, item in finite_items.items():
        requested = quantities[item_id]
        if item.inventory_quantity is not None and item.inventory_quantity < requested:
            raise InventoryInsufficientError("inventory_insufficient")


@dataclass(frozen=True)
class _CheckoutQuote:
    cart_items: list[dict]
    shop_settings: ShopSettings
    delivery_snapshot: dict[str, Any] | None
    subtotal: int
    discount: int
    after_points: int
    points_applied: int
    delivery_fee: int
    total: int
    accrual: int
    estimated_ready_at: datetime | None
    promocode: Promocode | None
    account: LoyaltyAccount | None


def _build_checkout_quote(
    user_id: uuid.UUID,
    request: CreateOrderRequest,
    redis_client: Any,
    db_session: Session,
) -> _CheckoutQuote:
    cart_items = _read_cart(redis_client, user_id)

    shop_settings = db_session.get(ShopSettings, 1)
    if shop_settings is None:
        raise RuntimeError("ShopSettings row id=1 is missing")

    validate_stop_list(cart_items, db_session)
    estimated_ready_at = validate_time_slot(
        request.requested_time,
        shop_settings,
        request.type,
    )
    if not isinstance(estimated_ready_at, datetime):
        estimated_ready_at = None

    delivery_snapshot: dict[str, Any] | None = None
    if request.type == OrderType.DELIVERY:
        if request.delivery_address_id is not None:
            # Saved-flow: ownership check + Haversine ВСЕГДА; geocoder НЕ вызывается.
            saved_address = load_saved_address(
                request.delivery_address_id, user_id, db_session
            )
            validate_delivery_address(
                saved_address.lat, saved_address.lon, shop_settings
            )
            delivery_snapshot = _build_snapshot_from_saved(saved_address)
        else:
            inline = request.delivery_address
            if inline is None:
                raise ValueError("delivery_address is required for delivery")
            validate_delivery_address(inline.lat, inline.lon, shop_settings)
            delivery_snapshot = inline.model_dump(exclude_none=True)

    # Pricing chain (§7.2). Subtotal must be known before delivery minimum
    # and promocode validation, but these are still read-only checks before
    # any order/payment/loyalty/promo writes.
    subtotal = compute_subtotal(cart_items, db_session)
    if request.type == OrderType.DELIVERY:
        validate_min_delivery_amount(subtotal, shop_settings)

    promocode = None
    if request.promocode_code:
        promocode = validate_promocode(
            request.promocode_code,
            user_id,
            subtotal,
            db_session,
        )

    discount, after_promo = apply_promocode(subtotal, promocode)
    account = db_session.get(LoyaltyAccount, user_id)
    points_applied, after_points = apply_loyalty_points(
        after_promo, request.points_to_use, account
    )
    delivery_fee = compute_delivery_fee(subtotal, request, shop_settings)
    total = compute_order_total(subtotal, discount, points_applied, delivery_fee)
    accrual = compute_estimated_accrual(after_points, account, shop_settings)

    return _CheckoutQuote(
        cart_items=cart_items,
        shop_settings=shop_settings,
        delivery_snapshot=delivery_snapshot,
        subtotal=subtotal,
        discount=discount,
        after_points=after_points,
        points_applied=points_applied,
        delivery_fee=delivery_fee,
        total=total,
        accrual=accrual,
        estimated_ready_at=estimated_ready_at,
        promocode=promocode,
        account=account,
    )


# START_CONTRACT: estimate_order
#   PURPOSE: Return a read-only, server-owned checkout estimate for the current
#            Redis cart using the same validation and pricing chain as
#            create_order, without writing orders/payments/loyalty/promo rows.
#   INPUTS:  user_id: UUID
#            request: CreateOrderRequest — type/address/promocode/points/time
#            redis_client: Any — Redis-like cart read
#            db_session: Session
#   OUTPUTS: OrderEstimateResponse — totals, estimated_ready_at, loyalty balance
#            and delivery free-threshold guidance.
#   SIDE_EFFECTS: DB SELECTs and Redis GET only; no commits, no Celery, no logs
#                 containing address/PII.
#   LINKS:   PDD §7.2, §7.4, §7.5, INV-004, INV-013, INV-014
# END_CONTRACT: estimate_order
def estimate_order(
    user_id: uuid.UUID,
    request: CreateOrderRequest,
    redis_client: Any,
    db_session: Session,
) -> OrderEstimateResponse:
    quote = _build_checkout_quote(user_id, request, redis_client, db_session)
    _validate_finite_inventory_available(quote.cart_items, db_session)
    free_threshold = int(quote.shop_settings.free_delivery_threshold)
    free_remaining = (
        max(free_threshold - quote.subtotal, 0)
        if request.type == OrderType.DELIVERY
        else 0
    )
    return OrderEstimateResponse(
        subtotal=quote.subtotal,
        discount_amount=quote.discount,
        points_used=quote.points_applied,
        delivery_fee=quote.delivery_fee,
        total=quote.total,
        estimated_accrual=quote.accrual,
        estimated_ready_at=quote.estimated_ready_at,
        loyalty_balance=int(getattr(quote.account, "balance", 0) or 0),
        min_delivery_amount=int(quote.shop_settings.min_delivery_amount),
        free_delivery_threshold=free_threshold,
        free_delivery_remaining=free_remaining,
    )


# START_CONTRACT: create_order
#   PURPOSE: Atomic checkout — read cart, run validators, compute pricing chain,
#            lock/decrement finite inventory, persist Order/OrderItems/Payment
#            plus optional LoyaltyTransaction and PromocodeUsage in one DB
#            transaction, then dispatch payment task or clean Redis cart for
#            zero-total flow.
#   INPUTS:  user_id: UUID
#            request: CreateOrderRequest — type/address/promocode/points
#            redis_client: Any — Redis-like for cart read/cleanup
#            db_session: Session
#   OUTPUTS: OrderResponse — populated from persisted rows.
#   SIDE_EFFECTS: DB UPDATE of menu_items.inventory_quantity for finite-stock
#                 rows + DB INSERTs (orders, order_items per INV-014
#                 immutability, payments, loyalty_transactions,
#                 promocode_usages) + UPDATE of promocodes.current_uses via
#                 conditional WHERE; commit; then either Celery dispatch
#                 (paid path) or Redis DEL (zero-total).
#                 Source state: n/a → CREATED (paid path) or PAID (zero-total).
#                 Empty cart → EmptyCartError.
#   LINKS:   PDD §6.1 (initial state), §7.1, §7.2, INV-002, INV-004, INV-006,
#            INV-008, INV-009, INV-011, INV-013, INV-014, INV-016
# END_CONTRACT: create_order
def create_order(
    user_id: uuid.UUID,
    request: CreateOrderRequest,
    redis_client: Any,
    db_session: Session,
) -> OrderResponse:
    """Конвертирует корзину в заказ. См. модуль-docstring."""
    _grace_log.block("orders.create", "BLOCK_TX_BEGIN", user_id=str(user_id))
    quote = _build_checkout_quote(user_id, request, redis_client, db_session)

    # 4. Атомарные записи (single logical transaction, INV-004)
    inventory_quantities, finite_inventory = _lock_finite_inventory_rows(
        quote.cart_items, db_session
    )
    _decrement_finite_inventory(inventory_quantities, finite_inventory, db_session)

    idempotency_key = str(uuid.uuid4())
    order_status = OrderStatus.PAID if quote.total == 0 else OrderStatus.CREATED

    order = Order(
        user_id=user_id,
        status=order_status,
        type=request.type,
        requested_time=request.requested_time,
        estimated_ready_at=quote.estimated_ready_at,
        delivery_address_snapshot=quote.delivery_snapshot,
        subtotal=quote.subtotal,
        discount_amount=quote.discount,
        points_used=quote.points_applied,
        delivery_fee=quote.delivery_fee,
        total=quote.total,
        estimated_accrual=quote.accrual,
        promocode_id=(quote.promocode.id if quote.promocode is not None else None),
    )
    db_session.add(order)
    db_session.flush()

    # OrderItems: снимки из БД, не из Redis (INV-014)
    for line in quote.cart_items:
        menu_item = db_session.get(MenuItem, line["menu_item_id"])
        if menu_item is None:
            continue
        unit_price = menu_item.base_price
        name_ru = menu_item.name_ru
        name_en = menu_item.name_en
        size_label: str | None = None
        size_option_id = line.get("size_option_id")
        if size_option_id:
            size = db_session.get(SizeOption, size_option_id)
            if size is not None:
                unit_price = size.price
                label = size.label
                size_label = label.value if hasattr(label, "value") else str(label)
        modifiers_snapshot: list[dict[str, Any]] = []
        for mod_id in line.get("modifier_ids") or []:
            mod = db_session.get(Modifier, mod_id)
            if mod is None:
                continue
            unit_price += mod.price
            modifiers_snapshot.append(
                {
                    "id": mod.id,
                    "name_ru": mod.name_ru,
                    "name_en": mod.name_en,
                    "price": mod.price,
                }
            )
        quantity = int(line.get("quantity", 0))
        line_total = unit_price * quantity
        db_session.add(
            OrderItem(
                order_id=order.id,
                menu_item_id=menu_item.id,
                menu_item_name_ru=name_ru,
                menu_item_name_en=name_en,
                size_option_id=size_option_id,
                size_label=size_label,
                unit_price=unit_price,
                modifiers_snapshot=modifiers_snapshot,
                quantity=quantity,
                line_total=line_total,
            )
        )

    # Payment (idempotency_key генерируется до Celery enqueue)
    payment_status = (
        PaymentStatus.SUCCEEDED if quote.total == 0 else PaymentStatus.PENDING
    )
    db_session.add(
        Payment(
            order_id=order.id,
            amount=quote.total,
            status=payment_status,
            idempotency_key=idempotency_key,
        )
    )

    # LoyaltyTransaction (только если баллы реально применены)
    if quote.points_applied > 0 and quote.account is not None:
        tx_type = (
            LoyaltyTransactionType.REDEMPTION
            if quote.total == 0
            else LoyaltyTransactionType.RESERVATION
        )
        new_balance = int(quote.account.balance or 0) - int(quote.points_applied)
        quote.account.balance = new_balance
        db_session.add(
            LoyaltyTransaction(
                user_id=user_id,
                order_id=order.id,
                type=tx_type,
                amount=-int(quote.points_applied),
                balance_after=new_balance,
            )
        )

    # PromocodeUsage: атомарный conditional UPDATE (PDD §6.6, INV-011).
    # Предикат квоты живёт внутри WHERE — БД, а не Python-снапшот, решает
    # может ли счётчик быть увеличен. На rowcount==0 (проиграли гонку)
    # поднимаем ту же PromocodeValidationError, что и pre-check валидатор —
    # клиент видит одинаковый 422.
    if quote.promocode is not None:
        from core_api.services.validators.exceptions import (
            PromocodeValidationError,
        )

        result = db_session.execute(
            update(Promocode)
            .where(
                Promocode.id == quote.promocode.id,
                or_(
                    Promocode.max_uses.is_(None),
                    Promocode.current_uses < Promocode.max_uses,
                ),
            )
            .values(current_uses=Promocode.current_uses + 1)
        )
        if result.rowcount == 0:
            raise PromocodeValidationError("Global quota exhausted")
        db_session.add(
            PromocodeUsage(
                promocode_id=quote.promocode.id,
                user_id=user_id,
                order_id=order.id,
            )
        )

    db_session.flush()
    db_session.commit()
    _grace_log.belief(
        "orders.create",
        "BLOCK_STATE_TRANSITION",
        belief=order_status.value,
        actual=order.status.value,
        order_id=str(order.id),
    )
    _grace_log.block("orders.create", "BLOCK_TX_COMMIT", order_id=str(order.id))

    # 5. Post-commit побочные эффекты
    if quote.total > 0:
        enqueue_payment_task(
            order_id=order.id, amount=quote.total, idempotency_key=idempotency_key
        )
    else:
        try:
            redis_client.delete(f"cart:{user_id}")
        except Exception:
            pass

    # 6. Сборка OrderResponse
    order_items = (
        db_session.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    )
    payment = (
        db_session.query(Payment).filter(Payment.order_id == order.id).first()
    )
    items_resp = [OrderItemResponse.model_validate(oi) for oi in order_items]
    confirmation_url = payment.confirmation_url if payment is not None else None

    return OrderResponse(
        id=order.id,
        status=order.status,
        type=order.type,
        items=items_resp,
        subtotal=quote.subtotal,
        discount_amount=quote.discount,
        points_used=quote.points_applied,
        delivery_fee=quote.delivery_fee,
        total=quote.total,
        estimated_accrual=quote.accrual,
        confirmation_url=confirmation_url,
        requested_time=order.requested_time,
        estimated_ready_at=order.estimated_ready_at,
        cancelled_by=order.cancelled_by,
        cancelled_at=order.cancelled_at,
        created_at=order.created_at or datetime.now(tz=UTC),
    )
