"""Ленивый Redis-клиент.

Отделён от webhook/tasks, чтобы тесты могли подменять
``payment_worker.webhook.get_redis``.
"""

from __future__ import annotations

import redis

from payment_worker.settings import settings

_redis: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.Redis.from_url(settings.redis_url, decode_responses=False)
    return _redis
