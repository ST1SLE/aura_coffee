"""Fake-клиент ЮKassa для локальной разработки и CI (INV-001 сохраняется: платёж
моделируется, а не пропускается).

Возвращает детерминированные идентификаторы, шлёт канонический webhook через
Celery-callback с countdown=1. Всё как у настоящего провайдера, но без HTTP
до api.yookassa.ru. Переключается `YUKASSA_BACKEND=fake`; параметр
`YUKASSA_FAKE_OUTCOME` управляет итогом: success / canceled / http_error.
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

import httpx

from payment_worker.main import celery_app

logger = logging.getLogger(__name__)

_WEBHOOK_URL = "http://payment-webhook:8241/webhooks/yukassa"


class FakeYukassaClient:
    """Drop-in замена YukassaClient без сетевых вызовов."""

    def create_payment(
        self,
        amount_kopecks: int,
        idempotency_key: str,
        return_url: str,
        description: str,
    ) -> dict[str, Any]:
        outcome = os.getenv("YUKASSA_FAKE_OUTCOME", "success")

        if outcome == "http_error":
            # Имитируем обрыв соединения — Celery должен пойти по retry+компенсации.
            raise httpx.RequestError("fake: simulated HTTP error")

        payment_id = f"fake_{uuid.uuid4().hex}"
        nginx_port = os.getenv("NGINX_PORT", "8240")
        confirmation_url = (
            f"http://localhost:{nginx_port}/dev/yukassa-sandbox/{payment_id}"
        )

        event = "payment.canceled" if outcome == "canceled" else "payment.succeeded"
        yukassa_fake_callback.apply_async(
            args=(payment_id, event),
            countdown=1,
        )

        return {
            "payment_id": payment_id,
            "confirmation_url": confirmation_url,
            "status": "pending",
        }

    def get_payment(self, payment_id: str) -> dict[str, Any]:
        # Минимум, который нужен вызывающему коду — статус и id.
        return {"id": payment_id, "status": "pending"}

    def create_refund(
        self,
        payment_id: str,
        amount_kopecks: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        refund_id = f"fake_refund_{uuid.uuid4().hex}"
        # В проде возврат также приезжает webhook'ом refund.succeeded; дёргаем
        # callback на том же канале.
        yukassa_fake_callback.apply_async(
            args=(payment_id, "refund.succeeded"),
            countdown=1,
            kwargs={"refund_id": refund_id},
        )
        return {
            "id": refund_id,
            "payment_id": payment_id,
            "status": "pending",
            "amount": {"value": f"{amount_kopecks // 100}.{amount_kopecks % 100:02d}"},
        }


def _canonical_body(payment_id: str, event: str, refund_id: str | None) -> dict:
    if event.startswith("refund."):
        obj = {
            "id": refund_id or f"fake_refund_{uuid.uuid4().hex}",
            "payment_id": payment_id,
            "status": "succeeded" if event == "refund.succeeded" else "canceled",
        }
    else:
        succeeded = event == "payment.succeeded"
        obj = {
            "id": payment_id,
            "status": "succeeded" if succeeded else "canceled",
            "paid": succeeded,
        }
    return {"event": event, "object": obj}


@celery_app.task(name="yukassa_fake_callback", max_retries=0)
def yukassa_fake_callback(
    payment_id: str,
    event: str,
    refund_id: str | None = None,
) -> None:
    """POSTит канонический webhook на локальный payment-webhook.

    Ошибки HTTP логируем и возвращаемся — ретраев нет намеренно (см. дизайн
    green: callback-task non-retrying contract).
    """
    body = _canonical_body(payment_id, event, refund_id)
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(_WEBHOOK_URL, json=body)
            if resp.status_code >= 400:
                logger.warning(
                    "yukassa_fake_callback: webhook returned %s for %s",
                    resp.status_code,
                    event,
                )
    except httpx.HTTPError as exc:
        logger.warning("yukassa_fake_callback: POST failed: %s", exc)
