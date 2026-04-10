from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings

_PLACEHOLDER = "your-smsru-api-key"


class Settings(BaseSettings):
    redis_url: str = "redis://redis:6379/0"
    smsru_api_key: str = ""
    encryption_key: str = ""
    sms_backend: Literal["log", "smsru"] = "log"

    @model_validator(mode="after")
    def _validate_smsru_key(self) -> "Settings":
        if self.sms_backend == "smsru":
            if not self.smsru_api_key or self.smsru_api_key == _PLACEHOLDER:
                raise ValueError(
                    "SMSRU_API_KEY must be a real api_id when SMS_BACKEND=smsru "
                    "(INV-015: secrets must not be empty or placeholder values)"
                )
        return self


settings = Settings()  # type: ignore[call-arg]
