"""Ленивый Redis-клиент.

Отделён от webhook/tasks, чтобы тесты могли подменять
``payment_worker.webhook.get_redis``.
"""

# START_MODULE_CONTRACT
#   PURPOSE: Lazy Redis client factory used by the webhook handler for
#            event-id idempotency keys and for clearing the post-purchase cart;
#            isolated so tests can patch `payment_worker.webhook.get_redis`
#            without dragging in Settings-validation.
#   SCOPE:   Process-singleton redis.Redis instance.
#   DEPENDS: redis-py, stdlib os
#   LINKS:   docs/development-plan.xml M-PAYMENT-WORKER, PDD §7.9 (webhook chain)
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   get_redis - lazy redis.Redis factory (singleton per-process)
# END_MODULE_MAP

from __future__ import annotations

import os

import redis

_redis: redis.Redis | None = None


# START_CONTRACT: get_redis
#   PURPOSE: Lazily build the per-process redis.Redis client; reads REDIS_URL
#            from env on first call so tests/imports don't require Settings.
#   INPUTS:  none
#   OUTPUTS: redis.Redis — process-singleton client (decode_responses=False)
#   SIDE_EFFECTS: caches the client in a module-level global; opens a TCP
#                 connection on first use against REDIS_URL.
#   LINKS:   PDD §7.9 (idempotent webhook processing via Redis event keys)
# END_CONTRACT: get_redis
def get_redis() -> redis.Redis:
    """Ленивая инициализация: REDIS_URL читаем из env при первом вызове.

    Не импортируем Settings на module-level: её safety-rail может фалить в
    тестах, где creds ещё не выставлены.
    """
    global _redis
    if _redis is None:
        redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        _redis = redis.Redis.from_url(redis_url, decode_responses=False)
    return _redis
