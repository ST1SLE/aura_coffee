"""Тесты log-транспорта."""

from unittest.mock import patch

from sms_worker.clients.log import send_via_log


def test_send_via_log_logs_message_and_returns_true(caplog) -> None:
    import logging
    with caplog.at_level(logging.INFO):
        result = send_via_log("+79161234567", "Код подтверждения: 123456. Aura Coffee")

    assert result is True
    assert "+79161234567" in caplog.text
    assert "Код подтверждения: 123456. Aura Coffee" in caplog.text
    assert "[SMS:log]" in caplog.text


def test_send_via_log_never_calls_httpx() -> None:
    with patch("httpx.post") as mock_post:
        send_via_log("+79161234567", "Код подтверждения: 654321. Aura Coffee")
        mock_post.assert_not_called()
