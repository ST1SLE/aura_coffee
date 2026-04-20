"""Pydantic-схемы прокси Яндекс.Карт (PDD §7.3, §8.3).

Контракт фиксирован RED-тестами: каждая модель содержит ровно
объявленные поля (extra='forbid').
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Suggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    lat: float
    lon: float
    precision: str


class GeocodeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lat: float
    lon: float
    precision: str
    canonical_text: str
