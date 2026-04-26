# START_MODULE_CONTRACT
#   PURPOSE: HTTP routes for customer SMS-OTP authentication under
#            /api/v1/auth — send code, verify code, refresh and logout.
#   SCOPE:   Customer-facing auth: phone normalization (utils.phone),
#            phone hashing/encryption (utils.crypto), OTP rate limit
#            (services.otp), token issue/refresh (services.auth),
#            Celery dispatch to sms-worker.
#   DEPENDS: M-SHARED (enums.UserStatus), M-DATABASE (Session),
#            core_api.services.{auth,otp,user},
#            core_api.deps.{auth,database,redis}.
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §6.4 OTP lifecycle,
#            §6.5 User lifecycle, INV-002, INV-012, INV-013.
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   router       - APIRouter("/api/v1/auth", tags=["auth"])
#   send_code    - POST /api/v1/auth/send-code
#   verify_code  - POST /api/v1/auth/verify-code
#   refresh      - POST /api/v1/auth/refresh
#   logout       - POST /api/v1/auth/logout
# END_MODULE_MAP

import redis
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core_api.deps.auth import get_current_user
from core_api.deps.database import get_db
from core_api.deps.redis import get_redis
from core_api.schemas.auth import (
    ErrorResponse,
    RefreshRequest,
    SendCodeRequest,
    TokenResponse,
    VerifyCodeRequest,
)
from core_api.services.auth import AuthService
from core_api.services.otp import OTPService, VerifyResult
from core_api.services.user import UserService
from core_api.utils.crypto import hash_phone
from core_api.utils.phone import normalize_phone
from shared.enums import UserStatus

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


# START_CONTRACT: send_code
#   PURPOSE: Accept phone, validate, enforce per-phone OTP rate limit, issue
#            a fresh OTP and dispatch SMS via Celery to sms-worker.
#   INPUTS:  body: SendCodeRequest (JSON), Session, Redis client.
#   OUTPUTS: 200 {"message", "phone_hash"}; 422 invalid phone;
#            403 blocked user; 429 rate limit hit (with Retry-After header).
#   SIDE_EFFECTS: Redis writes (rate counters + OTP record), DB upsert
#                 of pending user, Celery send_task to sms_worker queue.
#   LINKS:   PDD §6.4, §6.5, INV-012 (OTP rate-limit), INV-013 (phone
#            stored only as hash + AES-encrypted), services.otp/user/auth.
# END_CONTRACT: send_code
@router.post(
    "/send-code",
    status_code=status.HTTP_200_OK,
    responses={429: {"model": ErrorResponse}},
)
def send_code(
    body: SendCodeRequest,
    db: Session = Depends(get_db),
    r: redis.Redis = Depends(get_redis),
) -> dict:
    try:
        phone = normalize_phone(body.phone)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid phone number format")

    phone_hash = hash_phone(phone)

    user_svc = UserService(db)
    user_status = user_svc.get_user_status(phone_hash)
    if user_status == UserStatus.BLOCKED:
        raise HTTPException(status_code=403, detail="Account is blocked")

    otp_svc = OTPService(r)

    rate_check = otp_svc.check_rate_limit(phone_hash)
    if not rate_check.allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Too many requests. Retry after {rate_check.retry_after}s",
            headers={"Retry-After": str(rate_check.retry_after)},
        )

    user_info = user_svc.get_or_create_user(phone, phone_hash)
    otp_svc.increment_rate_limits(phone_hash)
    code = otp_svc.create_otp(phone_hash)

    # Отправка SMS через sms-worker (Celery send_task — без прямого импорта)
    from celery import Celery
    from core_api.settings import settings
    from core_api.utils.crypto import encrypt_phone

    key = bytes.fromhex(settings.encryption_key)
    encrypted_phone = encrypt_phone(phone, key)

    celery_app = Celery(broker=settings.redis_url)
    celery_app.send_task(
        "sms_worker.tasks.otp.send_otp_sms",
        args=[phone_hash, encrypted_phone.hex(), code],
        queue="sms",
    )

    return {"message": "OTP sent", "phone_hash": phone_hash}


# START_CONTRACT: verify_code
#   PURPOSE: Verify the OTP for a phone, activate PENDING_VERIFICATION
#            users, and issue access/refresh tokens.
#   INPUTS:  body: VerifyCodeRequest (JSON), Session, Redis client.
#   OUTPUTS: 200 TokenResponse; 401 wrong code / too many attempts;
#            409 OTP not yet delivered; 410 expired; 422 bad phone.
#   SIDE_EFFECTS: User row activation (status update), refresh token
#                 stored in Redis, OTP record consumed.
#   LINKS:   PDD §6.4 OTP lifecycle, §6.5 User lifecycle (INV-016),
#            INV-002 (server-side auth), services.auth/otp/user.
# END_CONTRACT: verify_code
@router.post(
    "/verify-code",
    response_model=TokenResponse,
    responses={401: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 410: {"model": ErrorResponse}},
)
def verify_code(
    body: VerifyCodeRequest,
    db: Session = Depends(get_db),
    r: redis.Redis = Depends(get_redis),
) -> TokenResponse:
    try:
        phone = normalize_phone(body.phone)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid phone number format")

    phone_hash = hash_phone(phone)
    otp_svc = OTPService(r)
    result = otp_svc.verify_otp(phone_hash, body.code)

    if result.result == VerifyResult.EXPIRED:
        raise HTTPException(status_code=410, detail="OTP expired")
    if result.result == VerifyResult.INVALID_STATUS:
        raise HTTPException(status_code=409, detail="OTP not yet delivered")
    if result.result == VerifyResult.WRONG_CODE:
        raise HTTPException(
            status_code=401,
            detail=f"Wrong code. {result.remaining_attempts} attempts remaining",
        )
    if result.result == VerifyResult.FAILED:
        raise HTTPException(
            status_code=401,
            detail="Too many failed attempts. Code invalidated",
        )

    # OTP verified — активация пользователя если нужно
    user_svc = UserService(db)
    user_info = user_svc.get_or_create_user(phone, phone_hash)

    if user_info.status == UserStatus.PENDING_VERIFICATION:
        user_svc.activate_user(user_info.user_id)

    auth_svc = AuthService(r)
    tokens = auth_svc.issue_tokens(user_info.user_id)

    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
    )


# START_CONTRACT: refresh
#   PURPOSE: Rotate access/refresh tokens for an authenticated session.
#   INPUTS:  body: RefreshRequest (JSON), Redis client.
#   OUTPUTS: 200 TokenResponse on success; 401 invalid/expired refresh.
#   SIDE_EFFECTS: Redis write — old refresh token revoked, new pair stored.
#   LINKS:   PDD §6.4, INV-002 (server-side validation), services.auth.
# END_CONTRACT: refresh
@router.post(
    "/refresh",
    response_model=TokenResponse,
    responses={401: {"model": ErrorResponse}},
)
def refresh(
    body: RefreshRequest,
    r: redis.Redis = Depends(get_redis),
) -> TokenResponse:
    auth_svc = AuthService(r)
    tokens = auth_svc.refresh_tokens(body.refresh_token)

    if tokens is None:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
    )


# START_CONTRACT: logout
#   PURPOSE: Revoke the refresh token bound to the current session.
#   INPUTS:  body: RefreshRequest, current_user (get_current_user),
#            Redis client.
#   OUTPUTS: 200 {"message": "Logged out"}.
#   SIDE_EFFECTS: Redis write — refresh token blacklisted/removed.
#   LINKS:   INV-002 (mutation requires auth), services.auth.
# END_CONTRACT: logout
@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(
    body: RefreshRequest,
    current_user: dict = Depends(get_current_user),
    r: redis.Redis = Depends(get_redis),
) -> dict:
    auth_svc = AuthService(r)
    auth_svc.logout(body.refresh_token)
    return {"message": "Logged out"}
