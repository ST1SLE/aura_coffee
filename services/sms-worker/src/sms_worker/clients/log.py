import logging

logger = logging.getLogger(__name__)


def send_via_log(phone: str, message: str) -> bool:
    """Dev-транспорт: выводит SMS в лог вместо реальной отправки."""
    logger.info("[SMS:log] to=%s msg=%s", phone, message)
    return True
