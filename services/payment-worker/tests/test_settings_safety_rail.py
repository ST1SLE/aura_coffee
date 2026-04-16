"""RED: safety-rail на Settings payment-worker (INV-015).

Live-режим не должен стартовать, если secrets пусты или base_url — это
sandbox/test/localhost. Fake-режим безопасен без creds.
"""

from __future__ import annotations

import importlib

import pytest
from pydantic import ValidationError


def _reload_settings():
    import payment_worker.settings as settings_module

    importlib.reload(settings_module)
    return settings_module


def _set_live_with(monkeypatch, **overrides) -> None:
    defaults = {
        "YUKASSA_BACKEND": "live",
        "YUKASSA_SHOP_ID": "real_shop",
        "YUKASSA_SECRET_KEY": "real_secret",
        "YUKASSA_BASE_URL": "https://api.yookassa.ru/v3",
    }
    defaults.update(overrides)
    for k, v in defaults.items():
        monkeypatch.setenv(k, v)


def test_live_with_empty_shop_id_refused(monkeypatch) -> None:
    _set_live_with(monkeypatch, YUKASSA_SHOP_ID="")
    mod = _reload_settings()
    with pytest.raises(ValidationError, match="INV-015"):
        mod.Settings()  # type: ignore[call-arg]


def test_live_with_empty_secret_refused(monkeypatch) -> None:
    _set_live_with(monkeypatch, YUKASSA_SECRET_KEY="")
    mod = _reload_settings()
    with pytest.raises(ValidationError, match="INV-015"):
        mod.Settings()  # type: ignore[call-arg]


def test_live_with_sandbox_url_refused(monkeypatch) -> None:
    _set_live_with(monkeypatch, YUKASSA_BASE_URL="https://api.sandbox.yookassa.ru/v3")
    mod = _reload_settings()
    with pytest.raises(ValidationError):
        mod.Settings()  # type: ignore[call-arg]


def test_live_with_test_url_refused(monkeypatch) -> None:
    _set_live_with(monkeypatch, YUKASSA_BASE_URL="https://api.test.yookassa.ru/v3")
    mod = _reload_settings()
    with pytest.raises(ValidationError):
        mod.Settings()  # type: ignore[call-arg]


def test_live_with_localhost_url_refused(monkeypatch) -> None:
    _set_live_with(monkeypatch, YUKASSA_BASE_URL="http://localhost:8000/v3")
    mod = _reload_settings()
    with pytest.raises(ValidationError):
        mod.Settings()  # type: ignore[call-arg]


def test_fake_with_empty_creds_accepted(monkeypatch) -> None:
    monkeypatch.setenv("YUKASSA_BACKEND", "fake")
    # creds намеренно не выставляем
    mod = _reload_settings()
    s = mod.Settings()  # type: ignore[call-arg]
    assert s.yukassa_backend == "fake"
    assert s.yukassa_shop_id == ""
