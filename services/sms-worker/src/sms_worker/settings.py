# START_MODULE_CONTRACT
#   PURPOSE: Centralised, env-driven configuration for the SMS worker —
#            broker/database URLs, SMS backend selector, and SMS.ru credentials.
#   SCOPE:   Defines the Settings model (pydantic_settings) and exposes a
#            singleton `settings` instance. Fail-fast validator enforces
#            INV-015 (no empty/placeholder secrets when SMS_BACKEND=smsru).
#   DEPENDS: pydantic, pydantic_settings
#   LINKS:   docs/development-plan.xml M-SMS-WORKER, PDD §8.2, INV-015
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   Settings - pydantic settings model loaded from environment variables
#   settings - module-level Settings() singleton consumed by main/clients/tasks
# END_MODULE_MAP

from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings

_PLACEHOLDER = "your-smsru-api-key"


# START_CONTRACT: Settings
#   PURPOSE: Typed container for runtime configuration loaded from env vars.
#            Selects between dev `log` transport and production `smsru` transport,
#            and refuses to boot if SMS.ru credentials look fake (INV-015).
#   INPUTS:  Environment variables (REDIS_URL, DATABASE_URL, SMSRU_API_KEY,
#            ENCRYPTION_KEY, SMS_BACKEND).
#   OUTPUTS: Settings instance with validated fields.
#   SIDE_EFFECTS: Reads process environment on instantiation; raises ValueError
#            on invalid SMS.ru credentials (fail-fast at startup).
#   LINKS:   PDD §8.2, INV-015 (secrets in env, never code)
# END_CONTRACT: Settings
class Settings(BaseSettings):
    redis_url: str = "redis://redis:6379/0"
    database_url: str = "postgresql://aura:aura_secret@postgres:5432/aura_coffee"
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
