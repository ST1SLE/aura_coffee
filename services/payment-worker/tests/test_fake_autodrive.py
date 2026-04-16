"""RED: FakeYukassaClient планирует webhook через Celery-таску yukassa_fake_callback.

Success → callback с "payment.succeeded". Canceled → "payment.canceled".
Http_error → httpx.RequestError синхронно и никаких callback'ов.
Callback POSTит канонический webhook на http://payment-webhook:8241/webhooks/yukassa.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest


def _fake_client(monkeypatch, outcome: str):
    monkeypatch.setenv("YUKASSA_BACKEND", "fake")
    monkeypatch.setenv("YUKASSA_FAKE_OUTCOME", outcome)
    # Принудительно перезагружаем settings, чтобы fake-клиент читал outcome
    import importlib
    import payment_worker.settings as settings_module

    importlib.reload(settings_module)
    import payment_worker.yukassa_fake as fake_module

    importlib.reload(fake_module)
    return fake_module


def test_create_payment_schedules_success_callback(monkeypatch) -> None:
    fake_module = _fake_client(monkeypatch, "success")

    with patch.object(
        fake_module.yukassa_fake_callback, "apply_async", autospec=True
    ) as scheduled:
        client = fake_module.FakeYukassaClient()
        client.create_payment(
            amount_kopecks=30000,
            idempotency_key="k1",
            return_url="https://example.test/",
            description="Order",
        )

    assert scheduled.call_count == 1
    call = scheduled.call_args
    # countdown=1
    assert call.kwargs.get("countdown") == 1
    # args содержат payment_id и event имя
    args = call.kwargs.get("args") or (call.args[0] if call.args else ())
    assert any("payment.succeeded" == a for a in args), args


def test_create_payment_schedules_cancel_callback(monkeypatch) -> None:
    fake_module = _fake_client(monkeypatch, "canceled")

    with patch.object(
        fake_module.yukassa_fake_callback, "apply_async", autospec=True
    ) as scheduled:
        client = fake_module.FakeYukassaClient()
        client.create_payment(
            amount_kopecks=30000,
            idempotency_key="k1",
            return_url="https://example.test/",
            description="Order",
        )

    args = scheduled.call_args.kwargs.get("args") or scheduled.call_args.args[0]
    assert any("payment.canceled" == a for a in args), args


def test_create_payment_http_error_outcome_raises(monkeypatch) -> None:
    fake_module = _fake_client(monkeypatch, "http_error")

    with patch.object(
        fake_module.yukassa_fake_callback, "apply_async", autospec=True
    ) as scheduled:
        client = fake_module.FakeYukassaClient()
        with pytest.raises(httpx.RequestError):
            client.create_payment(
                amount_kopecks=30000,
                idempotency_key="k1",
                return_url="https://example.test/",
                description="Order",
            )

    assert scheduled.call_count == 0


def test_callback_posts_canonical_webhook_body(monkeypatch) -> None:
    fake_module = _fake_client(monkeypatch, "success")

    posted = {}

    class _FakeClient:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, json=None, **kw):
            posted["url"] = url
            posted["json"] = json
            resp = MagicMock()
            resp.status_code = 200
            resp.raise_for_status = MagicMock()
            return resp

    with patch.object(fake_module.httpx, "Client", _FakeClient):
        # Вызываем таску как обычную функцию (через .run, без брокера)
        fake_module.yukassa_fake_callback.run(
            "fake_" + "a" * 32, "payment.succeeded"
        )

    assert posted["url"] == "http://payment-webhook:8241/webhooks/yukassa"
    body = posted["json"]
    assert body["event"] == "payment.succeeded"
    assert body["object"]["id"].startswith("fake_")
    assert body["object"]["status"] == "succeeded"
    assert body["object"]["paid"] is True
