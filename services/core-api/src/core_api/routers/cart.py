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
