# START_MODULE_CONTRACT
#   PURPOSE: SMS OTP service — rate-limited (INV-012) creation, atomic Lua
#            verification, status updates. All persistence is in Redis.
#            Drives PDD §6.4 OTP lifecycle (CREATED→SENT→VERIFIED/FAILED).
#   SCOPE:   rate-limit check & increment, OTP creation (6-digit, TTL 300s),
#            verify_otp via Lua script, status update for sms-worker callback.
#   DEPENDS: M-SHARED (OTPStatus enum), Redis
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §6.4, INV-012, INV-013
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   VerifyResult     - enum of verify outcomes
#   VerifyResponse   - dataclass (result + remaining_attempts)
#   RateLimitResult  - dataclass (allowed + retry_after)
#   OTPService       - rate-limit/create/verify/update over Redis
# END_MODULE_MAP
import json
import secrets
from dataclasses import dataclass
from enum import Enum

import redis

from shared.enums import OTPStatus

OTP_TTL = 300
OTP_MAX_ATTEMPTS = 5

RATE_LIMITS = {
    "min": (1, 60),
    "hour": (5, 3600),
    "day": (10, 86400),
}

# Lua-скрипт для атомарной верификации OTP
_VERIFY_LUA = """
local key = KEYS[1]
local submitted_code = ARGV[1]

local data = redis.call('GET', key)
if not data then
    return cjson.encode({result = "expired"})
end

local otp = cjson.decode(data)

if otp.status ~= "sent" then
    return cjson.encode({result = "invalid_status", status = otp.status})
end

otp.attempts = otp.attempts + 1

if submitted_code == otp.code then
    otp.status = "verified"
    redis.call('DEL', key)
    return cjson.encode({result = "verified"})
end

if otp.attempts >= tonumber(ARGV[2]) then
    otp.status = "failed"
    redis.call('DEL', key)
    return cjson.encode({result = "failed", attempts = otp.attempts})
end

redis.call('SET', key, cjson.encode(otp), 'KEEPTTL')
return cjson.encode({result = "wrong_code", attempts = otp.attempts, max = tonumber(ARGV[2])})
"""


# START_CONTRACT: VerifyResult
#   PURPOSE: Discriminator for OTP verification outcomes — returned by the
#            atomic Lua verifier and surfaced by VerifyResponse.
#   INPUTS:  members: VERIFIED, WRONG_CODE, EXPIRED, FAILED, INVALID_STATUS
#   OUTPUTS: enum class.
#   SIDE_EFFECTS: none
# END_CONTRACT: VerifyResult
class VerifyResult(str, Enum):
    VERIFIED = "verified"
    WRONG_CODE = "wrong_code"
    EXPIRED = "expired"
    FAILED = "failed"
    INVALID_STATUS = "invalid_status"


# START_CONTRACT: VerifyResponse
#   PURPOSE: Verification outcome bundle — code result and attempts left.
#   INPUTS:  result: VerifyResult, remaining_attempts: int | None
#   OUTPUTS: dataclass instance.
#   SIDE_EFFECTS: none
# END_CONTRACT: VerifyResponse
@dataclass
class VerifyResponse:
    result: VerifyResult
    remaining_attempts: int | None = None


# START_CONTRACT: RateLimitResult
#   PURPOSE: Result of rate-limit probe — allowed flag + Retry-After hint.
#   INPUTS:  allowed: bool, retry_after: int | None
#   OUTPUTS: dataclass instance.
#   SIDE_EFFECTS: none
#   LINKS:   INV-012
# END_CONTRACT: RateLimitResult
@dataclass
class RateLimitResult:
    allowed: bool
    retry_after: int | None = None


# START_CONTRACT: OTPService
#   PURPOSE: Encapsulates OTP lifecycle (PDD §6.4) over Redis: rate-limit
#            counters, code creation with TTL, atomic Lua verify, status
#            updates for sms-worker callback.
#   INPUTS:  redis_client: redis.Redis
#   OUTPUTS: OTPService instance with registered Lua script.
#   SIDE_EFFECTS: registers verify script with Redis on construction.
#   LINKS:   PDD §6.4, INV-012, INV-013
# END_CONTRACT: OTPService
class OTPService:
    def __init__(self, redis_client: redis.Redis) -> None:
        self._redis = redis_client
        self._verify_script = self._redis.register_script(_VERIFY_LUA)

    def _otp_key(self, phone_hash: str) -> str:
        return f"otp:{phone_hash}"

    def _rate_key(self, phone_hash: str, window: str) -> str:
        return f"sms_rate:{phone_hash}:{window}"

    # START_CONTRACT: OTPService.check_rate_limit
    #   PURPOSE: Probe per-minute / per-hour / per-day OTP counters and report
    #            allowed=False with Retry-After when any window is exhausted.
    #   INPUTS:  phone_hash: str
    #   OUTPUTS: RateLimitResult
    #   SIDE_EFFECTS: Redis GET + TTL only.
    #   LINKS:   INV-012
    # END_CONTRACT: OTPService.check_rate_limit
    def check_rate_limit(self, phone_hash: str) -> RateLimitResult:
        """Проверка rate-limit (INV-012): 1/мин, 5/час, 10/день."""
        for window, (limit, _ttl) in RATE_LIMITS.items():
            key = self._rate_key(phone_hash, window)
            count = self._redis.get(key)
            if count is not None and int(count) >= limit:
                ttl = self._redis.ttl(key)
                return RateLimitResult(allowed=False, retry_after=max(ttl, 1))
        return RateLimitResult(allowed=True)

    # START_CONTRACT: OTPService.increment_rate_limits
    #   PURPOSE: Increment per-minute/hour/day OTP counters atomically with NX
    #            EXPIRE so the first hit pins the TTL window.
    #   INPUTS:  phone_hash: str
    #   OUTPUTS: None
    #   SIDE_EFFECTS: Redis pipeline INCR + EXPIRE NX on three keys.
    #   LINKS:   INV-012
    # END_CONTRACT: OTPService.increment_rate_limits
    def increment_rate_limits(self, phone_hash: str) -> None:
        """Инкремент всех трёх rate-limit счётчиков."""
        pipe = self._redis.pipeline()
        for window, (_limit, ttl) in RATE_LIMITS.items():
            key = self._rate_key(phone_hash, window)
            pipe.incr(key)
            pipe.expire(key, ttl, nx=True)
        pipe.execute()

    # START_CONTRACT: OTPService.create_otp
    #   PURPOSE: Mint a fresh 6-digit OTP, persist to Redis with status=CREATED
    #            and TTL=OTP_TTL, return the plaintext code (caller hands it to
    #            sms-worker via Celery — INV-013).
    #   INPUTS:  phone_hash: str
    #   OUTPUTS: str — 6-digit code
    #   SIDE_EFFECTS: Redis SET with EX=OTP_TTL on `otp:<phone_hash>`. Source
    #                 state: n/a → CREATED (PDD §6.4).
    #   LINKS:   PDD §6.4, INV-012, INV-013, INV-016
    # END_CONTRACT: OTPService.create_otp
    def create_otp(self, phone_hash: str) -> str:
        """Создание OTP: 6 цифр, статус CREATED, TTL 300с."""
        code = f"{secrets.randbelow(1_000_000):06d}"
        otp_data = json.dumps({
            "code": code,
            "attempts": 0,
            "status": OTPStatus.CREATED.value,
        })
        self._redis.set(self._otp_key(phone_hash), otp_data, ex=OTP_TTL)
        return code

    # START_CONTRACT: OTPService.verify_otp
    #   PURPOSE: Atomic OTP verification — single Lua call increments attempts,
    #            transitions SENT→VERIFIED on match, →FAILED at attempt cap,
    #            keeps OTP alive on wrong code with KEEPTTL.
    #   INPUTS:  phone_hash: str, code: str
    #   OUTPUTS: VerifyResponse — VERIFIED / WRONG_CODE / EXPIRED / FAILED /
    #            INVALID_STATUS, plus remaining_attempts.
    #   SIDE_EFFECTS: Redis EVALSHA on Lua script; modifies/deletes OTP key.
    #                 Transitions: SENT → VERIFIED | FAILED. Source: SENT.
    #   LINKS:   PDD §6.4, INV-016
    # END_CONTRACT: OTPService.verify_otp
    def verify_otp(self, phone_hash: str, code: str) -> VerifyResponse:
        """Атомарная верификация OTP через Lua-скрипт."""
        raw = self._verify_script(
            keys=[self._otp_key(phone_hash)],
            args=[code, str(OTP_MAX_ATTEMPTS)],
        )
        data = json.loads(raw)
        result = VerifyResult(data["result"])

        if result == VerifyResult.WRONG_CODE:
            remaining = data["max"] - data["attempts"]
            return VerifyResponse(result=result, remaining_attempts=remaining)
        if result == VerifyResult.FAILED:
            return VerifyResponse(result=result, remaining_attempts=0)

        return VerifyResponse(result=result)

    # START_CONTRACT: OTPService.update_otp_status
    #   PURPOSE: External (sms-worker callback) status update — flips OTP into
    #            SENT after gateway accepts, or FAILED on send error.
    #   INPUTS:  phone_hash: str, new_status: OTPStatus
    #   OUTPUTS: bool — True if record existed and was updated.
    #   SIDE_EFFECTS: Redis GET/SET/DEL preserving existing TTL. Transitions:
    #                 CREATED → SENT or CREATED/SENT → FAILED (key dropped).
    #   LINKS:   PDD §6.4, INV-016
    # END_CONTRACT: OTPService.update_otp_status
    def update_otp_status(self, phone_hash: str, new_status: OTPStatus) -> bool:
        """Обновление статуса OTP (для callback от sms-worker)."""
        key = self._otp_key(phone_hash)
        raw = self._redis.get(key)
        if raw is None:
            return False

        otp_data = json.loads(raw)
        otp_data["status"] = new_status.value
        ttl = self._redis.ttl(key)

        if new_status == OTPStatus.FAILED:
            self._redis.delete(key)
        elif ttl > 0:
            self._redis.set(key, json.dumps(otp_data), ex=ttl)
        else:
            self._redis.set(key, json.dumps(otp_data), ex=OTP_TTL)

        return True
