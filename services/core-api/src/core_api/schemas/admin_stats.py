"""Pydantic v2 схемы для GET /api/v1/admin/stats (PDD §4.5, §7.1 Phase 6)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class PopularItemOut(BaseModel):
    """Одна строка в popular_items[]: снимок (name_ru, name_en) + суммарное quantity."""

    model_config = ConfigDict(from_attributes=True)

    name_ru: str
    name_en: str
    quantity: int


class AdminStatsResponse(BaseModel):
    """Ответ эндпойнта /admin/stats — агрегаты выручки, кол-ва и топ-популярных позиций."""

    model_config = ConfigDict(from_attributes=True)

    range: Literal["today", "week", "month"]
    range_start: datetime
    range_end: datetime
    revenue_kopecks: int
    orders_count: int
    popular_items: list[PopularItemOut]
