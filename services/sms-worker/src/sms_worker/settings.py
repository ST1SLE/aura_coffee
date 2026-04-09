from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    redis_url: str = "redis://redis:6379/0"
    smsru_api_key: str = ""
    encryption_key: str = ""


settings = Settings()  # type: ignore[call-arg]
