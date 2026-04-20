"""Маршрут дашборда админа: GET /api/v1/admin/stats.

RBAC: только {ADMIN}, прописано в rbac_matrix.ROUTE_MATRIX.
401/403 обрабатывает RBACMiddleware — здесь явных auth-deps нет.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core_api.deps.database import get_db
from core_api.schemas.admin_stats import AdminStatsResponse, PopularItemOut
from core_api.services.admin_stats import (
    compute_range,
    get_popular_items,
    get_revenue_and_count,
)

router = APIRouter(prefix="/api/v1/admin", tags=["admin", "stats"])


@router.get("/stats", response_model=AdminStatsResponse)
def get_admin_stats(
    range: Literal["today", "week", "month"] = Query("month"),
    db: Session = Depends(get_db),
) -> AdminStatsResponse:
    """Агрегированная статистика за выбранный диапазон (PDD §7.1 Phase 6 item 1)."""
    start, end = compute_range(range)
    revenue, count = get_revenue_and_count(db, start, end)
    popular = get_popular_items(db, start, end)

    return AdminStatsResponse(
        range=range,
        range_start=start,
        range_end=end,
        revenue_kopecks=revenue,
        orders_count=count,
        popular_items=[
            PopularItemOut(name_ru=p.name_ru, name_en=p.name_en, quantity=p.quantity)
            for p in popular
        ],
    )
