# START_MODULE_CONTRACT
#   PURPOSE: Core API runtime settings with fail-fast secret safety rails.
#   SCOPE:   Settings class and module-level settings instance.
#   DEPENDS: pydantic, pydantic-settings
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §8.4, INV-015
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   Settings - pydantic BaseSettings carrying env-driven Core API config
#   settings - module-level Settings() instantiated at import/startup
# END_MODULE_MAP

from __future__ import annotations

import re

from pydantic import ConfigDict, model_validator
from pydantic_settings import BaseSettings


_JWT_MIN_LENGTH = 32
_ENCRYPTION_KEY_HEX_LENGTH = 64
_PLACEHOLDER_SECRETS = {
    "",
    "change-me-to-random-secret",
    "change-me",
    "changeme",
    "dev-secret",
    "test-secret",
    "secret",
    "password",
    "placeholder",
}
_PLACEHOLDER_FRAGMENTS = ("change-me", "changeme", "replace-me", "placeholder")


def _is_dev_env(value: str) -> bool:
    return value.strip().lower() == "dev"


def _looks_placeholder(value: str) -> bool:
    normalized = value.strip().lower()
    return (
        normalized in _PLACEHOLDER_SECRETS
        or any(fragment in normalized for fragment in _PLACEHOLDER_FRAGMENTS)
        or len(set(normalized)) <= 1
    )


# START_CONTRACT: Settings
#   PURPOSE: Strongly-typed env config for Core API; outside explicit
#            AURA_ENV=dev, rejects weak JWT and PII encryption secrets before
#            the app can start.
#   INPUTS:  reads env vars including AURA_ENV, DATABASE_URL, REDIS_URL,
#            JWT_SECRET_KEY, ENCRYPTION_KEY, SMSRU_API_KEY,
#            YANDEX_MAPS_API_KEY.
#   OUTPUTS: Settings instance.
#   SIDE_EFFECTS: none; raises ValidationError on unsafe non-dev secrets.
#   LINKS:   PDD §8.4, INV-015, INV-013
# END_CONTRACT: Settings
class Settings(BaseSettings):
    model_config = ConfigDict(hide_input_in_errors=True)

    aura_env: str = "production"
    database_url: str
    redis_url: str = "redis://redis:6379/0"
    cors_origins: str = "http://localhost:5173"
    core_api_host: str = "0.0.0.0"
    core_api_port: int = 8000

    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_ttl: int = 900
    refresh_token_ttl: int = 604800
    encryption_key: str = ""
    smsru_api_key: str = ""
    cart_ttl_seconds: int = 86400  # PDD §5.3: TTL корзины в Redis — 24 ч
    # PDD §8.3, §8.4, INV-015: API-ключ Яндекс.Карт. Используется Core API
    # при проксировании Suggest/Geocoder; в клиентский бандл не попадает.
    yandex_maps_api_key: str = ""

    @model_validator(mode="after")
    def _check_secret_safety(self) -> "Settings":
        """Fail fast on placeholder auth/PII secrets outside local dev."""
        if _is_dev_env(self.aura_env):
            return self

        if (
            _looks_placeholder(self.jwt_secret_key)
            or len(self.jwt_secret_key) < _JWT_MIN_LENGTH
        ):
            raise ValueError(
                "JWT_SECRET_KEY must be a non-placeholder value with at least "
                f"{_JWT_MIN_LENGTH} characters unless AURA_ENV=dev"
            )

        if (
            _looks_placeholder(self.encryption_key)
            or len(self.encryption_key) != _ENCRYPTION_KEY_HEX_LENGTH
            or re.fullmatch(r"[0-9a-fA-F]{64}", self.encryption_key) is None
        ):
            raise ValueError(
                "ENCRYPTION_KEY must be a non-placeholder 32-byte hex value "
                "unless AURA_ENV=dev"
            )
        return self

    # START_CONTRACT: Settings.cors_origin_list
    #   PURPOSE: Parse comma-separated CORS_ORIGINS for Starlette CORS config.
    #   INPUTS:  self.cors_origins: str
    #   OUTPUTS: list[str]
    #   SIDE_EFFECTS: none
    #   LINKS:   PDD §4.1
    # END_CONTRACT: Settings.cors_origin_list
    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


settings = Settings()  # type: ignore[call-arg]
