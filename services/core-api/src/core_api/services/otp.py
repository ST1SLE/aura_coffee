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


class VerifyResult(str, Enum):
    VERIFIED = "verified"
    WRONG_CODE = "wrong_code"
    EXPIRED = "expired"
    FAILED = "failed"
    INVALID_STATUS = "invalid_status"


@dataclass
class VerifyResponse:
    result: VerifyResult
    remaining_attempts: int | None = None


@dataclass
class RateLimitResult:
    allowed: bool
    retry_after: int | None = None


class OTPService:
    def __init__(self, redis_client: redis.Redis) -> None:
        self._redis = redis_client
        self._verify_script = self._redis.register_script(_VERIFY_LUA)

    def _otp_key(self, phone_hash: str) -> str:
        return f"otp:{phone_hash}"

    def _rate_key(self, phone_hash: str, window: str) -> str:
        return f"sms_rate:{phone_hash}:{window}"

    def check_rate_limit(self, phone_hash: str) -> RateLimitResult:
        """Проверка rate-limit (INV-012): 1/мин, 5/час, 10/день."""
        for window, (limit, _ttl) in RATE_LIMITS.items():
            key = self._rate_key(phone_hash, window)
            count = self._redis.get(key)
            if count is not None and int(count) >= limit:
                ttl = self._redis.ttl(key)
                return RateLimitResult(allowed=False, retry_after=max(ttl, 1))
        return RateLimitResult(allowed=True)

    def increment_rate_limits(self, phone_hash: str) -> None:
        """Инкремент всех трёх rate-limit счётчиков."""
        pipe = self._redis.pipeline()
        for window, (_limit, ttl) in RATE_LIMITS.items():
            key = self._rate_key(phone_hash, window)
            pipe.incr(key)
            pipe.expire(key, ttl, nx=True)
        pipe.execute()

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
