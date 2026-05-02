"""DTOs for account deletion responses (PDD §6.5, INV-013)."""

# START_MODULE_CONTRACT
#   PURPOSE: Response DTO shared by customer and admin account-deletion
#            endpoints.
#   SCOPE:   AccountDeletionResponse only; contains no phone/profile/address
#            fields and exposes only opaque ids plus non-PII operation counts.
#   DEPENDS: pydantic v2.
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §6.5, INV-013.
#   ROLE:    TYPES
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   AccountDeletionResponse - DELETE /profile and DELETE /admin/users/{id} body
# END_MODULE_MAP

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict


class AccountDeletionResponse(BaseModel):
    """Non-PII account-deletion result."""

    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    status: Literal["deleted"]
    cancelled_orders_count: int
    pii_rows_removed: int
