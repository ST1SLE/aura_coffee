# START_MODULE_CONTRACT
#   PURPOSE: Customer User aggregate orchestration — get-or-create on phone
#            during OTP-init flow (PENDING_VERIFICATION) and activation on
#            successful OTP verify (ACTIVE) which spawns a LoyaltyAccount.
#            Drives PDD §6.5 PENDING_VERIFICATION → ACTIVE transition.
#   SCOPE:   get_or_create_user, activate_user, get_user_status.
#   DEPENDS: M-SHARED (User, UserProfile, LoyaltyAccount, UserStatus enum),
#            M-DATABASE, utils.crypto, settings
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §6.4, §6.5,
#            INV-002, INV-013, INV-016
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   UserInfo        - dataclass (user_id, status, is_new)
#   UserService     - get-or-create / activate / status-by-hash
# END_MODULE_MAP
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from core_api.settings import settings
from core_api.utils.crypto import encrypt_phone
from shared.enums import UserStatus
from shared.models.loyalty_account import LoyaltyAccount
from shared.models.user import User
from shared.models.user_profile import UserProfile


# START_CONTRACT: UserInfo
#   PURPOSE: Lightweight tuple-like return value for get_or_create_user with
#            user identity, status, and a new-vs-existing flag.
#   INPUTS:  user_id, status, is_new
#   OUTPUTS: dataclass instance.
#   SIDE_EFFECTS: none
# END_CONTRACT: UserInfo
@dataclass
class UserInfo:
    user_id: uuid.UUID
    status: UserStatus
    is_new: bool


# START_CONTRACT: UserService
#   PURPOSE: User aggregate write boundary used by the OTP / activation flow.
#            Stores phone in encrypted form (INV-013) and indexes by phone_hash.
#   INPUTS:  db: Session
#   OUTPUTS: UserService instance.
#   SIDE_EFFECTS: per method.
#   LINKS:   PDD §6.4, §6.5, INV-013
# END_CONTRACT: UserService
class UserService:
    def __init__(self, db: Session) -> None:
        self._db = db

    # START_CONTRACT: UserService.get_or_create_user
    #   PURPOSE: Look up an existing User by phone_hash; if absent, create a
    #            new one in PENDING_VERIFICATION with encrypted phone in the
    #            UserProfile sibling row.
    #   INPUTS:  phone: str (plaintext, transient), phone_hash: str (lookup key)
    #   OUTPUTS: UserInfo (user_id, status, is_new)
    #   SIDE_EFFECTS: DB SELECT + optional INSERT into users + user_profiles
    #                 + commit. Source: n/a → PENDING_VERIFICATION on creation.
    #   LINKS:   PDD §6.4, §6.5, INV-013, INV-016
    # END_CONTRACT: UserService.get_or_create_user
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

    # START_CONTRACT: UserService.activate_user
    #   PURPOSE: State transition PENDING_VERIFICATION → ACTIVE on OTP verify
    #            success; creates a fresh LoyaltyAccount row for the user.
    #   INPUTS:  user_id: UUID
    #   OUTPUTS: bool — True when transition applied, False on no-op (missing
    #            user or wrong source state).
    #   SIDE_EFFECTS: DB UPDATE users.status + INSERT loyalty_accounts + commit.
    #                 Source: PENDING_VERIFICATION. Target: ACTIVE.
    #   LINKS:   PDD §6.5, INV-016
    # END_CONTRACT: UserService.activate_user
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

    # START_CONTRACT: UserService.get_user_status
    #   PURPOSE: Return UserStatus for a known phone_hash (used by OTP-verify
    #            handler to branch is_new flow vs. existing-user activation).
    #   INPUTS:  phone_hash: str
    #   OUTPUTS: UserStatus | None
    #   SIDE_EFFECTS: DB SELECT only.
    #   LINKS:   INV-013
    # END_CONTRACT: UserService.get_user_status
    def get_user_status(self, phone_hash: str) -> UserStatus | None:
        """Получение статуса пользователя по phone_hash."""
        user = self._db.query(User).filter(User.phone_hash == phone_hash).first()
        return user.status if user else None
