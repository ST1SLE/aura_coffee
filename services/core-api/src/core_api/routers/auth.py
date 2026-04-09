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
    )

    return {"message": "OTP sent", "phone_hash": phone_hash}


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


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(
    body: RefreshRequest,
    current_user: dict = Depends(get_current_user),
    r: redis.Redis = Depends(get_redis),
) -> dict:
    auth_svc = AuthService(r)
    auth_svc.logout(body.refresh_token)
    return {"message": "Logged out"}
