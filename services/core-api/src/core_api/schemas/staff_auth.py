from pydantic import BaseModel, Field


class StaffLoginRequest(BaseModel):
    login: str = Field(..., examples=["admin"])
    password: str = Field(..., examples=["secret123"])


class StaffTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: str


class StaffRefreshRequest(BaseModel):
    refresh_token: str


class StaffLogoutRequest(BaseModel):
    refresh_token: str
