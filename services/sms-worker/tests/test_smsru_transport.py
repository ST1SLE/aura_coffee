"""Tests for SMS.ru transport redaction."""

import logging

from sms_worker.clients import smsru


# START_CONTRACT: test_send_via_smsru_error_logs_redacted_provider_metadata
#   PURPOSE: Verify SMS.ru provider error logging keeps only safe metadata and
#            redacts echoed phone, OTP, API key, JWT, and full SMS body.
#   INPUTS:  caplog: pytest LogCaptureFixture; monkeypatch: pytest MonkeyPatch.
#   OUTPUTS: None — assertions pin redacted provider-error log behavior.
#   SIDE_EFFECTS: Patches httpx.post and SMS.ru settings for this test only.
#   LINKS:   INV-013, INV-015, PDD §7.8, PDD §8.2.
# END_CONTRACT: test_send_via_smsru_error_logs_redacted_provider_metadata
def test_send_via_smsru_error_logs_redacted_provider_metadata(
    caplog, monkeypatch
) -> None:
    phone = "+79161234567"
    code = "123456"
    message = f"Код подтверждения: {code}. Aura Coffee"
    api_key = "smsru_live_api_key_secret"
    jwt = "eyJhbGciOiJIUzI1NiJ9.sensitive.signature"
    provider_status_text = (
        f"Rejected phone={phone} code={code} api={api_key} "
        f"jwt={jwt} body={message}"
    )

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "status": "ERROR",
                "status_text": provider_status_text,
                "sms": {
                    phone: {
                        "status": "ERROR",
                        "status_text": provider_status_text,
                    }
                },
            }

    def fake_post(*args, **kwargs) -> Response:
        assert kwargs["data"]["api_id"] == api_key
        assert kwargs["data"]["to"] == phone
        assert kwargs["data"]["msg"] == message
        return Response()

    monkeypatch.setattr(smsru.settings, "smsru_api_key", api_key)
    monkeypatch.setattr(smsru.httpx, "post", fake_post)

    with caplog.at_level(logging.ERROR, logger=smsru.logger.name):
        result = smsru.send_via_smsru(phone, message)

    assert result is False
    assert "SMS.ru error:" in caplog.text
    assert "recipient_ref=" in caplog.text
    assert "status='ERROR'" in caplog.text
    for sensitive in (phone, code, api_key, jwt, message):
        assert sensitive not in caplog.text
