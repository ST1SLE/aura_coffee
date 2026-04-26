# START_MODULE_CONTRACT
#   PURPOSE: FastAPI dependency providing a Redis client backed by a shared
#            connection pool (cart, sessions, rate-limiting, INV-012).
#   SCOPE:   get_redis generator + private connection pool.
#   DEPENDS: M-SHARED (settings), redis-py.
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §4.1, INV-012
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   get_redis - FastAPI dep yielding a redis.Redis client from shared pool
# END_MODULE_MAP

from typing import Generator

import redis

from core_api.settings import settings

_pool = redis.ConnectionPool.from_url(settings.redis_url)


# START_CONTRACT: get_redis
#   PURPOSE: Yield a redis.Redis client borrowed from the module pool, then
#            close it on teardown.
#   INPUTS:  none
#   OUTPUTS: Generator[redis.Redis, None, None]
#   SIDE_EFFECTS: acquires/releases a connection from _pool.
#   LINKS:   PDD §4.1, INV-012 (rate-limiting backed by Redis)
# END_CONTRACT: get_redis
def get_redis() -> Generator[redis.Redis, None, None]:
    """FastAPI-зависимость: синхронный Redis-клиент."""
    client = redis.Redis(connection_pool=_pool)
    try:
        yield client
    finally:
        client.close()
