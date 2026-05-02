# START_MODULE_CONTRACT
#   PURPOSE: Staff (admin/barista/courier) authentication — login + bcrypt
#            password verification, JWT access + opaque refresh tokens with
#            Redis storage and indexed revocation. Tokens carry role for
#            INV-002 / INV-010 enforcement.
#   SCOPE:   authenticate with failed-login throttling, refresh_tokens,
#            revoke_staff_sessions, logout.
#   DEPENDS: M-SHARED (StaffAccount), M-DATABASE, Redis, PyJWT, bcrypt
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §4.5, INV-002, INV-010, INV-013
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   StaffTokenPair        - dataclass (access_token, refresh_token, role)
#   StaffLoginRateLimited - failed-login throttle signal carrying retry_after
#   StaffAuthService      - login + token issuance + refresh rotation + revocation + logout
# END_MODULE_MAP
import hashlib
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
from shared.grace.logging import get_grace_logger

_grace_log = get_grace_logger("CoreApi")

STAFF_LOGIN_RATE_LIMITS = {
    "login": (5, 900),
    "ip": (30, 900),
}


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


# START_CONTRACT: StaffLoginRateLimited
#   PURPOSE: Domain error for staff-login brute-force throttling; router maps
#            it to HTTP 429 with Retry-After.
#   INPUTS:  retry_after: int — seconds until the next allowed attempt.
#   OUTPUTS: Exception with .retry_after.
#   SIDE_EFFECTS: none
#   LINKS:   INV-002, INV-013
# END_CONTRACT: StaffLoginRateLimited
class StaffLoginRateLimited(Exception):
    def __init__(self, retry_after: int) -> None:
        super().__init__("staff_login_rate_limited")
        self.retry_after = retry_after


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

    def _refresh_key(self, refresh_token: str) -> str:
        return f"staff_refresh:{refresh_token}"

    def _sessions_index_key(self, staff_id: uuid.UUID) -> str:
        return f"staff_sessions:{staff_id}"

    def _login_rate_key(self, kind: str, raw_value: str) -> str:
        normalized = raw_value.strip().lower()
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]
        return f"staff_login_rate:{kind}:{digest}"

    def _login_rate_dimensions(
        self, login: str, source_ip: str | None
    ) -> list[tuple[str, int, int]]:
        dimensions = [
            (
                self._login_rate_key("login", login),
                *STAFF_LOGIN_RATE_LIMITS["login"],
            )
        ]
        if source_ip:
            dimensions.append(
                (
                    self._login_rate_key("ip", source_ip),
                    *STAFF_LOGIN_RATE_LIMITS["ip"],
                )
            )
        return dimensions

    def _current_login_retry_after(
        self, login: str, source_ip: str | None
    ) -> int | None:
        retry_after = 0
        for key, limit, _ttl in self._login_rate_dimensions(login, source_ip):
            raw = self._redis.get(key)
            if raw is None:
                continue
            try:
                count = int(raw)
            except (TypeError, ValueError):
                continue
            if count >= limit:
                try:
                    ttl = int(self._redis.ttl(key))
                except (TypeError, ValueError):
                    ttl = 1
                retry_after = max(retry_after, max(ttl, 1))
        return retry_after or None

    def _record_failed_login(self, login: str, source_ip: str | None) -> None:
        pipe = self._redis.pipeline()
        for key, _limit, ttl in self._login_rate_dimensions(login, source_ip):
            pipe.incr(key)
            pipe.expire(key, ttl, nx=True)
        pipe.execute()

    def _clear_failed_login_counters(
        self, login: str, source_ip: str | None
    ) -> None:
        del source_ip
        self._redis.delete(self._login_rate_key("login", login))

    def _log_login_attempt(self, *, outcome: str) -> None:
        _grace_log.block(
            "staff.auth_login",
            "BLOCK_AUTH_VERIFY",
            outcome=outcome,
        )

    def _remember_refresh_token(
        self,
        staff_id: uuid.UUID,
        refresh_token: str,
    ) -> None:
        index_key = self._sessions_index_key(staff_id)
        self._redis.sadd(index_key, refresh_token)
        self._redis.expire(index_key, settings.refresh_token_ttl)

    def _forget_refresh_token(
        self,
        refresh_token: str,
        staff_id: uuid.UUID | None,
    ) -> bool:
        deleted = bool(self._redis.delete(self._refresh_key(refresh_token)))
        if staff_id is not None:
            self._redis.srem(self._sessions_index_key(staff_id), refresh_token)
        return deleted

    def _current_staff_allows_refresh(self, staff_id: uuid.UUID, role: str) -> bool:
        staff = (
            self._db.query(StaffAccount)
            .filter(StaffAccount.id == staff_id)
            .first()
        )
        if staff is None or not staff.is_active:
            return False
        return staff.role.value == role

    # START_CONTRACT: StaffAuthService.authenticate
    #   PURPOSE: Verify staff credentials with bcrypt; on success, issue token pair.
    #   INPUTS:  login: str, password: str
    #   OUTPUTS: StaffTokenPair | None — None on unknown/inactive/wrong password.
    #   SIDE_EFFECTS: DB SELECT on staff_accounts; bcrypt comparison; on success
    #                 a Redis SET on `staff_refresh:<uuid>`.
    #   LINKS:   INV-002, INV-013 (no PII in tokens)
    # END_CONTRACT: StaffAuthService.authenticate
    def authenticate(
        self,
        login: str,
        password: str,
        source_ip: str | None = None,
    ) -> StaffTokenPair | None:
        """Аутентификация по логину/паролю. Возвращает токены или None."""
        retry_after = self._current_login_retry_after(login, source_ip)
        if retry_after is not None:
            self._log_login_attempt(outcome="rate_limited")
            raise StaffLoginRateLimited(retry_after)

        staff = (
            self._db.query(StaffAccount)
            .filter(StaffAccount.login == login)
            .first()
        )
        if staff is None:
            self._record_failed_login(login, source_ip)
            self._log_login_attempt(outcome="invalid_credentials")
            return None
        if not staff.is_active:
            self._record_failed_login(login, source_ip)
            self._log_login_attempt(outcome="invalid_credentials")
            return None
        if not bcrypt.checkpw(
            password.encode("utf-8"),
            staff.password_hash.encode("utf-8"),
        ):
            self._record_failed_login(login, source_ip)
            self._log_login_attempt(outcome="invalid_credentials")
            return None

        self._clear_failed_login_counters(login, source_ip)
        self._log_login_attempt(outcome="success")
        return self._issue_tokens(staff.id, staff.role.value)

    # START_CONTRACT: StaffAuthService.refresh_tokens
    #   PURPOSE: Single-use refresh rotation — old token deleted, new pair issued.
    #   INPUTS:  refresh_token: str
    #   OUTPUTS: StaffTokenPair | None
    #   SIDE_EFFECTS: Redis GET + DEL on the old key, SET on the new one.
    # END_CONTRACT: StaffAuthService.refresh_tokens
    def refresh_tokens(self, refresh_token: str) -> StaffTokenPair | None:
        """Ротация refresh token: валидация → удаление → новая пара."""
        key = self._refresh_key(refresh_token)
        raw = self._redis.get(key)
        if raw is None:
            return None

        session_data = json.loads(raw)
        staff_id = uuid.UUID(session_data["staff_id"])
        role = session_data["role"]

        if not self._current_staff_allows_refresh(staff_id, role):
            self._forget_refresh_token(refresh_token, staff_id)
            self.revoke_staff_sessions(staff_id)
            return None

        self._forget_refresh_token(refresh_token, staff_id)
        return self._issue_tokens(staff_id, role)

    # START_CONTRACT: StaffAuthService.revoke_staff_sessions
    #   PURPOSE: Revoke every indexed staff refresh session for a staff account,
    #            used by future deactivate/delete flows and failed status checks.
    #   INPUTS:  staff_id: UUID
    #   OUTPUTS: int — number of session keys deleted.
    #   SIDE_EFFECTS: Redis SMEMBERS + DEL on `staff_refresh:*`, DEL on
    #                 `staff_sessions:<staff_id>`.
    #   LINKS:   INV-002, INV-010.
    # END_CONTRACT: StaffAuthService.revoke_staff_sessions
    def revoke_staff_sessions(self, staff_id: uuid.UUID) -> int:
        index_key = self._sessions_index_key(staff_id)
        tokens = self._redis.smembers(index_key)
        deleted = 0
        for raw_token in tokens:
            token = raw_token.decode() if isinstance(raw_token, bytes) else str(raw_token)
            deleted += int(self._redis.delete(self._refresh_key(token)))
        self._redis.delete(index_key)
        return deleted

    # START_CONTRACT: StaffAuthService.logout
    #   PURPOSE: Invalidate the staff refresh token session.
    #   INPUTS:  refresh_token: str
    #   OUTPUTS: bool — True if a session was deleted.
    #   SIDE_EFFECTS: Redis DEL on `staff_refresh:<uuid>`.
    # END_CONTRACT: StaffAuthService.logout
    def logout(self, refresh_token: str) -> bool:
        """Удаление staff refresh token из Redis."""
        raw = self._redis.get(self._refresh_key(refresh_token))
        staff_id = None
        if isinstance(raw, (str, bytes, bytearray)):
            staff_id = uuid.UUID(json.loads(raw)["staff_id"])
        return self._forget_refresh_token(refresh_token, staff_id)

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
        self._redis.set(self._refresh_key(token), session_data, ex=settings.refresh_token_ttl)
        self._remember_refresh_token(staff_id, token)
        return token
