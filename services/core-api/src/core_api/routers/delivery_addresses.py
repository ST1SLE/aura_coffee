"""HTTP-роуты сохранённых адресов доставки (PDD §3, §5.2)."""

from __future__ import annotations

# START_MODULE_CONTRACT
#   PURPOSE: HTTP routes for customer saved delivery addresses
#            (mounted under /api/v1/profile/addresses by main.py).
#   SCOPE:   List, create, patch, delete saved addresses bound to the
#            current user. Delivery-radius validation via shared validator.
#   DEPENDS: M-DATABASE (Session), core_api.services.delivery_addresses,
#            core_api.services.validators (DeliveryRadiusError),
#            core_api.deps.{auth,database}.
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §3, §5.2, §7.3,
#            INV-002, INV-013 (PII isolation per user).
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   router          - APIRouter(tags=["delivery-addresses"])
#   list_addresses  - GET    /api/v1/profile/addresses
#   create_address  - POST   /api/v1/profile/addresses
#   patch_address   - PATCH  /api/v1/profile/addresses/{address_id}
#   delete_address  - DELETE /api/v1/profile/addresses/{address_id}
# END_MODULE_MAP

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


# START_CONTRACT: list_addresses
#   PURPOSE: List the current customer's saved delivery addresses.
#   INPUTS:  current_user (get_current_user), Session.
#   OUTPUTS: 200 list[DeliveryAddressRead].
#   SIDE_EFFECTS: none.
#   LINKS:   PDD §3, §5.2, INV-002, INV-013, services.delivery_addresses.
# END_CONTRACT: list_addresses
@router.get("", response_model=list[DeliveryAddressRead])
def list_addresses(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DeliveryAddressRead]:
    rows = svc.list_for_user(db, current_user["user_id"])
    return [DeliveryAddressRead.model_validate(r) for r in rows]


# START_CONTRACT: create_address
#   PURPOSE: Persist a new delivery address for the current customer
#            after delivery-radius validation.
#   INPUTS:  payload: DeliveryAddressCreate, current_user, Session.
#   OUTPUTS: 201 DeliveryAddressRead; 422 DeliveryRadiusError.
#   SIDE_EFFECTS: DB insert into delivery_addresses.
#   LINKS:   PDD §7.3, §7.4, INV-002, INV-013, services.delivery_addresses.
# END_CONTRACT: create_address
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


# START_CONTRACT: patch_address
#   PURPOSE: Partial update of an owned delivery address.
#   INPUTS:  address_id: UUID, payload: DeliveryAddressUpdate, current_user,
#            Session.
#   OUTPUTS: 200 DeliveryAddressRead; 404 if not owned/not found.
#   SIDE_EFFECTS: DB update on delivery_addresses row.
#   LINKS:   PDD §3, §5.2, INV-002, INV-013, services.delivery_addresses.
# END_CONTRACT: patch_address
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


# START_CONTRACT: delete_address
#   PURPOSE: Soft/hard delete of an owned delivery address.
#   INPUTS:  address_id: UUID, current_user, Session.
#   OUTPUTS: 204 No Content; 404 if not owned/not found.
#   SIDE_EFFECTS: DB delete on delivery_addresses row.
#   LINKS:   PDD §3, §5.2, INV-002, INV-013, services.delivery_addresses.
# END_CONTRACT: delete_address
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
