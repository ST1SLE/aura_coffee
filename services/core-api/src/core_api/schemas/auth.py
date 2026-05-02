# START_MODULE_CONTRACT
#   PURPOSE: Request/response DTOs for customer SMS-OTP authentication.
#   SCOPE:   Pydantic models for send-code, verify-code, refresh, token,
#            generic error envelope.
#   DEPENDS: pydantic v2.
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §6.5 (auth state machine),
#            INV-012 (rate-limiting), INV-013 (phone is PII — never echo back raw)
#   ROLE:    TYPES
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   SendCodeRequest    - body of POST /auth/send-code (phone)
#   VerifyCodeRequest  - body of POST /auth/verify-code (phone, 6-digit code)
#   RefreshRequest     - optional body fallback for POST /auth/refresh/logout
#   TokenResponse      - access/refresh JWT pair
#   ErrorResponse      - generic 4xx body with optional retry/attempt hints
# END_MODULE_MAP

from pydantic import BaseModel, Field


class SendCodeRequest(BaseModel):
    phone: str = Field(..., examples=["+79161234567"])


class VerifyCodeRequest(BaseModel):
    phone: str = Field(..., examples=["+79161234567"])
    code: str = Field(..., min_length=6, max_length=6, examples=["123456"])


class RefreshRequest(BaseModel):
    refresh_token: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class ErrorResponse(BaseModel):
    detail: str
    retry_after: int | None = None
    remaining_attempts: int | None = None
