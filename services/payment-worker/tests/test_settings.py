"""RED: контракт Settings payment-worker (PDD §4.2, §8.1, INV-015).

Тесты должны падать до GREEN — текущий Settings содержит только redis_url.
"""

from __future__ import annotations


def test_settings_exposes_yukassa_and_db_fields(monkeypatch) -> None:
    monkeypatch.setenv("YUKASSA_SHOP_ID", "123")
    monkeypatch.setenv("YUKASSA_SECRET_KEY", "test_key")
    monkeypatch.setenv(
        "YUKASSA_WEBHOOK_IPS", "185.71.76.0/27,185.71.77.0/27"
    )
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@db/aura")
    monkeypatch.setenv("REDIS_URL", "redis://r:6379/0")

    # Принудительный reload, чтобы подхватить новый env
    import importlib
    import payment_worker.settings as settings_module

    importlib.reload(settings_module)

    s = settings_module.Settings()  # type: ignore[call-arg]
    assert s.yukassa_shop_id == "123"
    assert s.yukassa_secret_key == "test_key"
    # whitespace tolerance — см. 2.3
    assert s.yukassa_webhook_ips == ["185.71.76.0/27", "185.71.77.0/27"]
    assert s.database_url == "postgresql://u:p@db/aura"
    assert s.redis_url == "redis://r:6379/0"


def test_yukassa_base_url_default(monkeypatch) -> None:
    monkeypatch.delenv("YUKASSA_BASE_URL", raising=False)
    monkeypatch.setenv("YUKASSA_SHOP_ID", "x")
    monkeypatch.setenv("YUKASSA_SECRET_KEY", "y")
    monkeypatch.setenv("YUKASSA_WEBHOOK_IPS", "1.2.3.4")
    monkeypatch.setenv("DATABASE_URL", "sqlite://")

    import importlib
    import payment_worker.settings as settings_module

    importlib.reload(settings_module)

    s = settings_module.Settings()  # type: ignore[call-arg]
    assert s.yukassa_base_url == "https://api.yookassa.ru/v3"


def test_webhook_ips_parses_comma_list(monkeypatch) -> None:
    monkeypatch.setenv("YUKASSA_WEBHOOK_IPS", "185.71.76.1, 185.71.76.2")
    monkeypatch.setenv("YUKASSA_SHOP_ID", "x")
    monkeypatch.setenv("YUKASSA_SECRET_KEY", "y")
    monkeypatch.setenv("DATABASE_URL", "sqlite://")

    import importlib
    import payment_worker.settings as settings_module

    importlib.reload(settings_module)

    s = settings_module.Settings()  # type: ignore[call-arg]
    assert s.yukassa_webhook_ips == ["185.71.76.1", "185.71.76.2"]


def test_webhook_signature_settings_are_optional(monkeypatch) -> None:
    monkeypatch.setenv("YUKASSA_SHOP_ID", "x")
    monkeypatch.setenv("YUKASSA_SECRET_KEY", "y")
    monkeypatch.setenv("YUKASSA_WEBHOOK_SIGNATURE_SECRET", "webhook-secret")
    monkeypatch.setenv("YUKASSA_WEBHOOK_SIGNATURE_HEADER", "X-Custom-Signature")
    monkeypatch.setenv("DATABASE_URL", "sqlite://")

    import importlib
    import payment_worker.settings as settings_module

    importlib.reload(settings_module)

    s = settings_module.Settings()  # type: ignore[call-arg]
    assert s.yukassa_webhook_signature_secret == "webhook-secret"
    assert s.yukassa_webhook_signature_header == "X-Custom-Signature"


def test_yukassa_backend_defaults_to_live(monkeypatch) -> None:
    # Нужны валидные creds и прод base_url, чтобы safety-rail не помешал.
    monkeypatch.setenv("YUKASSA_SHOP_ID", "real")
    monkeypatch.setenv("YUKASSA_SECRET_KEY", "real")
    monkeypatch.setenv("YUKASSA_BASE_URL", "https://api.yookassa.ru/v3")

    import importlib
    import payment_worker.settings as settings_module

    importlib.reload(settings_module)
    s = settings_module.Settings()  # type: ignore[call-arg]
    assert s.yukassa_backend == "live"


def test_yukassa_backend_accepts_fake(monkeypatch) -> None:
    monkeypatch.setenv("YUKASSA_BACKEND", "fake")

    import importlib
    import payment_worker.settings as settings_module

    importlib.reload(settings_module)
    s = settings_module.Settings()  # type: ignore[call-arg]
    assert s.yukassa_backend == "fake"


def test_yukassa_backend_rejects_unknown(monkeypatch) -> None:
    from pydantic import ValidationError

    monkeypatch.setenv("YUKASSA_BACKEND", "mock")

    import importlib
    import payment_worker.settings as settings_module

    importlib.reload(settings_module)
    import pytest as _pytest

    with _pytest.raises(ValidationError):
        settings_module.Settings()  # type: ignore[call-arg]
