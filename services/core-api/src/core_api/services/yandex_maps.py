# START_MODULE_CONTRACT
#   PURPOSE: Synchronous Yandex.Maps Suggest + Geocoder client — Core API's
#            allowed external sync call (≤ 500 ms latency target). Owns
#            httpx.Client with 3s timeout, response normalization, error
#            classification (timeout/5xx → MapsUnavailableError).
#   SCOPE:   suggest, geocode, low-precision check; cache & rate-limit live in router.
#   DEPENDS: httpx, schemas.yandex_maps, settings
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §7.3, §8.3, INV-015
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   MapsUnavailableError - timeout/connect/5xx normalised to single error class
#   is_low_precision     - precision below "street" threshold check
#   YandexMapsClient     - sync client wrapping suggest + geocode endpoints
# END_MODULE_MAP
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


# START_CONTRACT: MapsUnavailableError
#   PURPOSE: Single exception type for retryable upstream Yandex failures —
#            timeouts, connect errors, 5xx. 4xx is treated as a client error
#            and bubbles via httpx.HTTPStatusError.
#   INPUTS:  message: str
#   OUTPUTS: RuntimeError instance.
#   SIDE_EFFECTS: none
# END_CONTRACT: MapsUnavailableError
class MapsUnavailableError(RuntimeError):
    """Яндекс недоступен: timeout, connect error или 5xx."""


# START_CONTRACT: is_low_precision
#   PURPOSE: True when the supplied geocoder precision is below the "street"
#            threshold (PDD §7.3 step 2). Unknown values count as low.
#   INPUTS:  precision: str
#   OUTPUTS: bool
#   SIDE_EFFECTS: none
#   LINKS:   PDD §7.3, INV-015
# END_CONTRACT: is_low_precision
def is_low_precision(precision: str) -> bool:
    """True, если точность ниже 'street' (PDD §7.3 шаг 2)."""
    try:
        return PRECISION_ORDER.index(precision) < MIN_PRECISION_INDEX
    except ValueError:
        # Неизвестное значение точности — считаем ниже порога.
        return True


# START_CONTRACT: YandexMapsClient
#   PURPOSE: Synchronous httpx-backed client for Suggest + Geocoder endpoints.
#   INPUTS:  api_key: str = ""
#            suggest_api_key: str = "" — optional Suggest-specific fallback
#            geocoder_api_key: str = "" — optional Geocoder-specific fallback
#            timeout: float = 3.0 — httpx timeout in seconds
#   OUTPUTS: YandexMapsClient instance.
#   SIDE_EFFECTS: opens an httpx.Client on construction.
#   LINKS:   PDD §7.3, §8.3, INV-015
# END_CONTRACT: YandexMapsClient
class YandexMapsClient:
    """Синхронный прокси к Suggest и Geocoder Yandex.Maps."""

    def __init__(
        self,
        api_key: str = "",
        suggest_api_key: str = "",
        geocoder_api_key: str = "",
        timeout: float = 3.0,
    ) -> None:
        # Ключи из __init__ хранятся только как fallback — при каждом вызове
        # читаем settings, чтобы тесты и env-перезагрузка могли подменять ключи
        # без пересоздания клиента.
        self._api_key = api_key
        self._suggest_api_key = suggest_api_key
        self._geocoder_api_key = geocoder_api_key
        self._timeout = httpx.Timeout(timeout)
        self._client = httpx.Client(timeout=self._timeout)

    # START_CONTRACT: YandexMapsClient.timeout
    #   PURPOSE: Expose the configured httpx Timeout for diagnostics/tests.
    #   INPUTS:  none
    #   OUTPUTS: httpx.Timeout
    #   SIDE_EFFECTS: none
    # END_CONTRACT: YandexMapsClient.timeout
    @property
    def timeout(self) -> httpx.Timeout:
        return self._timeout

    def _current_suggest_api_key(self) -> str:
        # Специфичный ключ имеет приоритет; общий ключ — обратная совместимость.
        return (
            settings.yandex_maps_suggest_api_key
            or settings.yandex_maps_api_key
            or self._suggest_api_key
            or self._api_key
        )

    def _current_geocoder_api_key(self) -> str:
        # Специфичный ключ имеет приоритет; общий ключ — обратная совместимость.
        return (
            settings.yandex_maps_geocoder_api_key
            or settings.yandex_maps_api_key
            or self._geocoder_api_key
            or self._api_key
        )

    # START_CONTRACT: YandexMapsClient.suggest
    #   PURPOSE: Call Yandex Suggest endpoint and normalise into a list of
    #            Suggestion DTOs, dropping entries without coordinates.
    #   INPUTS:  text: str, lang: str
    #   OUTPUTS: list[Suggestion]
    #   SIDE_EFFECTS: outbound HTTP GET to suggest-maps.yandex.ru with API key.
    #                 Timeout / connect / 5xx → MapsUnavailableError; 4xx →
    #                 httpx.HTTPStatusError bubbles up.
    #   LINKS:   PDD §7.3, INV-015
    # END_CONTRACT: YandexMapsClient.suggest
    def suggest(self, text: str, lang: str) -> list[Suggestion]:
        params = {
            "text": text,
            "lang": lang,
            "apikey": self._current_suggest_api_key(),
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

    # START_CONTRACT: YandexMapsClient.geocode
    #   PURPOSE: Call Yandex Geocoder, parse first feature, return canonical
    #            text + lat/lon + precision; None when no feature returned.
    #   INPUTS:  text: str — free-form address
    #   OUTPUTS: GeocodeResult | None
    #   SIDE_EFFECTS: outbound HTTP GET to geocode-maps.yandex.ru. Timeout /
    #                 connect / 5xx → MapsUnavailableError.
    #   LINKS:   PDD §7.3, §8.3, INV-015
    # END_CONTRACT: YandexMapsClient.geocode
    def geocode(self, text: str) -> GeocodeResult | None:
        params = {
            "geocode": text,
            "apikey": self._current_geocoder_api_key(),
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
