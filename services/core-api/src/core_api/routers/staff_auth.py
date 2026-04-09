import redis
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core_api.deps.auth import get_current_user
from core_api.deps.database import get_db
from core_api.deps.redis import get_redis
from core_api.schemas.staff_auth import (
    StaffLoginRequest,
    StaffLogoutRequest,
    StaffRefreshRequest,
    StaffTokenResponse,
)
from core_api.services.staff_auth import StaffAuthService

router = APIRouter(prefix="/api/v1/staff/auth", tags=["staff-auth"])


@router.post(
    "/login",
    response_model=StaffTokenResponse,
    status_code=status.HTTP_200_OK,
)
def login(
    body: StaffLoginRequest,
    db: Session = Depends(get_db),
    r: redis.Redis = Depends(get_redis),
) -> StaffTokenResponse:
    svc = StaffAuthService(db, r)
    result = svc.authenticate(body.login, body.password)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    return StaffTokenResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        role=result.role,
    )


@router.post(
    "/refresh",
    response_model=StaffTokenResponse,
    status_code=status.HTTP_200_OK,
)
def refresh(
    body: StaffRefreshRequest,
    db: Session = Depends(get_db),
    r: redis.Redis = Depends(get_redis),
) -> StaffTokenResponse:
    svc = StaffAuthService(db, r)
    result = svc.refresh_tokens(body.refresh_token)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    return StaffTokenResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        role=result.role,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
)
def logout(
    body: StaffLogoutRequest,
    current_user: dict = Depends(get_current_user),
    r: redis.Redis = Depends(get_redis),
    db: Session = Depends(get_db),
) -> dict:
    svc = StaffAuthService(db, r)
    svc.logout(body.refresh_token)
    return {"detail": "Logged out"}
