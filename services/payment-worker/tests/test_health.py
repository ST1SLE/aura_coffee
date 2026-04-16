"""RED: GET /health на payment_worker.webhook.app отдаёт yukassa_backend.

Deploy smoke tests должны уметь проверить режим бэкенда на боевом окружении.
"""

from __future__ import annotations

import importlib

from fastapi.testclient import TestClient


def _reload_app():
    import payment_worker.settings as settings_module
    import payment_worker.webhook as webhook_module

    importlib.reload(settings_module)
    importlib.reload(webhook_module)
    return webhook_module


def test_health_reports_backend_live(monkeypatch) -> None:
    monkeypatch.setenv("YUKASSA_BACKEND", "live")
    monkeypatch.setenv("YUKASSA_SHOP_ID", "real")
    monkeypatch.setenv("YUKASSA_SECRET_KEY", "real")
    monkeypatch.setenv("YUKASSA_BASE_URL", "https://api.yookassa.ru/v3")

    mod = _reload_app()
    client = TestClient(mod.app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json().get("yukassa_backend") == "live"


def test_health_reports_backend_fake(monkeypatch) -> None:
    monkeypatch.setenv("YUKASSA_BACKEND", "fake")

    mod = _reload_app()
    client = TestClient(mod.app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json().get("yukassa_backend") == "fake"
