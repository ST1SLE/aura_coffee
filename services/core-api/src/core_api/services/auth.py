# START_MODULE_CONTRACT
#   PURPOSE: Customer JWT auth — issues HS256 access tokens + opaque UUID refresh
#            tokens stored in Redis with TTL. Owns token rotation, indexed
#            session revocation, logout, and optional DB status checks.
#   SCOPE:   create/issue/refresh/decode/revoke access+refresh tokens for customers.
#   DEPENDS: M-SHARED (settings via core_api.settings), M-DATABASE, Redis, PyJWT
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §6.4 (OTP→ACTIVE issues
#            tokens), INV-002 (server-side auth on every mutation), INV-013
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   TokenPair    - dataclass holding (access_token, refresh_token)
#   AuthService  - JWT issuance, refresh rotation, revoke, logout, decode
# END_MODULE_MAP
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
import redis
from sqlalchemy.orm import Session

from core_api.settings import settings
from core_api.services.session_subjects import is_customer_active


# START_CONTRACT: TokenPair
#   PURPOSE: Lightweight container for issued access + refresh token pair.
#   INPUTS:  access_token: str
#            refresh_token: str
#   OUTPUTS: dataclass instance.
#   SIDE_EFFECTS: none
# END_CONTRACT: TokenPair
@dataclass
class TokenPair:
    access_token: str
    refresh_token: str


# START_CONTRACT: AuthService
#   PURPOSE: Customer-side authentication boundary — token issuance, rotation,
#            invalidation. The single source for JWT minting.
#   INPUTS:  redis_client: redis.Redis — connection pool for session storage
#   OUTPUTS: AuthService instance.
#   SIDE_EFFECTS: stores opaque refresh tokens in Redis (`session:<uuid>` keys
#                 with TTL); JWT signed with shared secret. INV-013: tokens
#                 contain only `sub` (user_id) and `role`, no PII.
#   LINKS:   PDD §6.4 (token issuance after OTP verify), INV-002, INV-013
# END_CONTRACT: AuthService
class AuthService:
    def __init__(self, redis_client: redis.Redis) -> None:
        self._redis = redis_client

    def _session_key(self, refresh_token: str) -> str:
        return f"session:{refresh_token}"

    def _sessions_index_key(self, user_id: uuid.UUID) -> str:
        return f"user_sessions:{user_id}"

    def _remember_refresh_token(self, user_id: uuid.UUID, refresh_token: str) -> None:
        index_key = self._sessions_index_key(user_id)
        self._redis.sadd(index_key, refresh_token)
        self._redis.expire(index_key, settings.refresh_token_ttl)

    def _forget_refresh_token(
        self,
        refresh_token: str,
        user_id: uuid.UUID | None,
    ) -> bool:
        deleted = bool(self._redis.delete(self._session_key(refresh_token)))
        if user_id is not None:
            self._redis.srem(self._sessions_index_key(user_id), refresh_token)
        return deleted

    # START_CONTRACT: AuthService.create_access_token
    #   PURPOSE: Mint a short-lived HS256 JWT carrying user_id + role.
    #   INPUTS:  user_id: UUID
    #            role: str — defaults to "customer"
    #   OUTPUTS: str — encoded JWT.
    #   SIDE_EFFECTS: none (pure crypto operation).
    #   LINKS:   INV-002
    # END_CONTRACT: AuthService.create_access_token
    def create_access_token(self, user_id: uuid.UUID, role: str = "customer") -> str:
        """JWT access token: HS256, TTL из настроек."""
        now = datetime.now(UTC)
        payload = {
            "sub": str(user_id),
            "role": role,
            "iat": now,
            "exp": now + timedelta(seconds=settings.access_token_ttl),
        }
        return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    # START_CONTRACT: AuthService.create_refresh_token
    #   PURPOSE: Generate an opaque UUID refresh token and persist a session
    #            blob to Redis with configured TTL (typically 7 days).
    #   INPUTS:  user_id: UUID
    #   OUTPUTS: str — refresh token (opaque UUID).
    #   SIDE_EFFECTS: Redis SET with EX=refresh_token_ttl on `session:<uuid>`.
    # END_CONTRACT: AuthService.create_refresh_token
    def create_refresh_token(self, user_id: uuid.UUID) -> str:
        """Opaque UUID refresh token, хранится в Redis с TTL 7 дней."""
        token = str(uuid.uuid4())
        session_data = json.dumps({
            "user_id": str(user_id),
            "issued_at": datetime.now(UTC).isoformat(),
        })
        self._redis.set(self._session_key(token), session_data, ex=settings.refresh_token_ttl)
        self._remember_refresh_token(user_id, token)
        return token

    # START_CONTRACT: AuthService.issue_tokens
    #   PURPOSE: One-shot helper that returns a fresh (access, refresh) pair.
    #   INPUTS:  user_id: UUID, role: str (default "customer")
    #   OUTPUTS: TokenPair
    #   SIDE_EFFECTS: see create_refresh_token (Redis write).
    # END_CONTRACT: AuthService.issue_tokens
    def issue_tokens(self, user_id: uuid.UUID, role: str = "customer") -> TokenPair:
        """Выпуск пары access + refresh токенов."""
        return TokenPair(
            access_token=self.create_access_token(user_id, role),
            refresh_token=self.create_refresh_token(user_id),
        )

    # START_CONTRACT: AuthService.refresh_tokens
    #   PURPOSE: Refresh-token rotation: validate old token, delete it, issue
    #            a fresh pair (single-use semantics).
    #   INPUTS:  refresh_token: str, db: optional Session for current user-state check.
    #   OUTPUTS: TokenPair on success, None when token unknown/expired.
    #   SIDE_EFFECTS: Redis GET + DEL on old session key, SET on new one.
    # END_CONTRACT: AuthService.refresh_tokens
    def refresh_tokens(
        self,
        refresh_token: str,
        db: Session | None = None,
    ) -> TokenPair | None:
        """Ротация: валидация старого refresh → удаление → выпуск новой пары."""
        key = self._session_key(refresh_token)
        raw = self._redis.get(key)
        if raw is None:
            return None

        session_data = json.loads(raw)
        user_id = uuid.UUID(session_data["user_id"])

        if db is not None and not is_customer_active(
            db, user_id, require_present=True
        ):
            self._forget_refresh_token(refresh_token, user_id)
            self.revoke_user_sessions(user_id)
            return None

        self._forget_refresh_token(refresh_token, user_id)
        return self.issue_tokens(user_id)

    # START_CONTRACT: AuthService.revoke_user_sessions
    #   PURPOSE: Revoke every indexed customer refresh session for a user,
    #            used by admin block/delete flows.
    #   INPUTS:  user_id: UUID
    #   OUTPUTS: int — number of session keys deleted.
    #   SIDE_EFFECTS: Redis SMEMBERS + DEL on `session:*`, DEL on
    #                 `user_sessions:<user_id>`.
    #   LINKS:   PDD §6.5, INV-002.
    # END_CONTRACT: AuthService.revoke_user_sessions
    def revoke_user_sessions(self, user_id: uuid.UUID) -> int:
        index_key = self._sessions_index_key(user_id)
        tokens = self._redis.smembers(index_key)
        deleted = 0
        for raw_token in tokens:
            token = raw_token.decode() if isinstance(raw_token, bytes) else str(raw_token)
            deleted += int(self._redis.delete(self._session_key(token)))
        self._redis.delete(index_key)
        return deleted

    # START_CONTRACT: AuthService.logout
    #   PURPOSE: Invalidate a refresh token (cooperative logout — access token
    #            cannot be revoked early, only its refresh).
    #   INPUTS:  refresh_token: str
    #   OUTPUTS: bool — True if a session was deleted.
    #   SIDE_EFFECTS: Redis DEL on `session:<uuid>`.
    # END_CONTRACT: AuthService.logout
    def logout(self, refresh_token: str) -> bool:
        """Удаление refresh token из Redis."""
        raw = self._redis.get(self._session_key(refresh_token))
        user_id = None
        if isinstance(raw, (str, bytes, bytearray)):
            user_id = uuid.UUID(json.loads(raw)["user_id"])
        return self._forget_refresh_token(refresh_token, user_id)

    # START_CONTRACT: AuthService.decode_access_token
    #   PURPOSE: Verify HS256 signature + expiry on access token, return claims.
    #   INPUTS:  token: str
    #   OUTPUTS: dict — JWT claims (sub, role, iat, exp).
    #   SIDE_EFFECTS: none. Raises jwt.PyJWTError on invalid/expired token.
    #   LINKS:   INV-002
    # END_CONTRACT: AuthService.decode_access_token
    @staticmethod
    def decode_access_token(token: str) -> dict:
        """Декодирование и валидация JWT access token."""
        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
