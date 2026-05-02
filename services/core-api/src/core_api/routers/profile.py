# START_MODULE_CONTRACT
#   PURPOSE: HTTP routes for the customer's own profile under /api/v1/profile:
#            read, partial update, and irreversible account deletion.
#   SCOPE:   Read/update of the current user's profile row plus PDD §6.5
#            ACTIVE→DELETED deletion/anonymization. CUSTOMER-only; phone number
#            is never exposed (INV-013).
#   DEPENDS: M-DATABASE (Session), core_api.services.profile,
#            core_api.deps.{auth,database}.
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §3, §5.2,
#            INV-002, INV-013 (PII isolation).
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   router             - APIRouter("/api/v1/profile", tags=["profile"])
#   get_my_profile     - GET   /api/v1/profile
#   update_my_profile  - PATCH /api/v1/profile
#   delete_my_profile  - DELETE /api/v1/profile
# END_MODULE_MAP

import redis
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core_api.deps.auth import get_current_user
from core_api.deps.database import get_db
from core_api.deps.redis import get_redis
from core_api.schemas.account_deletion import AccountDeletionResponse
from core_api.schemas.profile import ProfileResponse, ProfileUpdateRequest
from core_api.services.account_deletion import (
    AccountDeletionActiveOrderError,
    AccountDeletionInvalidStateError,
    AccountDeletionNotFoundError,
    delete_customer_account,
)
from core_api.services.auth import AuthService
from core_api.services.profile import get_profile, update_profile
from shared.grace.logging import get_grace_logger

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])
_grace_log = get_grace_logger("CoreApi")


# START_CONTRACT: get_my_profile
#   PURPOSE: Return the current customer's profile.
#   INPUTS:  current_user (get_current_user), Session.
#   OUTPUTS: 200 ProfileResponse; 404 Profile not found.
#   SIDE_EFFECTS: none (read-only DB query).
#   LINKS:   PDD §3, §5.2, INV-002, INV-013, services.profile.
# END_CONTRACT: get_my_profile
@router.get("", response_model=ProfileResponse)
def get_my_profile(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    result = get_profile(current_user["user_id"], db)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return result


# START_CONTRACT: update_my_profile
#   PURPOSE: Partial update of the current customer's profile.
#   INPUTS:  body: ProfileUpdateRequest, current_user, Session.
#   OUTPUTS: 200 ProfileResponse; 404 Profile not found.
#   SIDE_EFFECTS: DB update on user_profiles row.
#   LINKS:   PDD §3, §5.2, INV-002, INV-013, services.profile.
# END_CONTRACT: update_my_profile
@router.patch("", response_model=ProfileResponse)
def update_my_profile(
    body: ProfileUpdateRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    result = update_profile(current_user["user_id"], body, db)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return result


# START_CONTRACT: delete_my_profile
#   PURPOSE: Irreversibly delete the current customer's account by applying the
#            PDD §6.5 ACTIVE→DELETED lifecycle transition and INV-013
#            anonymization.
#   INPUTS:  current_user, Session, Redis client.
#   OUTPUTS: 200 AccountDeletionResponse; 404 user_not_found; 409
#            invalid_user_state or active_order_not_deletable.
#   SIDE_EFFECTS: DB tombstone/PII cleanup, cancellable order cancellations,
#                 loyalty zeroing, Redis session revocation.
#   LINKS:   PDD §6.5, §7.6, INV-002, INV-013, INV-016,
#            services.account_deletion.
# END_CONTRACT: delete_my_profile
@router.delete("", response_model=AccountDeletionResponse)
def delete_my_profile(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
    r: redis.Redis = Depends(get_redis),
) -> AccountDeletionResponse:
    _grace_log.block(
        "profile.delete",
        "BLOCK_AUTH_VERIFY",
        "customer account deletion authorized",
        user_id=str(current_user["user_id"]),
    )
    try:
        response = delete_customer_account(db=db, user_id=current_user["user_id"])
        AuthService(r).revoke_user_sessions(current_user["user_id"])
        return response
    except AccountDeletionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found"
        ) from exc
    except AccountDeletionActiveOrderError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="active_order_not_deletable",
        ) from exc
    except AccountDeletionInvalidStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="invalid_user_state"
        ) from exc
