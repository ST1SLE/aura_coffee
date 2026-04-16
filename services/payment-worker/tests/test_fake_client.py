"""RED: контракт FakeYukassaClient — возвращаемые формы create_payment и create_refund.

Форма ответа должна совпадать с live-клиентом, но payment_id — детерминирован
(префикс fake_), confirmation_url — localhost-адрес dev-стенда.
"""

from __future__ import annotations

import re


def test_create_payment_returns_fake_payment_id(monkeypatch) -> None:
    monkeypatch.setenv("YUKASSA_BACKEND", "fake")
    from payment_worker.yukassa_fake import FakeYukassaClient

    client = FakeYukassaClient()
    result = client.create_payment(
        amount_kopecks=30000,
        idempotency_key="k1",
        return_url="https://example.test/return",
        description="Order #x",
    )
    assert re.match(r"^fake_[0-9a-f]{32}$", result["payment_id"]), result["payment_id"]


def test_create_payment_confirmation_url_is_localhost(monkeypatch) -> None:
    monkeypatch.setenv("YUKASSA_BACKEND", "fake")
    from payment_worker.yukassa_fake import FakeYukassaClient

    client = FakeYukassaClient()
    result = client.create_payment(
        amount_kopecks=30000,
        idempotency_key="k1",
        return_url="https://example.test/return",
        description="Order #x",
    )
    assert result["confirmation_url"].startswith("http://localhost:")
    assert result["payment_id"] in result["confirmation_url"]


def test_create_payment_status_pending(monkeypatch) -> None:
    monkeypatch.setenv("YUKASSA_BACKEND", "fake")
    from payment_worker.yukassa_fake import FakeYukassaClient

    client = FakeYukassaClient()
    result = client.create_payment(
        amount_kopecks=30000,
        idempotency_key="k1",
        return_url="https://example.test/return",
        description="Order #x",
    )
    assert result["status"] == "pending"


def test_create_refund_returns_fake_refund_id(monkeypatch) -> None:
    monkeypatch.setenv("YUKASSA_BACKEND", "fake")
    from payment_worker.yukassa_fake import FakeYukassaClient

    client = FakeYukassaClient()
    result = client.create_refund(
        payment_id="fake_" + "a" * 32,
        amount_kopecks=30000,
        idempotency_key="r1",
    )
    # id возврата в ответе ЮKassa лежит в ключе "id"
    refund_id = result.get("id") or result.get("refund_id")
    assert refund_id is not None
    assert re.match(r"^fake_refund_[0-9a-f]+$", refund_id), refund_id
