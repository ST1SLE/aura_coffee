# START_MODULE_CONTRACT
#   PURPOSE: Pydantic settings model for payment-worker — Redis/DB URLs,
#            YuKassa backend selector (live | fake), credentials, base URL,
#            webhook IP whitelist, and optional webhook signature verification.
#            Carries a live-mode safety-rail that refuses empty creds or
#            sandbox/test URLs in production.
#   SCOPE:   Settings class + lazy module-level `settings` accessor. Used by
#            main.py at worker boot and by webhook.py at request time. NOT
#            imported by tasks.py / db.py / redis_client.py to avoid firing
#            the safety-rail during test imports.
#   DEPENDS: pydantic, pydantic-settings
#   LINKS:   docs/development-plan.xml M-PAYMENT-WORKER, PDD §8.1 (YuKassa
#            compliance), INV-015 (no secrets in code; live mode requires
#            non-empty real creds against a non-sandbox endpoint)
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   Settings - pydantic BaseSettings carrying env-driven worker config
#   settings - lazily instantiated module-level Settings() (via __getattr__)
# END_MODULE_MAP

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode


# START_CONTRACT: Settings
#   PURPOSE: Strongly-typed env config; on instantiation in live mode it
#            verifies INV-015 (creds non-empty, base_url not pointing at
#            test/sandbox/localhost).
#   INPUTS:  reads env vars (REDIS_URL, DATABASE_URL, YUKASSA_BACKEND,
#            YUKASSA_FAKE_OUTCOME, YUKASSA_SHOP_ID, YUKASSA_SECRET_KEY,
#            YUKASSA_WEBHOOK_IPS, YUKASSA_WEBHOOK_SIGNATURE_SECRET,
#            YUKASSA_WEBHOOK_SIGNATURE_HEADER, YUKASSA_BASE_URL).
#   OUTPUTS: Settings instance.
#   SIDE_EFFECTS: none (no I/O); raises ValidationError when live-mode safety
#                 rail fails.
#   LINKS:   PDD §8.1, INV-015
# END_CONTRACT: Settings
class Settings(BaseSettings):
    redis_url: str = "redis://redis:6379/0"
    database_url: str = "postgresql+psycopg://postgres:postgres@postgres:5432/aura"

    yukassa_backend: Literal["live", "fake"] = "live"
    yukassa_fake_outcome: Literal["success", "canceled", "http_error"] = "success"
    yukassa_shop_id: str = ""
    yukassa_secret_key: str = ""
    # NoDecode отключает JSON-парсинг: ЮKassa выдаёт CSV-строку IP в env.
    yukassa_webhook_ips: Annotated[list[str], NoDecode] = []
    yukassa_webhook_signature_secret: str = ""
    yukassa_webhook_signature_header: str = "X-YooKassa-Signature"
    yukassa_base_url: str = "https://api.yookassa.ru/v3"

    @field_validator("yukassa_webhook_ips", mode="before")
    @classmethod
    def _split_ips(cls, v: object) -> list[str]:
        # Запятая-разделённая строка из env -> список (пробелы тримятся).
        if isinstance(v, str):
            return [part.strip() for part in v.split(",") if part.strip()]
        if isinstance(v, (list, tuple)):
            return [str(x).strip() for x in v if str(x).strip()]
        return []

    @model_validator(mode="after")
    def _check_live_mode_safety(self) -> "Settings":
        """INV-015: live-режим запрещает пустые creds и непроизводственные base_url.

        Зеркалит SMSRU-safety-rail в sms-worker. В fake-режиме проверка
        отключена — пустые creds безопасны, клиент их не использует.
        """
        if self.yukassa_backend != "live":
            return self
        if not self.yukassa_shop_id or not self.yukassa_secret_key:
            raise ValueError(
                "YUKASSA_SHOP_ID/YUKASSA_SECRET_KEY must be non-empty when "
                "YUKASSA_BACKEND=live (INV-015: secrets must not be empty)"
            )
        low = self.yukassa_base_url.lower()
        for marker in ("test", "sandbox", "localhost", "127.0.0.1"):
            if marker in low:
                raise ValueError(
                    f"YUKASSA_BASE_URL contains '{marker}' — refusing live mode "
                    "against non-production endpoint"
                )
        return self


def __getattr__(name: str):
    # Ленивая инициализация singleton: тесты reload-ят модуль с невалидным env
    # и ожидают ValidationError только при явном вызове Settings(), не при import.
    # Кэш не держим — reload не чистит module.__dict__, поэтому кэш между тестами
    # не пересобирался бы под новый env.
    if name == "settings":
        return Settings()  # type: ignore[call-arg]
    raise AttributeError(name)
