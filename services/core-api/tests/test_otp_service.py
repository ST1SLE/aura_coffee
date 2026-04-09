import json

import fakeredis
import pytest

from core_api.services.otp import OTPService, VerifyResult
from shared.enums import OTPStatus


class TestCreateOTP:
    def test_creates_6_digit_code(self, otp_svc: OTPService) -> None:
        code = otp_svc.create_otp("testhash")
        assert len(code) == 6
        assert code.isdigit()

    def test_stores_in_redis(self, otp_svc: OTPService, r: fakeredis.FakeRedis) -> None:
        otp_svc.create_otp("testhash")
        raw = r.get("otp:testhash")
        assert raw is not None
        data = json.loads(raw)
        assert data["status"] == "created"
        assert data["attempts"] == 0


class TestVerifyOTP:
    def _create_sent_otp(self, otp_svc: OTPService, r: fakeredis.FakeRedis, ph: str) -> str:
        code = otp_svc.create_otp(ph)
        otp_svc.update_otp_status(ph, OTPStatus.SENT)
        return code

    def test_correct_code(self, otp_svc: OTPService, r: fakeredis.FakeRedis) -> None:
        code = self._create_sent_otp(otp_svc, r, "ph1")
        result = otp_svc.verify_otp("ph1", code)
        assert result.result == VerifyResult.VERIFIED

    def test_wrong_code(self, otp_svc: OTPService, r: fakeredis.FakeRedis) -> None:
        self._create_sent_otp(otp_svc, r, "ph2")
        result = otp_svc.verify_otp("ph2", "000000")
        assert result.result == VerifyResult.WRONG_CODE
        assert result.remaining_attempts == 4

    def test_exhausted_attempts(self, otp_svc: OTPService, r: fakeredis.FakeRedis) -> None:
        self._create_sent_otp(otp_svc, r, "ph3")
        for _ in range(4):
            otp_svc.verify_otp("ph3", "000000")
        result = otp_svc.verify_otp("ph3", "000000")
        assert result.result == VerifyResult.FAILED

    def test_expired(self, otp_svc: OTPService) -> None:
        result = otp_svc.verify_otp("nonexistent", "123456")
        assert result.result == VerifyResult.EXPIRED

    def test_correct_code_on_final_attempt(self, otp_svc: OTPService, r: fakeredis.FakeRedis) -> None:
        """Правильный код на 5-й (последней) попытке → VERIFIED, не FAILED."""
        code = self._create_sent_otp(otp_svc, r, "ph_final")
        for _ in range(4):
            otp_svc.verify_otp("ph_final", "000000")
        result = otp_svc.verify_otp("ph_final", code)
        assert result.result == VerifyResult.VERIFIED

    def test_invalid_status_created(self, otp_svc: OTPService) -> None:
        """Верификация OTP в статусе 'created' (не 'sent') → INVALID_STATUS."""
        otp_svc.create_otp("ph_created")
        result = otp_svc.verify_otp("ph_created", "123456")
        assert result.result == VerifyResult.INVALID_STATUS

    def test_remaining_attempts_decrement(self, otp_svc: OTPService, r: fakeredis.FakeRedis) -> None:
        """Проверка убывания remaining_attempts: 4, 3, 2."""
        self._create_sent_otp(otp_svc, r, "ph_dec")
        results = []
        for _ in range(3):
            res = otp_svc.verify_otp("ph_dec", "000000")
            results.append(res.remaining_attempts)
        assert results == [4, 3, 2]

    def test_key_deleted_after_verified(self, otp_svc: OTPService, r: fakeredis.FakeRedis) -> None:
        """После VERIFIED ключ удалён из Redis."""
        code = self._create_sent_otp(otp_svc, r, "ph_del_v")
        otp_svc.verify_otp("ph_del_v", code)
        assert r.get("otp:ph_del_v") is None

    def test_key_deleted_after_failed(self, otp_svc: OTPService, r: fakeredis.FakeRedis) -> None:
        """После исчерпания попыток ключ удалён из Redis."""
        self._create_sent_otp(otp_svc, r, "ph_del_f")
        for _ in range(5):
            otp_svc.verify_otp("ph_del_f", "000000")
        assert r.get("otp:ph_del_f") is None


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

    def test_per_hour_exceeded(self, otp_svc: OTPService, r: fakeredis.FakeRedis) -> None:
        r.set("sms_rate:ph_rl3:min", "0", ex=60)
        r.set("sms_rate:ph_rl3:hour", "5", ex=3600)
        r.set("sms_rate:ph_rl3:day", "5", ex=86400)
        result = otp_svc.check_rate_limit("ph_rl3")
        assert result.allowed is False

    def test_per_day_exceeded(self, otp_svc: OTPService, r: fakeredis.FakeRedis) -> None:
        r.set("sms_rate:ph_rl4:min", "0", ex=60)
        r.set("sms_rate:ph_rl4:hour", "0", ex=3600)
        r.set("sms_rate:ph_rl4:day", "10", ex=86400)
        result = otp_svc.check_rate_limit("ph_rl4")
        assert result.allowed is False

    def test_exact_boundary_per_minute(self, otp_svc: OTPService) -> None:
        """Ровно 1 SMS отправлена → per-minute лимит заблокирован."""
        otp_svc.increment_rate_limits("ph_boundary")
        result = otp_svc.check_rate_limit("ph_boundary")
        assert result.allowed is False

    def test_retry_after_positive(self, otp_svc: OTPService) -> None:
        """retry_after — положительное целое число при превышении лимита."""
        otp_svc.increment_rate_limits("ph_retry")
        result = otp_svc.check_rate_limit("ph_retry")
        assert result.retry_after is not None
        assert isinstance(result.retry_after, int)
        assert result.retry_after > 0
