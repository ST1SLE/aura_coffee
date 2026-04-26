"""HTTP-клиент ЮKassa (PDD §8.1).

Только REST: POST /v3/payments, GET /v3/payments/{id}, POST /v3/refunds.
Суммы всегда в строковом формате ``"123.45"`` из int-копеек; HTTP Basic
(``shop_id:secret_key``); ``Idempotency-Key`` на всех create-вызовах.
"""

# START_MODULE_CONTRACT
#   PURPOSE: Live thin REST client for YuKassa. Wraps three endpoints
#            (POST /v3/payments, GET /v3/payments/{id}, POST /v3/refunds)
#            with HTTP Basic auth (shop_id, secret_key) and Idempotency-Key
#            on every create call (PDD §8.1). Currency is fixed to RUB.
#   SCOPE:   YukassaClient class + module default base URL. Credentials are
#            injected by the caller from env (no hardcoded secrets — INV-015).
#   DEPENDS: httpx
#   LINKS:   docs/development-plan.xml M-PAYMENT-WORKER, PDD §8.1, INV-015
#            (no secrets in code), INV-005 (full refund only — caller-enforced)
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   DEFAULT_BASE_URL - production YuKassa API base URL
#   YukassaClient    - REST client with create_payment / get_payment / create_refund
# END_MODULE_MAP

from __future__ import annotations

from typing import Any

import httpx

DEFAULT_BASE_URL = "https://api.yookassa.ru/v3"


def _format_amount(kopecks: int) -> str:
    # "123.45" из 12345 копеек, "1.00" из 100, "0.01" из 1.
    return f"{kopecks // 100}.{kopecks % 100:02d}"


# START_CONTRACT: YukassaClient
#   PURPOSE: Live YuKassa REST client; opens a persistent httpx.Client with
#            HTTP Basic auth (shop_id, secret_key) bound for the lifetime of
#            the instance.
#   INPUTS:  shop_id: str — YuKassa shop id (must be non-empty in live mode)
#            secret_key: str — YuKassa secret key (must be non-empty in live mode)
#            base_url: str — YuKassa API base URL (default: production)
#            timeout: httpx.Timeout | None — optional override (default 10/30/30/30s)
#   OUTPUTS: YukassaClient instance.
#   SIDE_EFFECTS: opens an httpx.Client (no network until a method is called).
#   LINKS:   PDD §8.1, INV-015 (no secrets in code)
# END_CONTRACT: YukassaClient
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

    # START_CONTRACT: YukassaClient.create_payment
    #   PURPOSE: POST /v3/payments — request a payment intent at YuKassa.
    #            Returns the YuKassa payment id and confirmation URL the
    #            client redirects the user to (PDD §6.2, AWAITING_CONFIRMATION).
    #   INPUTS:  amount_kopecks: int — gross amount in kopecks
    #            idempotency_key: str — required Idempotency-Key header value
    #            return_url: str — post-payment redirect URL
    #            description: str — human-readable payment description
    #   OUTPUTS: dict[str, Any] — {"payment_id", "confirmation_url", "status"}
    #   SIDE_EFFECTS: external HTTP POST to YuKassa /v3/payments. Raises on
    #                 non-2xx (httpx.HTTPStatusError) or transport failure
    #                 (httpx.RequestError).
    #   LINKS:   PDD §8.1, §6.2 (PENDING -> AWAITING_CONFIRMATION),
    #            INV-016 (explicit transitions enforced by caller)
    # END_CONTRACT: YukassaClient.create_payment
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

    # START_CONTRACT: YukassaClient.get_payment
    #   PURPOSE: GET /v3/payments/{id} — poll payment status (used by the
    #            15-minute timeout fallback per AGENTS.md / PDD §6.1).
    #   INPUTS:  payment_id: str — YuKassa payment id
    #   OUTPUTS: dict[str, Any] — raw YuKassa payload
    #   SIDE_EFFECTS: external HTTP GET to YuKassa; raises on non-2xx /
    #                 transport failure.
    #   LINKS:   PDD §8.1, §6.1 (timeout fallback)
    # END_CONTRACT: YukassaClient.get_payment
    def get_payment(self, payment_id: str) -> dict[str, Any]:
        resp = self._client.get(f"{self.base_url}/payments/{payment_id}")
        resp.raise_for_status()
        return resp.json()

    # START_CONTRACT: YukassaClient.create_refund
    #   PURPOSE: POST /v3/refunds — request a full refund against an existing
    #            YuKassa payment id. Caller is responsible for enforcing
    #            INV-005 (full refund only, amount equals original gross).
    #   INPUTS:  payment_id: str — YuKassa payment id (the original)
    #            amount_kopecks: int — refund amount in kopecks
    #            idempotency_key: str — required Idempotency-Key header value
    #   OUTPUTS: dict[str, Any] — raw YuKassa refund payload
    #   SIDE_EFFECTS: external HTTP POST to YuKassa /v3/refunds; raises on
    #                 non-2xx / transport failure.
    #   LINKS:   PDD §8.1, §6.2 (SUCCEEDED -> REFUND_PENDING — caller),
    #            INV-005 (full refund only), INV-016 (explicit transitions)
    # END_CONTRACT: YukassaClient.create_refund
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
