"""Маршрут дашборда админа: GET /api/v1/admin/stats.

RBAC: только {ADMIN}, прописано в rbac_matrix.ROUTE_MATRIX.
401/403 обрабатывает RBACMiddleware — здесь явных auth-deps нет.
"""
from __future__ import annotations

# START_MODULE_CONTRACT
#   PURPOSE: HTTP route for the admin dashboard aggregate under
#            /api/v1/admin/stats (revenue, order count, popular items).
#   SCOPE:   Read-only aggregation over orders/order_items for a chosen
#            range (today / week / month). ADMIN-only via RBACMiddleware.
#   DEPENDS: M-DATABASE (Session), core_api.services.admin_stats,
#            core_api.deps.database.
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §7.1 Phase 6 item 1,
#            INV-002, INV-010.
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   router            - APIRouter("/api/v1/admin", tags=["admin", "stats"])
#   get_admin_stats   - GET /api/v1/admin/stats
# END_MODULE_MAP

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


# START_CONTRACT: get_admin_stats
#   PURPOSE: Return aggregated admin dashboard stats for a chosen range
#            (today/week/month): revenue (kopecks), order count, popular items.
#   INPUTS:  range: Literal["today","week","month"] (query, default "month"),
#            Session.
#   OUTPUTS: 200 AdminStatsResponse.
#   SIDE_EFFECTS: none (read-only DB queries).
#   LINKS:   PDD §7.1 Phase 6 item 1, INV-002, INV-010, services.admin_stats.
# END_CONTRACT: get_admin_stats
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
