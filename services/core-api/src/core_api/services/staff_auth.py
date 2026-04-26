# START_MODULE_CONTRACT
#   PURPOSE: Staff (admin/barista/courier) authentication — login + bcrypt
#            password verification, JWT access + opaque refresh tokens with
#            Redis storage. Tokens carry role for INV-002 / INV-010 enforcement.
#   SCOPE:   authenticate, refresh_tokens, logout.
#   DEPENDS: M-SHARED (StaffAccount), M-DATABASE, Redis, PyJWT, bcrypt
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §4.5, INV-002, INV-010, INV-013
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   StaffTokenPair    - dataclass (access_token, refresh_token, role)
#   StaffAuthService  - login + token issuance + refresh rotation + logout
# END_MODULE_MAP
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
import redis
from sqlalchemy.orm import Session

from core_api.settings import settings
from shared.models.staff_account import StaffAccount


# START_CONTRACT: StaffTokenPair
#   PURPOSE: Bundle of issued tokens for a staff session.
#   INPUTS:  access_token: str, refresh_token: str, role: str
#   OUTPUTS: dataclass instance.
#   SIDE_EFFECTS: none
# END_CONTRACT: StaffTokenPair
@dataclass
class StaffTokenPair:
    access_token: str
    refresh_token: str
    role: str


# START_CONTRACT: StaffAuthService
#   PURPOSE: Staff-side authentication boundary — owns login validation,
#            access+refresh token minting, refresh rotation, logout.
#   INPUTS:  db: Session — DB to look up StaffAccount
#            redis_client: redis.Redis — backend for refresh token sessions
#   OUTPUTS: StaffAuthService instance.
#   SIDE_EFFECTS: per method; bcrypt verify + Redis SET/DEL on session keys.
#   LINKS:   PDD §4.5, INV-002, INV-010, INV-013
# END_CONTRACT: StaffAuthService
class StaffAuthService:
    def __init__(self, db: Session, redis_client: redis.Redis) -> None:
        self._db = db
        self._redis = redis_client

    # START_CONTRACT: StaffAuthService.authenticate
    #   PURPOSE: Verify staff credentials with bcrypt; on success, issue token pair.
    #   INPUTS:  login: str, password: str
    #   OUTPUTS: StaffTokenPair | None — None on unknown/inactive/wrong password.
    #   SIDE_EFFECTS: DB SELECT on staff_accounts; bcrypt comparison; on success
    #                 a Redis SET on `staff_refresh:<uuid>`.
    #   LINKS:   INV-002, INV-013 (no PII in tokens)
    # END_CONTRACT: StaffAuthService.authenticate
    def authenticate(self, login: str, password: str) -> StaffTokenPair | None:
        """Аутентификация по логину/паролю. Возвращает токены или None."""
        staff = (
            self._db.query(StaffAccount)
            .filter(StaffAccount.login == login)
            .first()
        )
        if staff is None:
            return None
        if not staff.is_active:
            return None
        if not bcrypt.checkpw(
            password.encode("utf-8"),
            staff.password_hash.encode("utf-8"),
        ):
            return None

        return self._issue_tokens(staff.id, staff.role.value)

    # START_CONTRACT: StaffAuthService.refresh_tokens
    #   PURPOSE: Single-use refresh rotation — old token deleted, new pair issued.
    #   INPUTS:  refresh_token: str
    #   OUTPUTS: StaffTokenPair | None
    #   SIDE_EFFECTS: Redis GET + DEL on the old key, SET on the new one.
    # END_CONTRACT: StaffAuthService.refresh_tokens
    def refresh_tokens(self, refresh_token: str) -> StaffTokenPair | None:
        """Ротация refresh token: валидация → удаление → новая пара."""
        key = f"staff_refresh:{refresh_token}"
        raw = self._redis.get(key)
        if raw is None:
            return None

        self._redis.delete(key)
        session_data = json.loads(raw)
        staff_id = uuid.UUID(session_data["staff_id"])
        role = session_data["role"]
        return self._issue_tokens(staff_id, role)

    # START_CONTRACT: StaffAuthService.logout
    #   PURPOSE: Invalidate the staff refresh token session.
    #   INPUTS:  refresh_token: str
    #   OUTPUTS: bool — True if a session was deleted.
    #   SIDE_EFFECTS: Redis DEL on `staff_refresh:<uuid>`.
    # END_CONTRACT: StaffAuthService.logout
    def logout(self, refresh_token: str) -> bool:
        """Удаление staff refresh token из Redis."""
        return bool(self._redis.delete(f"staff_refresh:{refresh_token}"))

    def _issue_tokens(self, staff_id: uuid.UUID, role: str) -> StaffTokenPair:
        """Выпуск пары access + refresh токенов для сотрудника."""
        access_token = self._create_access_token(staff_id, role)
        refresh_token = self._create_refresh_token(staff_id, role)
        return StaffTokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            role=role,
        )

    def _create_access_token(self, staff_id: uuid.UUID, role: str) -> str:
        """JWT access token с ролью сотрудника."""
        now = datetime.now(UTC)
        payload = {
            "sub": str(staff_id),
            "role": role,
            "iat": now,
            "exp": now + timedelta(seconds=settings.access_token_ttl),
        }
        return jwt.encode(
            payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )

    def _create_refresh_token(self, staff_id: uuid.UUID, role: str) -> str:
        """Opaque UUID refresh token для сотрудника, хранится в Redis."""
        token = str(uuid.uuid4())
        session_data = json.dumps({
            "staff_id": str(staff_id),
            "role": role,
            "issued_at": datetime.now(UTC).isoformat(),
        })
        self._redis.set(
            f"staff_refresh:{token}",
            session_data,
            ex=settings.refresh_token_ttl,
        )
        return token
