# START_MODULE_CONTRACT
#   PURPOSE: Customer profile read/update — decrypts the stored phone for
#            display (masked) and lets the user change display_name and
#            preferred_language. INV-013: phone never leaves this module unmasked.
#   SCOPE:   get_profile, update_profile.
#   DEPENDS: M-SHARED (UserProfile), M-DATABASE, schemas.profile, utils.crypto
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §3, §5.2, INV-013
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   get_profile     - load profile and return masked-phone view
#   update_profile  - PATCH display_name / preferred_language
# END_MODULE_MAP
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


# START_CONTRACT: get_profile
#   PURPOSE: Load a customer profile, decrypt phone with the configured AES key,
#            and return a response with the phone masked to last 4 digits.
#   INPUTS:  user_id: UUID, db: Session
#   OUTPUTS: ProfileResponse | None (None when profile is absent)
#   SIDE_EFFECTS: DB SELECT only; phone decrypt happens in-process and never
#                 surfaces unmasked to caller (INV-013).
#   LINKS:   PDD §3, INV-013
# END_CONTRACT: get_profile
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


# START_CONTRACT: update_profile
#   PURPOSE: PATCH display_name / preferred_language for a customer profile;
#            phone is immutable here (handled via re-auth flow).
#   INPUTS:  user_id: UUID, data: ProfileUpdateRequest, db: Session
#   OUTPUTS: ProfileResponse | None
#   SIDE_EFFECTS: DB UPDATE + commit; phone decrypted just for masked response.
#   LINKS:   PDD §3, INV-013
# END_CONTRACT: update_profile
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
