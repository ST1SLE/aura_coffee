from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core_api.deps.auth import get_current_user
from core_api.deps.database import get_db
from core_api.schemas.profile import ProfileResponse, ProfileUpdateRequest
from core_api.services.profile import get_profile, update_profile

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])


def _require_customer(current_user: dict = Depends(get_current_user)) -> dict:
    """Проверка роли customer."""
    if current_user["role"] != "customer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return current_user


@router.get("", response_model=ProfileResponse)
def get_my_profile(
    current_user: dict = Depends(_require_customer),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    result = get_profile(current_user["user_id"], db)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return result


@router.patch("", response_model=ProfileResponse)
def update_my_profile(
    body: ProfileUpdateRequest,
    current_user: dict = Depends(_require_customer),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    result = update_profile(current_user["user_id"], body, db)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return result
