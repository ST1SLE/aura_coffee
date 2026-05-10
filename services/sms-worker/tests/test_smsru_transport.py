"""Tests for SMS.ru transport redaction."""

import logging

from sms_worker.clients import smsru


class _SuccessResponse:
    def __init__(self, data: dict[str, object]) -> None:
        self._data = data

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._data


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
    message = f"Ваш код: {code}"
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
        assert "from" not in kwargs["data"]
        return Response()

    monkeypatch.setattr(smsru.settings, "smsru_api_key", api_key)
    monkeypatch.setattr(smsru.settings, "smsru_sender_name", "")
    monkeypatch.setattr(smsru.httpx, "post", fake_post)

    with caplog.at_level(logging.ERROR, logger=smsru.logger.name):
        result = smsru.send_via_smsru(phone, message)

    assert result is False
    assert "SMS.ru error:" in caplog.text
    assert "recipient_ref=" in caplog.text
    assert "status='ERROR'" in caplog.text
    for sensitive in (phone, code, api_key, jwt, message):
        assert sensitive not in caplog.text


# START_CONTRACT: test_send_via_smsru_requires_recipient_level_ok
#   PURPOSE: Verify SMS.ru transport treats top-level OK plus recipient ERROR
#            as delivery failure, while redacting provider echoes.
#   INPUTS:  caplog: pytest LogCaptureFixture; monkeypatch: pytest MonkeyPatch.
#   OUTPUTS: None — assertions pin nested SMS.ru recipient-error handling.
#   SIDE_EFFECTS: Patches httpx.post and SMS.ru settings for this test only.
#   LINKS:   INV-013, INV-015, PDD §7.8, SMS.ru /sms/send response contract.
# END_CONTRACT: test_send_via_smsru_requires_recipient_level_ok
def test_send_via_smsru_requires_recipient_level_ok(caplog, monkeypatch) -> None:
    phone = "+79161234567"
    code = "654321"
    message = f"Ваш код: {code}"
    api_key = "smsru_live_api_key_secret"
    provider_status_text = (
        f"Need sender for phone={phone} code={code} api={api_key} "
        f"body={message}"
    )

    def fake_post(*args, **kwargs) -> _SuccessResponse:
        assert kwargs["data"]["api_id"] == api_key
        assert kwargs["data"]["to"] == phone
        assert kwargs["data"]["msg"] == message
        assert "from" not in kwargs["data"]
        return _SuccessResponse(
            {
                "status": "OK",
                "status_code": 100,
                "sms": {
                    phone: {
                        "status": "ERROR",
                        "status_code": 221,
                        "status_text": provider_status_text,
                    }
                },
                "balance": 99.5,
            }
        )

    monkeypatch.setattr(smsru.settings, "smsru_api_key", api_key)
    monkeypatch.setattr(smsru.settings, "smsru_sender_name", "")
    monkeypatch.setattr(smsru.httpx, "post", fake_post)

    with caplog.at_level(logging.ERROR, logger=smsru.logger.name):
        result = smsru.send_via_smsru(phone, message)

    assert result is False
    assert "SMS.ru recipient error:" in caplog.text
    assert "status='ERROR'" in caplog.text
    assert "status_code=221" in caplog.text
    assert "recipient_ref=" in caplog.text
    for sensitive in (phone, code, api_key, message):
        assert sensitive not in caplog.text


# START_CONTRACT: test_send_via_smsru_accepts_recipient_level_ok
#   PURPOSE: Verify SMS.ru transport reports success only when the recipient
#            item itself is OK and logs safe provider metadata.
#   INPUTS:  caplog: pytest LogCaptureFixture; monkeypatch: pytest MonkeyPatch.
#   OUTPUTS: None — assertions pin nested SMS.ru success handling.
#   SIDE_EFFECTS: Patches httpx.post and SMS.ru settings for this test only.
#   LINKS:   INV-013, INV-015, PDD §7.8, SMS.ru /sms/send response contract.
# END_CONTRACT: test_send_via_smsru_accepts_recipient_level_ok
def test_send_via_smsru_accepts_recipient_level_ok(caplog, monkeypatch) -> None:
    phone = "+79161234567"
    message = "Ваш код: 123456"
    api_key = "smsru_live_api_key_secret"
    sms_id = "000000-10000000"

    def fake_post(*args, **kwargs) -> _SuccessResponse:
        assert kwargs["data"]["api_id"] == api_key
        assert kwargs["data"]["to"] == phone
        assert kwargs["data"]["msg"] == message
        assert kwargs["data"]["from"] == "AURACOFFEE"
        return _SuccessResponse(
            {
                "status": "OK",
                "status_code": 100,
                "sms": {
                    phone: {
                        "status": "OK",
                        "status_code": 100,
                        "sms_id": sms_id,
                    }
                },
                "balance": 99.5,
            }
        )

    monkeypatch.setattr(smsru.settings, "smsru_api_key", api_key)
    monkeypatch.setattr(smsru.settings, "smsru_sender_name", "AURACOFFEE")
    monkeypatch.setattr(smsru.httpx, "post", fake_post)

    with caplog.at_level(logging.INFO, logger=smsru.logger.name):
        result = smsru.send_via_smsru(phone, message)

    assert result is True
    assert "SMS.ru accepted message:" in caplog.text
    assert sms_id in caplog.text
    assert phone not in caplog.text
    assert api_key not in caplog.text
