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
