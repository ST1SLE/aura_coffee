"""Синхронный клиент Яндекс.Карт для Core API (PDD §7.3, §8.3, INV-015).

Владеет httpx.Client (timeout 3.0s), нормализацией Suggest/Geocoder и
классификацией ошибок. Не трогает Redis — кэш и rate-limit живут в роутере.
"""

from __future__ import annotations

import httpx

from core_api.schemas.yandex_maps import GeocodeResult, Suggestion
from core_api.settings import settings

# Порядок точности Yandex (от худшей к лучшей). Порог для приёма — "street".
PRECISION_ORDER: tuple[str, ...] = (
    "other",
    "near",
    "range",
    "street",
    "number",
    "exact",
)
MIN_PRECISION_INDEX = PRECISION_ORDER.index("street")

SUGGEST_URL = "https://suggest-maps.yandex.ru/v1/suggest"
GEOCODER_URL = "https://geocode-maps.yandex.ru/1.x/"


class MapsUnavailableError(RuntimeError):
    """Яндекс недоступен: timeout, connect error или 5xx."""


def is_low_precision(precision: str) -> bool:
    """True, если точность ниже 'street' (PDD §7.3 шаг 2)."""
    try:
        return PRECISION_ORDER.index(precision) < MIN_PRECISION_INDEX
    except ValueError:
        # Неизвестное значение точности — считаем ниже порога.
        return True


class YandexMapsClient:
    """Синхронный прокси к Suggest и Geocoder Yandex.Maps."""

    def __init__(self, api_key: str = "", timeout: float = 3.0) -> None:
        # api_key хранится только как стартовое значение — при каждом
        # вызове читаем settings.yandex_maps_api_key, чтобы тесты могли
        # монки-патчить ключ на лету.
        self._api_key = api_key
        self._timeout = httpx.Timeout(timeout)
        self._client = httpx.Client(timeout=self._timeout)

    @property
    def timeout(self) -> httpx.Timeout:
        return self._timeout

    def _current_api_key(self) -> str:
        # settings — источник истины; ключ из __init__ оставлен как fallback.
        return settings.yandex_maps_api_key or self._api_key

    def suggest(self, text: str, lang: str) -> list[Suggestion]:
        params = {
            "text": text,
            "lang": lang,
            "apikey": self._current_api_key(),
            "print_address": 1,
        }
        try:
            resp = self._client.get(SUGGEST_URL, params=params)
        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as exc:
            raise MapsUnavailableError(str(exc)) from exc

        if 500 <= resp.status_code < 600:
            raise MapsUnavailableError(f"Yandex 5xx: {resp.status_code}")
        resp.raise_for_status()  # 4xx → HTTPStatusError → bubble как 500

        payload = resp.json()
        results = payload.get("results") or []
        suggestions: list[Suggestion] = []
        for item in results:
            text_val = (item.get("title") or {}).get("text") or item.get("text") or ""
            lat = item.get("lat")
            lon = item.get("lon")
            precision = item.get("precision", "other")
            if lat is None or lon is None:
                # Skip partial matches without coordinates.
                continue
            suggestions.append(
                Suggestion(text=text_val, lat=float(lat), lon=float(lon), precision=precision)
            )
        return suggestions

    def geocode(self, text: str) -> GeocodeResult | None:
        params = {
            "geocode": text,
            "apikey": self._current_api_key(),
            "format": "json",
            "results": 1,
        }
        try:
            resp = self._client.get(GEOCODER_URL, params=params)
        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as exc:
            raise MapsUnavailableError(str(exc)) from exc

        if 500 <= resp.status_code < 600:
            raise MapsUnavailableError(f"Yandex 5xx: {resp.status_code}")
        resp.raise_for_status()  # 4xx → HTTPStatusError → bubble как 500

        payload = resp.json()
        feature_members = (
            payload.get("response", {})
            .get("GeoObjectCollection", {})
            .get("featureMember", [])
        )
        if not feature_members:
            return None

        geo_object = feature_members[0].get("GeoObject", {})
        meta = (
            geo_object.get("metaDataProperty", {})
            .get("GeocoderMetaData", {})
        )
        precision = meta.get("precision", "other")
        canonical_text = meta.get("text", "")

        pos = geo_object.get("Point", {}).get("pos", "")
        parts = pos.split()
        if len(parts) != 2:
            return None
        lon, lat = float(parts[0]), float(parts[1])

        return GeocodeResult(
            lat=lat,
            lon=lon,
            precision=precision,
            canonical_text=canonical_text,
        )
