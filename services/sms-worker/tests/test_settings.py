"""Тесты валидации Settings."""

import pytest
from pydantic import ValidationError

from sms_worker.settings import Settings


def test_smsru_backend_rejects_placeholder_key() -> None:
    with pytest.raises(ValidationError, match="SMSRU_API_KEY"):
        Settings(sms_backend="smsru", smsru_api_key="your-smsru-api-key")


def test_smsru_backend_requires_nonempty_key() -> None:
    with pytest.raises(ValidationError, match="SMSRU_API_KEY"):
        Settings(sms_backend="smsru", smsru_api_key="")


def test_log_backend_accepts_empty_key() -> None:
    s = Settings(sms_backend="log", smsru_api_key="")
    assert s.sms_backend == "log"


def test_smsru_backend_accepts_real_key() -> None:
    s = Settings(sms_backend="smsru", smsru_api_key="abc123real")
    assert s.sms_backend == "smsru"


def test_smsru_sender_name_loads_from_settings() -> None:
    s = Settings(
        sms_backend="smsru",
        smsru_api_key="abc123real",
        smsru_sender_name="AURACOFFEE",
    )
    assert s.smsru_sender_name == "AURACOFFEE"
