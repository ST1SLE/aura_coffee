# START_MODULE_CONTRACT
#   PURPOSE: Staff (admin/barista/courier) authentication DTOs — login,
#            refresh, logout, token response with role.
#   SCOPE:   Pydantic models for /api/v1/staff/auth/*.
#   DEPENDS: pydantic v2.
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §6.5 (auth FSM),
#            INV-002, INV-010 (role isolation)
#   ROLE:    TYPES
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   StaffLoginRequest    - POST /staff/auth/login body (login, password)
#   StaffTokenResponse   - JWT pair + role
#   StaffRefreshRequest  - POST /staff/auth/refresh body
#   StaffLogoutRequest   - POST /staff/auth/logout body
# END_MODULE_MAP

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
