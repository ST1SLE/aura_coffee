# START_MODULE_CONTRACT
#   PURPOSE: HTTP routes for staff (admin/barista/courier) login/refresh/
#            logout under /api/v1/staff/auth — login/password authentication
#            with brute-force throttling (no SMS OTP; that path is customer-only).
#   SCOPE:   Authenticate staff credentials, issue/rotate JWT pairs,
#            revoke refresh tokens on logout.
#   DEPENDS: M-DATABASE (Session), Redis,
#            core_api.services.staff_auth,
#            core_api.deps.{auth,database,redis}.
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §6.5, §8.1,
#            INV-002, INV-010 (role-bound tokens), INV-013.
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   router    - APIRouter("/api/v1/staff/auth", tags=["staff-auth"])
#   login     - POST /api/v1/staff/auth/login
#   refresh   - POST /api/v1/staff/auth/refresh
#   logout    - POST /api/v1/staff/auth/logout
# END_MODULE_MAP

import redis
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
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
from core_api.services.staff_auth import StaffAuthService, StaffLoginRateLimited

router = APIRouter(prefix="/api/v1/staff/auth", tags=["staff-auth"])

_STAFF_REFRESH_COOKIE = "aura_staff_refresh_token"
_STAFF_REFRESH_COOKIE_PATH = "/api/v1/staff/auth"


def _refresh_cookie_secure() -> bool:
    from core_api.settings import settings

    return settings.aura_env.strip().lower() != "dev"


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    from core_api.settings import settings

    response.set_cookie(
        key=_STAFF_REFRESH_COOKIE,
        value=refresh_token,
        max_age=settings.refresh_token_ttl,
        httponly=True,
        secure=_refresh_cookie_secure(),
        samesite="strict",
        path=_STAFF_REFRESH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=_STAFF_REFRESH_COOKIE,
        path=_STAFF_REFRESH_COOKIE_PATH,
        secure=_refresh_cookie_secure(),
        httponly=True,
        samesite="strict",
    )


def _refresh_token_from_request(
    request: Request,
    body: StaffRefreshRequest | StaffLogoutRequest | None,
) -> str | None:
    return request.cookies.get(_STAFF_REFRESH_COOKIE) or (
        body.refresh_token if body is not None else None
    )


# START_CONTRACT: login
#   PURPOSE: Authenticate staff credentials and issue access + refresh
#            tokens carrying the staff role.
#   INPUTS:  body: StaffLoginRequest (login, password), Session, Redis client.
#   OUTPUTS: 200 StaffTokenResponse; 401 invalid credentials; 429 throttled.
#   SIDE_EFFECTS: Redis writes — failed-login counters or refresh token stored.
#   LINKS:   PDD §8.1, INV-002, INV-010, INV-013, services.staff_auth.
# END_CONTRACT: login
@router.post(
    "/login",
    response_model=StaffTokenResponse,
    status_code=status.HTTP_200_OK,
)
def login(
    body: StaffLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    r: redis.Redis = Depends(get_redis),
) -> StaffTokenResponse:
    svc = StaffAuthService(db, r)
    source_ip = request.client.host if request.client is not None else None
    try:
        result = svc.authenticate(body.login, body.password, source_ip=source_ip)
    except StaffLoginRateLimited as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts",
            headers={"Retry-After": str(exc.retry_after)},
        )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    _set_refresh_cookie(response, result.refresh_token)
    return StaffTokenResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        role=result.role,
    )


# START_CONTRACT: refresh
#   PURPOSE: Rotate the staff access/refresh pair.
#   INPUTS:  body: StaffRefreshRequest, Session, Redis client.
#   OUTPUTS: 200 StaffTokenResponse; 401 invalid/expired refresh.
#   SIDE_EFFECTS: Redis write — old refresh revoked, new pair stored.
#   LINKS:   PDD §8.1, INV-002, INV-010, services.staff_auth.
# END_CONTRACT: refresh
@router.post(
    "/refresh",
    response_model=StaffTokenResponse,
    status_code=status.HTTP_200_OK,
)
def refresh(
    request: Request,
    response: Response,
    body: StaffRefreshRequest | None = None,
    db: Session = Depends(get_db),
    r: redis.Redis = Depends(get_redis),
) -> StaffTokenResponse:
    refresh_token = _refresh_token_from_request(request, body)
    if not refresh_token:
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    svc = StaffAuthService(db, r)
    result = svc.refresh_tokens(refresh_token)

    if result is None:
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    _set_refresh_cookie(response, result.refresh_token)
    return StaffTokenResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        role=result.role,
    )


# START_CONTRACT: logout
#   PURPOSE: Revoke the staff refresh token bound to the current session.
#   INPUTS:  body: StaffLogoutRequest, current_user, Redis client, Session.
#   OUTPUTS: 200 {"detail": "Logged out"}.
#   SIDE_EFFECTS: Redis write — refresh token blacklisted/removed.
#   LINKS:   INV-002, INV-010, services.staff_auth.
# END_CONTRACT: logout
@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
)
def logout(
    request: Request,
    response: Response,
    body: StaffLogoutRequest | None = None,
    current_user: dict = Depends(get_current_user),
    r: redis.Redis = Depends(get_redis),
    db: Session = Depends(get_db),
) -> dict:
    svc = StaffAuthService(db, r)
    refresh_token = _refresh_token_from_request(request, body)
    if refresh_token:
        svc.logout(refresh_token)
    _clear_refresh_cookie(response)
    return {"detail": "Logged out"}
