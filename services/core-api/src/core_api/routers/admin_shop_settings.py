"""Admin shop settings router (PDD §5.2, §6.1, §7.1 Phase 6 item 3, INV-010).

GET  /api/v1/admin/settings — snapshot singleton-строки shop_settings.
PUT  /api/v1/admin/settings — full-snapshot update. PATCH не поддерживается
(избегаем JSONB-merge на working_hours). ADMIN-only (RBACMiddleware).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core_api.deps import database as _db_dep
from core_api.schemas.shop_settings import (
    ShopSettingsResponse,
    ShopSettingsUpdate,
)
from core_api.services.admin_shop_settings import (
    ShopSettingsNotSeededError,
    get_settings,
    update_settings,
)

router = APIRouter(prefix="/api/v1/admin", tags=["admin-settings"])


def _get_session():
    yield from _db_dep.get_session()


@router.get("/settings", response_model=ShopSettingsResponse)
def get_shop_settings_endpoint(
    db: Session = Depends(_get_session),
) -> ShopSettingsResponse:
    try:
        row = get_settings(db)
    except ShopSettingsNotSeededError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    return ShopSettingsResponse.model_validate(row)


@router.put("/settings", response_model=ShopSettingsResponse)
def update_shop_settings_endpoint(
    payload: ShopSettingsUpdate,
    db: Session = Depends(_get_session),
) -> ShopSettingsResponse:
    try:
        row = update_settings(db, payload)
    except ShopSettingsNotSeededError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    db.commit()
    db.refresh(row)
    return ShopSettingsResponse.model_validate(row)
