"""HTTP-роуты сохранённых адресов доставки (PDD §3, §5.2)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from core_api.deps.auth import get_current_user
from core_api.deps.database import get_db
from core_api.schemas.delivery_address import (
    DeliveryAddressCreate,
    DeliveryAddressRead,
    DeliveryAddressUpdate,
)
from core_api.services import delivery_addresses as svc
from core_api.services.validators.exceptions import DeliveryRadiusError

router = APIRouter(tags=["delivery-addresses"])


@router.get("", response_model=list[DeliveryAddressRead])
def list_addresses(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DeliveryAddressRead]:
    rows = svc.list_for_user(db, current_user["user_id"])
    return [DeliveryAddressRead.model_validate(r) for r in rows]


@router.post(
    "",
    response_model=DeliveryAddressRead,
    status_code=status.HTTP_201_CREATED,
)
def create_address(
    payload: DeliveryAddressCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeliveryAddressRead:
    try:
        addr = svc.create_for_user(db, current_user["user_id"], payload)
    except DeliveryRadiusError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    return DeliveryAddressRead.model_validate(addr)


@router.patch("/{address_id}", response_model=DeliveryAddressRead)
def patch_address(
    address_id: uuid.UUID,
    payload: DeliveryAddressUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeliveryAddressRead:
    try:
        addr = svc.update_for_user(
            db, current_user["user_id"], address_id, payload
        )
    except svc.DeliveryAddressNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Address not found"
        )
    return DeliveryAddressRead.model_validate(addr)


@router.delete("/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_address(
    address_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    try:
        svc.delete_for_user(db, current_user["user_id"], address_id)
    except svc.DeliveryAddressNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Address not found"
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
