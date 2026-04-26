# START_MODULE_CONTRACT
#   PURPOSE: Customer profile DTOs (read + partial-update).
#   SCOPE:   ProfileResponse, ProfileUpdateRequest.
#   DEPENDS: pydantic v2.
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §3 (customer profile),
#            INV-013 (phone is PII — only exposed as phone_masked, never raw)
#   ROLE:    TYPES
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   ProfileResponse       - GET /api/v1/profile body (phone_masked, not raw)
#   ProfileUpdateRequest  - PATCH /api/v1/profile body (display_name, language)
# END_MODULE_MAP

import uuid
from typing import Literal

from pydantic import BaseModel, Field


class ProfileResponse(BaseModel):
    user_id: uuid.UUID
    phone_masked: str
    display_name: str | None
    preferred_language: str


class ProfileUpdateRequest(BaseModel):
    display_name: str | None = Field(None, min_length=1, max_length=100)
    preferred_language: Literal["ru", "en"] | None = None
