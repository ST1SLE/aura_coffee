from pydantic import BaseModel, Field


class SendCodeRequest(BaseModel):
    phone: str = Field(..., examples=["+79161234567"])


class VerifyCodeRequest(BaseModel):
    phone: str = Field(..., examples=["+79161234567"])
    code: str = Field(..., min_length=6, max_length=6, examples=["123456"])


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class ErrorResponse(BaseModel):
    detail: str
    retry_after: int | None = None
    remaining_attempts: int | None = None
