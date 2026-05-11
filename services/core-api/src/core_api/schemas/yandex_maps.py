"""Pydantic-схемы прокси Яндекс.Карт (PDD §7.3, §8.3).

Контракт фиксирован RED-тестами: каждая модель содержит ровно
объявленные поля (extra='forbid').
"""
# START_MODULE_CONTRACT
#   PURPOSE: DTOs for the Yandex.Maps proxy endpoints (suggest + geocode).
#            Request bodies keep address PII out of URLs; extra='forbid'
#            enforces strict shape contract.
#   SCOPE:   SuggestRequest, GeocodeRequest, Suggestion, GeocodeResult models.
#   DEPENDS: pydantic v2.
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §7.3, §8.3
#   ROLE:    TYPES
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   SuggestRequest - POST /maps/suggest request body
#   GeocodeRequest - POST /maps/geocode request body
#   Suggestion     - one entry of /maps/suggest response array
#   GeocodeResult  - /maps/geocode response body
# END_MODULE_MAP

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SuggestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    lang: str = "ru_RU"


class GeocodeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    lang: str = "ru_RU"


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
