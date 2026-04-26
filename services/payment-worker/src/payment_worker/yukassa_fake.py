"""Fake-клиент ЮKassa для локальной разработки и CI (INV-001 сохраняется: платёж
моделируется, а не пропускается).

Возвращает детерминированные идентификаторы, шлёт канонический webhook через
Celery-callback с countdown=1. Всё как у настоящего провайдера, но без HTTP
до api.yookassa.ru. Переключается `YUKASSA_BACKEND=fake`; параметр
`YUKASSA_FAKE_OUTCOME` управляет итогом: success / canceled / http_error.
"""

# START_MODULE_CONTRACT
#   PURPOSE: Drop-in fake YuKassa client for dev/CI and a Celery callback
#            that posts a canonical webhook to the real /webhooks/yukassa
#            endpoint, so the entire payment chain (create -> webhook ->
#            §6.2 transitions) is exercised end-to-end without hitting
#            api.yookassa.ru. Honors YUKASSA_FAKE_OUTCOME (success |
#            canceled | http_error) so tests can drive each branch
#            deterministically. INV-001 (payment is modelled, not skipped).
#   SCOPE:   FakeYukassaClient class + yukassa_fake_callback Celery task.
#            Imported by main.py for autodiscover registration.
#   DEPENDS: httpx, Celery (payment_worker.main.celery_app), stdlib uuid/os
#   LINKS:   docs/development-plan.xml M-PAYMENT-WORKER, PDD §6.2, §8.1,
#            INV-001 (payment is modelled, not skipped)
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   FakeYukassaClient      - drop-in YukassaClient stand-in (no network)
#   yukassa_fake_callback  - Celery task that POSTs the simulated webhook
#                            to the local payment-webhook service
#   logger                 - module logger
# END_MODULE_MAP

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

import httpx

from payment_worker.main import celery_app

logger = logging.getLogger(__name__)

_WEBHOOK_URL = "http://payment-webhook:8241/webhooks/yukassa"


# START_CONTRACT: FakeYukassaClient
#   PURPOSE: Network-free YukassaClient stand-in for dev / CI. Returns
#            deterministic payment ids and schedules a delayed webhook
#            callback that drives PDD §6.2 transitions through the real
#            webhook handler.
#   INPUTS:  none (constructor takes no args).
#   OUTPUTS: FakeYukassaClient instance.
#   SIDE_EFFECTS: none on construction; methods schedule Celery callbacks
#                 (see per-method contracts).
#   LINKS:   PDD §6.2, §8.1, INV-001
# END_CONTRACT: FakeYukassaClient
class FakeYukassaClient:
    """Drop-in замена YukassaClient без сетевых вызовов."""

    # START_CONTRACT: FakeYukassaClient.create_payment
    #   PURPOSE: Mirror YukassaClient.create_payment signature/return shape
    #            without HTTP. Schedules a delayed yukassa_fake_callback
    #            (countdown=1s) that POSTs a canonical webhook so the real
    #            webhook handler runs the §6.2 transition. Honors
    #            YUKASSA_FAKE_OUTCOME: "success" -> payment.succeeded,
    #            "canceled" -> payment.canceled, "http_error" -> raise
    #            httpx.RequestError (drives Celery retry + INV-004
    #            compensation in the caller).
    #   INPUTS:  amount_kopecks: int
    #            idempotency_key: str
    #            return_url: str
    #            description: str
    #   OUTPUTS: dict[str, Any] — {"payment_id", "confirmation_url", "status"}
    #   SIDE_EFFECTS: dispatches a Celery task (yukassa_fake_callback) onto
    #                 the broker; may raise httpx.RequestError for the
    #                 http_error branch.
    #   LINKS:   PDD §6.2 (PENDING -> AWAITING_CONFIRMATION),
    #            INV-016 (explicit transitions), INV-001
    # END_CONTRACT: FakeYukassaClient.create_payment
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

    # START_CONTRACT: FakeYukassaClient.get_payment
    #   PURPOSE: Minimal stand-in for YukassaClient.get_payment — returns
    #            just the id and a fixed "pending" status (sufficient for
    #            the timeout-fallback callsite).
    #   INPUTS:  payment_id: str
    #   OUTPUTS: dict[str, Any] — {"id": <payment_id>, "status": "pending"}
    #   SIDE_EFFECTS: none
    #   LINKS:   PDD §6.1 (timeout fallback)
    # END_CONTRACT: FakeYukassaClient.get_payment
    def get_payment(self, payment_id: str) -> dict[str, Any]:
        # Минимум, который нужен вызывающему коду — статус и id.
        return {"id": payment_id, "status": "pending"}

    # START_CONTRACT: FakeYukassaClient.create_refund
    #   PURPOSE: Mirror YukassaClient.create_refund without HTTP. Schedules
    #            a delayed yukassa_fake_callback that POSTs a canonical
    #            refund.succeeded webhook so the §6.2 transition
    #            (REFUND_PENDING -> REFUNDED) runs through the real handler.
    #   INPUTS:  payment_id: str — original YuKassa payment id
    #            amount_kopecks: int
    #            idempotency_key: str
    #   OUTPUTS: dict[str, Any] — refund payload mimicking YuKassa shape
    #   SIDE_EFFECTS: dispatches a Celery task (yukassa_fake_callback) onto
    #                 the broker.
    #   LINKS:   PDD §6.2 (REFUND_PENDING -> REFUNDED), INV-005, INV-016
    # END_CONTRACT: FakeYukassaClient.create_refund
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


# START_CONTRACT: yukassa_fake_callback
#   PURPOSE: Celery task that POSTs a canonical YuKassa webhook body to the
#            local payment-webhook service, simulating a real provider
#            callback. Drives the actual PDD §6.2 transitions through the
#            real webhook handler (so dev/CI flow matches production).
#            Non-retrying by design — green: callback-task non-retrying
#            contract.
#   INPUTS:  payment_id: str — YuKassa payment id (real or fake)
#            event: str — payment.succeeded | payment.canceled |
#                         refund.succeeded | refund.canceled
#            refund_id: str | None — refund id for refund.* events
#   OUTPUTS: None
#   SIDE_EFFECTS: external HTTP POST to the local webhook URL; HTTP errors
#                 are logged and swallowed (no retries).
#   LINKS:   PDD §6.2 (transitions land via the real webhook handler),
#            §7.9 (webhook chain), INV-016 (explicit transitions)
# END_CONTRACT: yukassa_fake_callback
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
