import logging

import httpx

from sms_worker.settings import settings

logger = logging.getLogger(__name__)

SMSRU_SEND_URL = "https://sms.ru/sms/send"


def send_sms(phone: str, message: str) -> bool:
    """Отправка SMS через SMS.ru API. Возвращает True при успехе."""
    try:
        response = httpx.post(
            SMSRU_SEND_URL,
            data={
                "api_id": settings.smsru_api_key,
                "to": phone,
                "msg": message,
                "json": 1,
            },
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "OK":
            return True

        logger.error("SMS.ru error: %s", data)
        return False
    except Exception:
        logger.exception("SMS.ru request failed")
        return False
