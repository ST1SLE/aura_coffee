# START_MODULE_CONTRACT
#   PURPOSE: Read-only customer notification feed over in-app Notification rows.
#   SCOPE:   list_notifications_for_user.
#   DEPENDS: M-SHARED (Notification, NotificationChannel), M-DATABASE,
#            schemas.notification_feed.
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §5.2 notifications,
#            INV-002, INV-013.
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   list_notifications_for_user - own-user paginated in-app notification feed
# END_MODULE_MAP
"""Customer notification-feed queries (PDD §5.2 notifications)."""

from __future__ import annotations

import uuid  # noqa: TC003

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core_api.schemas.notification_feed import (
    NotificationFeedItem,
    NotificationFeedResponse,
)
from shared.enums import NotificationChannel
from shared.models.notification import Notification


# START_CONTRACT: list_notifications_for_user
#   PURPOSE: Return the current customer's in-app notification rows newest
#            first; SMS rows are delivery/audit records and are excluded from
#            the customer-facing feed.
#   INPUTS:  user_id: UUID, page: int, per_page: int, db_session: Session.
#   OUTPUTS: NotificationFeedResponse.
#   SIDE_EFFECTS: DB SELECTs only.
#   LINKS:   PDD §5.2, INV-002, INV-013.
# END_CONTRACT: list_notifications_for_user
def list_notifications_for_user(
    *,
    user_id: uuid.UUID,
    page: int,
    per_page: int,
    db_session: Session,
) -> NotificationFeedResponse:
    where_clauses = [
        Notification.user_id == user_id,
        Notification.channel == NotificationChannel.IN_APP,
    ]
    total = db_session.execute(
        select(func.count()).select_from(Notification).where(*where_clauses)
    ).scalar_one()

    rows = (
        db_session.execute(
            select(Notification)
            .where(*where_clauses)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        .scalars()
        .all()
    )

    return NotificationFeedResponse(
        notifications=[NotificationFeedItem.model_validate(row) for row in rows],
        total_count=int(total),
        page=page,
        per_page=per_page,
    )
