import uuid

from sqlalchemy.orm import Session

from core_api.schemas.profile import ProfileResponse, ProfileUpdateRequest
from core_api.settings import settings
from core_api.utils.crypto import decrypt_phone
from shared.models.user_profile import UserProfile


def _mask_phone(phone: str) -> str:
    """Маскирование телефона: видны только последние 4 цифры."""
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) < 5:
        return phone
    last4 = digits[-4:]
    return f"+{digits[0]} *** *** {last4[:2]} {last4[2:]}"


def get_profile(user_id: uuid.UUID, db: Session) -> ProfileResponse | None:
    """Получение профиля клиента с маскированным телефоном."""
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if profile is None:
        return None

    key = bytes.fromhex(settings.encryption_key)
    plaintext_phone = decrypt_phone(profile.phone, key)
    masked = _mask_phone(plaintext_phone)

    return ProfileResponse(
        user_id=profile.user_id,
        phone_masked=masked,
        display_name=profile.display_name,
        preferred_language=profile.preferred_language,
    )


def update_profile(
    user_id: uuid.UUID, data: ProfileUpdateRequest, db: Session
) -> ProfileResponse | None:
    """Частичное обновление профиля клиента."""
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if profile is None:
        return None

    if data.display_name is not None:
        profile.display_name = data.display_name
    if data.preferred_language is not None:
        profile.preferred_language = data.preferred_language

    db.commit()
    db.refresh(profile)

    key = bytes.fromhex(settings.encryption_key)
    plaintext_phone = decrypt_phone(profile.phone, key)
    masked = _mask_phone(plaintext_phone)

    return ProfileResponse(
        user_id=profile.user_id,
        phone_masked=masked,
        display_name=profile.display_name,
        preferred_language=profile.preferred_language,
    )
