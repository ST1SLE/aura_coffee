"""Прокси Яндекс.Карт: GET /api/v1/maps/suggest + /geocode (PDD §7.3, §8.3).

Роутер владеет кэшированием (только для geocode) и дневным rate-limit
счётчиком. Сервис отвечает за HTTP к Яндексу и классификацию ошибок.
"""

from __future__ import annotations

# START_MODULE_CONTRACT
#   PURPOSE: Yandex Maps proxy under /api/v1/maps — Suggest (no cache)
#            + Geocoder (cached, low-precision filter). Owns Redis cache,
#            daily rate counter and 80% quota-warn.
#   SCOPE:   Two read-only endpoints. The router owns caching + rate
#            counters; HTTP to Yandex and error classification live in
#            services.yandex_maps. NOTE: this is the one endpoint allowed
#            to make a synchronous external call (AGENTS.md, ≤500ms SLA).
#   DEPENDS: Redis (cache + rate-counter), httpx (transitive),
#            core_api.services.yandex_maps,
#            core_api.deps.redis.
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §7.3 address,
#            §8.3 third-party SLA. INV-002 does not apply (public proxy
#            for the customer SPA address picker).
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   router      - APIRouter("/api/v1/maps", tags=["maps"])
#   suggest     - GET /api/v1/maps/suggest
#   geocode     - GET /api/v1/maps/geocode
# END_MODULE_MAP

import hashlib
import logging
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse

from core_api.deps import redis as _redis_dep
from core_api.schemas.yandex_maps import GeocodeResult, Suggestion
from core_api.services.yandex_maps import (
    MapsUnavailableError,
    YandexMapsClient,
    is_low_precision,
)

router = APIRouter(prefix="/api/v1/maps", tags=["maps"])
logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 604800  # 7 дней
RATE_LIMIT_TTL_SECONDS = 172800  # 48 часов
DAILY_QUOTA_WARN_THRESHOLD = 800  # 80% от 1000/день


def _get_redis():
    """Обёртка: обращение к атрибуту модуля разрешается в момент вызова,
    чтобы тесты могли патчить core_api.deps.redis.get_redis."""
    yield from _redis_dep.get_redis()


_CLIENT: YandexMapsClient | None = None


def _get_client() -> YandexMapsClient:
    """Ленивая инициализация модуль-уровневого httpx-клиента."""
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = YandexMapsClient(timeout=3.0)
    return _CLIENT


def _cache_key(text: str) -> str:
    normalized = text.strip().casefold()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"yandex:geocode:{digest}"


def _bump_daily_rate(redis_client) -> None:
    """Инкрементит дневной счётчик и эмитит один WARNING при 80%."""
    date = datetime.now(UTC).strftime("%Y-%m-%d")
    key = f"yandex:rate:{date}"
    count = redis_client.incr(key)
    if count == 1:
        # Первая запись за день — устанавливаем TTL.
        redis_client.expire(key, RATE_LIMIT_TTL_SECONDS)

    if count >= DAILY_QUOTA_WARN_THRESHOLD:
        warned_key = f"{key}:warned"
        # SET NX гарантирует, что WARNING эмитится ровно один раз за сутки.
        if redis_client.set(warned_key, "1", nx=True, ex=RATE_LIMIT_TTL_SECONDS):
            logger.warning(
                "yandex daily quota crossed 80%% (%d/1000 on %s)", count, date
            )


_MAPS_UNAVAILABLE = {"reason": "maps_unavailable"}
_LOW_PRECISION = {"reason": "low_precision"}


# START_CONTRACT: suggest
#   PURPOSE: Proxy Yandex Suggest — autocomplete query, no caching.
#   INPUTS:  text: str (query, min_length=1), lang: str (default ru_RU),
#            Redis client.
#   OUTPUTS: 200 list[Suggestion]; 503 {"reason": "maps_unavailable"};
#            500 yandex_upstream_error on 4xx upstream.
#   SIDE_EFFECTS: Redis INCR of daily rate counter; one-shot WARNING log
#                 when ≥80% of daily quota is reached.
#   LINKS:   PDD §7.3, §8.3, services.yandex_maps.
# END_CONTRACT: suggest
@router.get("/suggest", response_model=None)
def suggest(
    text: str = Query(..., min_length=1),
    lang: str = Query("ru_RU"),
    redis_client=Depends(_get_redis),
) -> list[Suggestion] | Response:
    """Прокси Yandex Suggest — без кэша (PDD §8.3)."""
    client = _get_client()
    try:
        results = client.suggest(text, lang)
    except MapsUnavailableError:
        return JSONResponse(status_code=503, content=_MAPS_UNAVAILABLE)
    except httpx.HTTPStatusError as exc:
        # 4xx — программная ошибка (плохой ключ); не 503, а 500.
        raise HTTPException(status_code=500, detail="yandex_upstream_error") from exc

    _bump_daily_rate(redis_client)
    return results


# START_CONTRACT: geocode
#   PURPOSE: Proxy Yandex Geocoder with 7-day Redis cache and a
#            precision≥street filter (low_precision rejected).
#   INPUTS:  text: str (query, min_length=1), Redis client.
#   OUTPUTS: 200 GeocodeResult JSON; 422 {"reason": "low_precision"};
#            503 {"reason": "maps_unavailable"}; 500 yandex_upstream_error.
#   SIDE_EFFECTS: Redis read on cache hit; on miss — Redis SETEX of
#                 serialized result and INCR of daily rate counter
#                 (with 80% one-shot WARNING).
#   LINKS:   PDD §7.3, §8.3, services.yandex_maps.
# END_CONTRACT: geocode
@router.get("/geocode", response_model=None)
def geocode(
    text: str = Query(..., min_length=1),
    redis_client=Depends(_get_redis),
) -> Response:
    """Прокси Yandex Geocoder — с кэшем (TTL 7 дней) и фильтром precision≥street."""
    key = _cache_key(text)
    cached = redis_client.get(key)
    if cached is not None:
        payload = cached.decode("utf-8") if isinstance(cached, (bytes, bytearray)) else cached
        return Response(content=payload, media_type="application/json")

    client = _get_client()
    try:
        result: GeocodeResult | None = client.geocode(text)
    except MapsUnavailableError:
        return JSONResponse(status_code=503, content=_MAPS_UNAVAILABLE)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=500, detail="yandex_upstream_error") from exc

    if result is None or is_low_precision(result.precision):
        return JSONResponse(status_code=422, content=_LOW_PRECISION)

    serialized = result.model_dump_json()
    redis_client.setex(key, CACHE_TTL_SECONDS, serialized)
    _bump_daily_rate(redis_client)
    return Response(content=serialized, media_type="application/json")
