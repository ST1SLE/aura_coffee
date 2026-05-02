"""Schemas for admin refund retry responses (PDD §6.2)."""
# START_MODULE_CONTRACT
#   PURPOSE: DTOs for the admin refund-retry command response. The command is
#            a queued side effect; payment state is still owned by the
#            payment-worker task and webhook lifecycle.
#   SCOPE:   Pydantic response models only.
#   DEPENDS: pydantic v2, stdlib uuid.
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §6.2, INV-002, INV-016
#   ROLE:    TYPES
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   RefundRetryResponse - POST /api/v1/admin/orders/{order_id}/refund/retry body
# END_MODULE_MAP

from __future__ import annotations

import uuid  # noqa: TC003

from pydantic import BaseModel


class RefundRetryResponse(BaseModel):
    """Admin refund retry enqueue result."""

    order_id: uuid.UUID
    payment_id: uuid.UUID
    payment_status: str
    queued: bool = True
