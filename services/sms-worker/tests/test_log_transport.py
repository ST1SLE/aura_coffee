"""Тесты log-транспорта."""

from unittest.mock import patch

from sms_worker.clients.log import send_via_log


def test_send_via_log_logs_redacted_metadata_and_returns_true(caplog) -> None:
    import logging

    phone = "+79161234567"
    message = "Код подтверждения: 123456. Aura Coffee"

    with caplog.at_level(logging.INFO):
        result = send_via_log(phone, message)

    assert result is True
    assert "[SMS:log]" in caplog.text
    assert "kind=otp" in caplog.text
    assert f"message_len={len(message)}" in caplog.text
    assert phone not in caplog.text
    assert message not in caplog.text
    assert "123456" not in caplog.text


def test_send_via_log_never_calls_httpx() -> None:
    with patch("httpx.post") as mock_post:
        send_via_log("+79161234567", "Код подтверждения: 654321. Aura Coffee")
        mock_post.assert_not_called()
