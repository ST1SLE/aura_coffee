# START_MODULE_CONTRACT
#   PURPOSE: Customer notification feed DTOs for GET /profile/notifications.
#   SCOPE:   NotificationFeedItem, NotificationFeedResponse.
#   DEPENDS: pydantic v2.
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §5.2
#            notifications table, INV-013 (own-user scoped messages only).
#   ROLE:    TYPES
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   NotificationFeedItem     - one in-app notification row for customer display
#   NotificationFeedResponse - paginated notification feed wrapper
# END_MODULE_MAP

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from shared.enums import NotificationChannel, NotificationStatus, NotificationType


class NotificationFeedItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID | None
    channel: NotificationChannel
    type: NotificationType
    status: NotificationStatus
    message_ru: str
    message_en: str
    sent_at: datetime | None
    created_at: datetime


class NotificationFeedResponse(BaseModel):
    notifications: list[NotificationFeedItem]
    total_count: int
    page: int
    per_page: int
