"""Pydantic v2 схемы для GET /api/v1/admin/stats (PDD §4.5, §7.1 Phase 6)."""
# START_MODULE_CONTRACT
#   PURPOSE: Response DTOs for the admin dashboard stats endpoint.
#   SCOPE:   Pydantic BaseModel subclasses for revenue/order-count/popular-items.
#   DEPENDS: pydantic v2 (no ORM imports — read-only projections).
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §4.5, §7.1 Phase 6, INV-010
#   ROLE:    TYPES
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   PopularItemOut       - row in popular_items[]: name_ru, name_en, quantity
#   AdminStatsResponse   - top-level body of GET /admin/stats
# END_MODULE_MAP

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
