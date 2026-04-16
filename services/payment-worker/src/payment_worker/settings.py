from __future__ import annotations

from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode


class Settings(BaseSettings):
    redis_url: str = "redis://redis:6379/0"
    database_url: str = "postgresql+psycopg://postgres:postgres@postgres:5432/aura"

    yukassa_shop_id: str = ""
    yukassa_secret_key: str = ""
    # NoDecode отключает JSON-парсинг: ЮKassa выдаёт CSV-строку IP в env.
    yukassa_webhook_ips: Annotated[list[str], NoDecode] = []
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


settings = Settings()  # type: ignore[call-arg]
