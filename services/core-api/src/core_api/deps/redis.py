from typing import Generator

import redis

from core_api.settings import settings

_pool = redis.ConnectionPool.from_url(settings.redis_url)


def get_redis() -> Generator[redis.Redis, None, None]:
    """FastAPI-зависимость: синхронный Redis-клиент."""
    client = redis.Redis(connection_pool=_pool)
    try:
        yield client
    finally:
        client.close()
