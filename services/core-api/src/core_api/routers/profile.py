# START_MODULE_CONTRACT
#   PURPOSE: HTTP routes for the customer's own profile under
#            /api/v1/profile — get and patch name/birthday/preferences.
#   SCOPE:   Read and partial update of the current user's profile row.
#            CUSTOMER-only; phone number is never exposed (INV-013).
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
# END_MODULE_MAP

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core_api.deps.auth import get_current_user
from core_api.deps.database import get_db
from core_api.schemas.profile import ProfileResponse, ProfileUpdateRequest
from core_api.services.profile import get_profile, update_profile

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])


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
