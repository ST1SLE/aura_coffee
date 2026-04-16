"""HTTP-клиент ЮKassa (PDD §8.1).

Только REST: POST /v3/payments, GET /v3/payments/{id}, POST /v3/refunds.
Суммы всегда в строковом формате ``"123.45"`` из int-копеек; HTTP Basic
(``shop_id:secret_key``); ``Idempotency-Key`` на всех create-вызовах.
"""

from __future__ import annotations

from typing import Any

import httpx

DEFAULT_BASE_URL = "https://api.yookassa.ru/v3"


def _format_amount(kopecks: int) -> str:
    # "123.45" из 12345 копеек, "1.00" из 100, "0.01" из 1.
    return f"{kopecks // 100}.{kopecks % 100:02d}"


class YukassaClient:
    def __init__(
        self,
        shop_id: str,
        secret_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: httpx.Timeout | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout or httpx.Timeout(
            connect=10.0, read=30.0, write=30.0, pool=30.0
        )
        self._client = httpx.Client(
            auth=(shop_id, secret_key),
            timeout=self.timeout,
        )

    def create_payment(
        self,
        amount_kopecks: int,
        idempotency_key: str,
        return_url: str,
        description: str,
    ) -> dict[str, Any]:
        body = {
            "amount": {
                "value": _format_amount(amount_kopecks),
                "currency": "RUB",
            },
            "confirmation": {"type": "redirect", "return_url": return_url},
            "capture": True,
            "description": description,
        }
        resp = self._client.post(
            f"{self.base_url}/payments",
            json=body,
            headers={"Idempotency-Key": idempotency_key},
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "payment_id": data["id"],
            "confirmation_url": data.get("confirmation", {}).get("confirmation_url"),
            "status": data.get("status"),
        }

    def get_payment(self, payment_id: str) -> dict[str, Any]:
        resp = self._client.get(f"{self.base_url}/payments/{payment_id}")
        resp.raise_for_status()
        return resp.json()

    def create_refund(
        self,
        payment_id: str,
        amount_kopecks: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        body = {
            "payment_id": payment_id,
            "amount": {
                "value": _format_amount(amount_kopecks),
                "currency": "RUB",
            },
        }
        resp = self._client.post(
            f"{self.base_url}/refunds",
            json=body,
            headers={"Idempotency-Key": idempotency_key},
        )
        resp.raise_for_status()
        return resp.json()
