import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from core_api.settings import settings
from core_api.utils.crypto import encrypt_phone
from shared.enums import UserStatus
from shared.models.loyalty_account import LoyaltyAccount
from shared.models.user import User
from shared.models.user_profile import UserProfile


@dataclass
class UserInfo:
    user_id: uuid.UUID
    status: UserStatus
    is_new: bool


class UserService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_or_create_user(self, phone: str, phone_hash: str) -> UserInfo:
        """Поиск по phone_hash или создание PENDING_VERIFICATION."""
        user = self._db.query(User).filter(User.phone_hash == phone_hash).first()

        if user is not None:
            return UserInfo(
                user_id=user.id, status=user.status, is_new=False
            )

        key = bytes.fromhex(settings.encryption_key)
        encrypted_phone = encrypt_phone(phone, key)

        user = User(phone_hash=phone_hash, status=UserStatus.PENDING_VERIFICATION)
        self._db.add(user)
        self._db.flush()

        profile = UserProfile(user_id=user.id, phone=encrypted_phone)
        self._db.add(profile)
        self._db.commit()

        return UserInfo(user_id=user.id, status=user.status, is_new=True)

    def activate_user(self, user_id: uuid.UUID) -> bool:
        """PENDING_VERIFICATION → ACTIVE + создание loyalty_accounts."""
        user = self._db.query(User).filter(User.id == user_id).first()
        if user is None or user.status != UserStatus.PENDING_VERIFICATION:
            return False

        user.status = UserStatus.ACTIVE
        loyalty = LoyaltyAccount(user_id=user_id)
        self._db.add(loyalty)
        self._db.commit()
        return True

    def get_user_status(self, phone_hash: str) -> UserStatus | None:
        """Получение статуса пользователя по phone_hash."""
        user = self._db.query(User).filter(User.phone_hash == phone_hash).first()
        return user.status if user else None
