"""Customer notification feed routes (PDD §5.2, INV-013)."""
from __future__ import annotations

# START_MODULE_CONTRACT
#   PURPOSE: HTTP route for the customer's own in-app notification feed under
#            /api/v1/profile/notifications.
#   SCOPE:   Read-only pagination over current user's notifications. CUSTOMER
#            only via rbac_matrix.ROUTE_MATRIX; no notification creation or
#            read-state mutation lives here.
#   DEPENDS: M-DATABASE (Session), core_api.deps.{auth,database},
#            core_api.services.notification_feed.
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §5.2, INV-002, INV-013.
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   router                     - APIRouter("/api/v1/profile", tags=["notifications"])
#   get_my_notifications       - GET /api/v1/profile/notifications
# END_MODULE_MAP

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core_api.deps import database as _db_dep
from core_api.deps.auth import get_current_user
from core_api.schemas.notification_feed import NotificationFeedResponse
from core_api.services.notification_feed import list_notifications_for_user

router = APIRouter(prefix="/api/v1/profile", tags=["notifications"])


def _get_session():
    yield from _db_dep.get_session()


# START_CONTRACT: get_my_notifications
#   PURPOSE: Paginated in-app notification feed for the current customer.
#   INPUTS:  page (1+), per_page (1..50), current_user, Session.
#   OUTPUTS: 200 NotificationFeedResponse.
#   SIDE_EFFECTS: none (read-only DB query).
#   LINKS:   PDD §5.2, INV-002, INV-013, services.notification_feed.
# END_CONTRACT: get_my_notifications
@router.get("/notifications", response_model=NotificationFeedResponse)
def get_my_notifications(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(_get_session),
) -> NotificationFeedResponse:
    return list_notifications_for_user(
        user_id=current_user["user_id"],
        page=page,
        per_page=per_page,
        db_session=db,
    )
