"""RED: контракт YukassaClient (PDD §8.1).

Эти тесты импортируют payment_worker.yukassa_client — модуля ещё нет.
Ожидаемое поведение: ImportError до GREEN.
"""

from __future__ import annotations

import base64
import json

import httpx
import pytest
import respx


BASE = "https://api.yookassa.ru/v3"


def _attr_or_key(obj, name):
    """YukassaClient.create_payment может вернуть dict, dataclass или pydantic.

    Вспомогательная функция — один способ чтения в тестах.
    """
    if isinstance(obj, dict):
        return obj[name]
    return getattr(obj, name)


@respx.mock
def test_create_payment_posts_to_v3_payments() -> None:
    route = respx.post(f"{BASE}/payments").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "pay_xyz",
                "status": "pending",
                "confirmation": {"confirmation_url": "https://yoo/confirm"},
            },
        )
    )

    from payment_worker.yukassa_client import YukassaClient

    client = YukassaClient(
        shop_id="s", secret_key="k", base_url=BASE
    )
    client.create_payment(
        amount_kopecks=12345,
        idempotency_key="uuid-1",
        return_url="https://r",
        description="Order #1",
    )

    assert route.called
    request: httpx.Request = route.calls.last.request
    assert request.method == "POST"
    expected_auth = "Basic " + base64.b64encode(b"s:k").decode()
    assert request.headers["authorization"] == expected_auth
    assert request.headers["idempotency-key"] == "uuid-1"

    body = json.loads(request.content.decode())
    assert body["amount"]["value"] == "123.45"
    assert body["amount"]["currency"] == "RUB"
    assert body["description"] == "Order #1"
    assert body["confirmation"]["return_url"] == "https://r"


@respx.mock
def test_create_payment_returns_id_confirmation_status() -> None:
    respx.post(f"{BASE}/payments").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "pay_xyz",
                "status": "pending",
                "confirmation": {"confirmation_url": "https://yoo/confirm"},
            },
        )
    )

    from payment_worker.yukassa_client import YukassaClient

    client = YukassaClient(shop_id="s", secret_key="k", base_url=BASE)
    result = client.create_payment(
        amount_kopecks=100,
        idempotency_key="x",
        return_url="https://r",
        description="d",
    )

    assert _attr_or_key(result, "payment_id") == "pay_xyz"
    assert _attr_or_key(result, "confirmation_url") == "https://yoo/confirm"
    assert _attr_or_key(result, "status") == "pending"


@respx.mock
def test_get_payment_hits_v3_payments_id_with_auth_no_idempotency() -> None:
    route = respx.get(f"{BASE}/payments/pay_abc").mock(
        return_value=httpx.Response(200, json={"id": "pay_abc", "status": "succeeded"})
    )

    from payment_worker.yukassa_client import YukassaClient

    client = YukassaClient(shop_id="s", secret_key="k", base_url=BASE)
    client.get_payment("pay_abc")

    assert route.called
    request: httpx.Request = route.calls.last.request
    assert request.method == "GET"
    expected_auth = "Basic " + base64.b64encode(b"s:k").decode()
    assert request.headers["authorization"] == expected_auth
    # GET не требует idempotency-key
    assert "idempotency-key" not in [h.lower() for h in request.headers.keys()]


@respx.mock
def test_create_refund_posts_full_refund() -> None:
    route = respx.post(f"{BASE}/refunds").mock(
        return_value=httpx.Response(
            200,
            json={"id": "ref_abc", "status": "pending", "payment_id": "pay_abc"},
        )
    )

    from payment_worker.yukassa_client import YukassaClient

    client = YukassaClient(shop_id="s", secret_key="k", base_url=BASE)
    client.create_refund(
        payment_id="pay_abc",
        amount_kopecks=12345,
        idempotency_key="uuid-2",
    )

    assert route.called
    request: httpx.Request = route.calls.last.request
    assert request.method == "POST"
    assert request.headers["idempotency-key"] == "uuid-2"
    body = json.loads(request.content.decode())
    assert body["payment_id"] == "pay_abc"
    assert body["amount"]["value"] == "123.45"
    assert body["amount"]["currency"] == "RUB"


def test_client_timeout_is_10_connect_30_read() -> None:
    from payment_worker.yukassa_client import YukassaClient

    client = YukassaClient(shop_id="s", secret_key="k", base_url=BASE)

    # Допускаем одну из форм: client.timeout (httpx.Timeout) или client._client.timeout
    timeout = getattr(client, "timeout", None) or client._client.timeout  # type: ignore[attr-defined]
    assert float(timeout.connect) == 10.0
    assert float(timeout.read) == 30.0


@pytest.mark.parametrize(
    "kopecks,formatted",
    [
        (100, "1.00"),
        (12345, "123.45"),
        (1, "0.01"),
        (100000, "1000.00"),
    ],
)
@respx.mock
def test_amount_formatting_edge_cases(kopecks: int, formatted: str) -> None:
    route = respx.post(f"{BASE}/payments").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "pay_x",
                "status": "pending",
                "confirmation": {"confirmation_url": "https://x"},
            },
        )
    )

    from payment_worker.yukassa_client import YukassaClient

    YukassaClient(shop_id="s", secret_key="k", base_url=BASE).create_payment(
        amount_kopecks=kopecks,
        idempotency_key="uuid",
        return_url="https://r",
        description="d",
    )
    body = json.loads(route.calls.last.request.content.decode())
    assert body["amount"]["value"] == formatted
