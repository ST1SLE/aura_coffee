"""Admin shop settings router (PDD §5.2, §6.1, §7.1 Phase 6 item 3, INV-010).

GET  /api/v1/admin/settings — snapshot singleton-строки shop_settings.
PUT  /api/v1/admin/settings — full-snapshot update. PATCH не поддерживается
(избегаем JSONB-merge на working_hours). ADMIN-only (RBACMiddleware).
"""

from __future__ import annotations

# START_MODULE_CONTRACT
#   PURPOSE: HTTP routes for the singleton shop_settings row under
#            /api/v1/admin/settings — full-snapshot GET + PUT.
#   SCOPE:   Read and replace shop settings (working_hours, delivery
#            radius, etc.). PATCH is intentionally unsupported to avoid
#            JSONB-merge ambiguity on working_hours.
#   DEPENDS: M-DATABASE (Session), core_api.services.admin_shop_settings,
#            RBACMiddleware (ADMIN-only).
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §5.2, §6.1, §7.1
#            Phase 6 item 3, INV-002, INV-010.
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   router                          - APIRouter("/api/v1/admin", tags=["admin-settings"])
#   get_shop_settings_endpoint      - GET /api/v1/admin/settings
#   update_shop_settings_endpoint   - PUT /api/v1/admin/settings
# END_MODULE_MAP

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


# START_CONTRACT: get_shop_settings_endpoint
#   PURPOSE: Return the singleton shop_settings snapshot.
#   INPUTS:  Session.
#   OUTPUTS: 200 ShopSettingsResponse; 500 if seed row missing.
#   SIDE_EFFECTS: none.
#   LINKS:   PDD §5.2, INV-002, INV-010, services.admin_shop_settings.
# END_CONTRACT: get_shop_settings_endpoint
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


# START_CONTRACT: update_shop_settings_endpoint
#   PURPOSE: Replace the singleton shop_settings row with a full snapshot.
#   INPUTS:  payload: ShopSettingsUpdate, Session.
#   OUTPUTS: 200 ShopSettingsResponse; 500 if seed row missing.
#   SIDE_EFFECTS: DB update + commit + refresh of shop_settings.
#   LINKS:   PDD §5.2, §6.1, §7.1 Phase 6 item 3, INV-002, INV-010,
#            services.admin_shop_settings.
# END_CONTRACT: update_shop_settings_endpoint
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
