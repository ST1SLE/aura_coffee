"""Pydantic-схемы прокси Яндекс.Карт (PDD §7.3, §8.3).

Контракт фиксирован RED-тестами: каждая модель содержит ровно
объявленные поля (extra='forbid').
"""
# START_MODULE_CONTRACT
#   PURPOSE: DTOs for the Yandex.Maps proxy endpoints (suggest + geocode).
#            extra='forbid' enforces strict shape contract.
#   SCOPE:   Suggestion, GeocodeResult Pydantic models.
#   DEPENDS: pydantic v2.
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §7.3, §8.3
#   ROLE:    TYPES
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   Suggestion     - one entry of GET /maps/suggest response array
#   GeocodeResult  - GET /maps/geocode response body
# END_MODULE_MAP

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Suggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    lat: float | None = None
    lon: float | None = None
    precision: str = "suggest"


class GeocodeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lat: float
    lon: float
    precision: str
    canonical_text: str
