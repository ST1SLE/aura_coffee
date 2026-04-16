"""Ленивый Redis-клиент.

Отделён от webhook/tasks, чтобы тесты могли подменять
``payment_worker.webhook.get_redis``.
"""

from __future__ import annotations

import os

import redis

_redis: redis.Redis | None = None


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
