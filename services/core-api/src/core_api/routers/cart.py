# START_MODULE_CONTRACT
#   PURPOSE: HTTP routes for customer cart operations under /api/v1/cart.
#            Cart lives in Redis with TTL; this router is the thin transport
#            layer over services.cart.CartService.
#   SCOPE:   GET/POST/PATCH/DELETE on cart and cart line items. Error
#            mapping CartValidationError → 404/409. No DB writes; Redis
#            reads/writes via CartService.
#   DEPENDS: M-DATABASE (Session), core_api.services.cart,
#            core_api.deps.{auth,database,redis}.
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §7.1 cart,
#            INV-002 (auth required), INV-006 (server-side stop-list).
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   router            - APIRouter("/api/v1/cart", tags=["cart"])
#   get_cart          - GET    /api/v1/cart
#   add_cart_item     - POST   /api/v1/cart/items
#   update_cart_item  - PATCH  /api/v1/cart/items/{line_id}
#   delete_cart_item  - DELETE /api/v1/cart/items/{line_id}
#   clear_cart        - DELETE /api/v1/cart
# END_MODULE_MAP

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core_api.deps import database as _db_dep
from core_api.deps import redis as _redis_dep
from core_api.deps.auth import get_current_user
from core_api.schemas.cart import CartItemCreate, CartItemQuantityUpdate, CartResponse
from core_api.services.cart import CartService, CartValidationError
from core_api.settings import settings

router = APIRouter(prefix="/api/v1/cart", tags=["cart"])


# Обёртки, которые обращаются к атрибутам модуля в момент вызова —
# это позволяет тестам патчить core_api.deps.redis.get_redis / get_session
def _get_redis():
    yield from _redis_dep.get_redis()


def _get_session():
    yield from _db_dep.get_session()


def _cart_error_to_http(exc: CartValidationError) -> HTTPException:
    """Конвертирует CartValidationError в HTTPException (design D8)."""
    if exc.reason == "not_found":
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.reason)
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.reason)


# START_CONTRACT: get_cart
#   PURPOSE: Return the current customer's cart snapshot.
#   INPUTS:  current_user (get_current_user), Session, Redis client.
#   OUTPUTS: 200 CartResponse.
#   SIDE_EFFECTS: none (read-only Redis lookup via CartService.get).
#   LINKS:   PDD §7.1, INV-002, services.cart.
# END_CONTRACT: get_cart
@router.get("", response_model=CartResponse)
def get_cart(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(_get_session),
    redis_client=Depends(_get_redis),
) -> CartResponse:
    """Возвращает текущую корзину покупателя."""
    svc = CartService(
        session=db,
        redis_client=redis_client,
        user_id=current_user["user_id"],
        ttl_seconds=settings.cart_ttl_seconds,
    )
    return svc.get()


# START_CONTRACT: add_cart_item
#   PURPOSE: Add a line to the cart or merge with an existing line on
#            matching line_id (qty += 1).
#   INPUTS:  item: CartItemCreate, current_user, Session, Redis client.
#   OUTPUTS: 201 CartResponse; 404 menu item not found;
#            409 stop-list / size mismatch (CartValidationError).
#   SIDE_EFFECTS: Redis write of cart payload, TTL refresh.
#   LINKS:   PDD §7.1, INV-002, INV-006 (server-side stop-list), services.cart.
# END_CONTRACT: add_cart_item
@router.post("/items", response_model=CartResponse, status_code=status.HTTP_201_CREATED)
def add_cart_item(
    item: CartItemCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(_get_session),
    redis_client=Depends(_get_redis),
) -> CartResponse:
    """Добавляет позицию в корзину или увеличивает quantity при совпадении line_id."""
    svc = CartService(
        session=db,
        redis_client=redis_client,
        user_id=current_user["user_id"],
        ttl_seconds=settings.cart_ttl_seconds,
    )
    try:
        return svc.add_item(item)
    except CartValidationError as exc:
        raise _cart_error_to_http(exc)


# START_CONTRACT: update_cart_item
#   PURPOSE: Replace quantity for an existing cart line.
#   INPUTS:  line_id: str, body: CartItemQuantityUpdate, current_user,
#            Session, Redis client.
#   OUTPUTS: 200 CartResponse; 404 line not found; 409 invalid update.
#   SIDE_EFFECTS: Redis write, TTL refresh.
#   LINKS:   PDD §7.1, INV-002, services.cart.
# END_CONTRACT: update_cart_item
@router.patch("/items/{line_id}", response_model=CartResponse)
def update_cart_item(
    line_id: str,
    body: CartItemQuantityUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(_get_session),
    redis_client=Depends(_get_redis),
) -> CartResponse:
    """Обновляет количество строки корзины по line_id."""
    svc = CartService(
        session=db,
        redis_client=redis_client,
        user_id=current_user["user_id"],
        ttl_seconds=settings.cart_ttl_seconds,
    )
    try:
        return svc.update_item_quantity(line_id, body.quantity)
    except CartValidationError as exc:
        raise _cart_error_to_http(exc)


# START_CONTRACT: delete_cart_item
#   PURPOSE: Remove a single line from the cart by line_id.
#   INPUTS:  line_id: str, current_user, Session, Redis client.
#   OUTPUTS: 200 CartResponse; 404 line not found.
#   SIDE_EFFECTS: Redis write, TTL refresh.
#   LINKS:   PDD §7.1, INV-002, services.cart.
# END_CONTRACT: delete_cart_item
@router.delete("/items/{line_id}", response_model=CartResponse)
def delete_cart_item(
    line_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(_get_session),
    redis_client=Depends(_get_redis),
) -> CartResponse:
    """Удаляет строку корзины по line_id."""
    svc = CartService(
        session=db,
        redis_client=redis_client,
        user_id=current_user["user_id"],
        ttl_seconds=settings.cart_ttl_seconds,
    )
    try:
        return svc.delete_item(line_id)
    except CartValidationError as exc:
        raise _cart_error_to_http(exc)


# START_CONTRACT: clear_cart
#   PURPOSE: Empty the current customer's cart. Idempotent.
#   INPUTS:  current_user, Session, Redis client.
#   OUTPUTS: 200 CartResponse (empty cart).
#   SIDE_EFFECTS: Redis delete of cart key.
#   LINKS:   PDD §7.1, INV-002, services.cart.
# END_CONTRACT: clear_cart
@router.delete("", response_model=CartResponse)
def clear_cart(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(_get_session),
    redis_client=Depends(_get_redis),
) -> CartResponse:
    """Очищает корзину целиком. Идемпотентен."""
    svc = CartService(
        session=db,
        redis_client=redis_client,
        user_id=current_user["user_id"],
        ttl_seconds=settings.cart_ttl_seconds,
    )
    return svc.clear()
