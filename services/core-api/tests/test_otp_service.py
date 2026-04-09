import json

import pytest
import redis

from core_api.services.otp import OTPService, VerifyResult

import os

REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15")


@pytest.fixture
def r() -> redis.Redis:
    client = redis.Redis.from_url(REDIS_URL)
    client.flushdb()
    yield client
    client.flushdb()
    client.close()


@pytest.fixture
def otp_svc(r: redis.Redis) -> OTPService:
    return OTPService(r)


class TestCreateOTP:
    def test_creates_6_digit_code(self, otp_svc: OTPService) -> None:
        code = otp_svc.create_otp("testhash")
        assert len(code) == 6
        assert code.isdigit()

    def test_stores_in_redis(self, otp_svc: OTPService, r: redis.Redis) -> None:
        otp_svc.create_otp("testhash")
        raw = r.get("otp:testhash")
        assert raw is not None
        data = json.loads(raw)
        assert data["status"] == "created"
        assert data["attempts"] == 0


class TestVerifyOTP:
    def _create_sent_otp(self, otp_svc: OTPService, r: redis.Redis, ph: str) -> str:
        code = otp_svc.create_otp(ph)
        otp_svc.update_otp_status(ph, __import__("shared.enums", fromlist=["OTPStatus"]).OTPStatus.SENT)
        return code

    def test_correct_code(self, otp_svc: OTPService, r: redis.Redis) -> None:
        code = self._create_sent_otp(otp_svc, r, "ph1")
        result = otp_svc.verify_otp("ph1", code)
        assert result.result == VerifyResult.VERIFIED

    def test_wrong_code(self, otp_svc: OTPService, r: redis.Redis) -> None:
        self._create_sent_otp(otp_svc, r, "ph2")
        result = otp_svc.verify_otp("ph2", "000000")
        assert result.result == VerifyResult.WRONG_CODE
        assert result.remaining_attempts == 4

    def test_exhausted_attempts(self, otp_svc: OTPService, r: redis.Redis) -> None:
        self._create_sent_otp(otp_svc, r, "ph3")
        for _ in range(4):
            otp_svc.verify_otp("ph3", "000000")
        result = otp_svc.verify_otp("ph3", "000000")
        assert result.result == VerifyResult.FAILED

    def test_expired(self, otp_svc: OTPService, r: redis.Redis) -> None:
        result = otp_svc.verify_otp("nonexistent", "123456")
        assert result.result == VerifyResult.EXPIRED


class TestRateLimit:
    def test_allowed(self, otp_svc: OTPService) -> None:
        result = otp_svc.check_rate_limit("ph_rl")
        assert result.allowed is True

    def test_per_minute_exceeded(self, otp_svc: OTPService) -> None:
        otp_svc.increment_rate_limits("ph_rl2")
        result = otp_svc.check_rate_limit("ph_rl2")
        assert result.allowed is False
        assert result.retry_after is not None
        assert result.retry_after > 0

    def test_per_hour_exceeded(self, otp_svc: OTPService, r: redis.Redis) -> None:
        r.set("sms_rate:ph_rl3:min", "0", ex=60)
        r.set("sms_rate:ph_rl3:hour", "5", ex=3600)
        r.set("sms_rate:ph_rl3:day", "5", ex=86400)
        result = otp_svc.check_rate_limit("ph_rl3")
        assert result.allowed is False

    def test_per_day_exceeded(self, otp_svc: OTPService, r: redis.Redis) -> None:
        r.set("sms_rate:ph_rl4:min", "0", ex=60)
        r.set("sms_rate:ph_rl4:hour", "0", ex=3600)
        r.set("sms_rate:ph_rl4:day", "10", ex=86400)
        result = otp_svc.check_rate_limit("ph_rl4")
        assert result.allowed is False
