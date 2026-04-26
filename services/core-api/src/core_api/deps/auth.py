# START_MODULE_CONTRACT
#   PURPOSE: FastAPI dependency that decodes the Bearer JWT and resolves the
#            calling user identity + role for downstream handlers. INV-002
#            enforcement entry point at the router-dependency layer.
#   SCOPE:   get_current_user dependency + private HTTPBearer instance.
#   DEPENDS: M-CORE-API (services.auth.AuthService), FastAPI security helpers.
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §4.1, INV-002
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   get_current_user - FastAPI dep returning {"user_id": UUID, "role": str}
# END_MODULE_MAP

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core_api.services.auth import AuthService

_bearer = HTTPBearer()


# START_CONTRACT: get_current_user
#   PURPOSE: Decode the Authorization Bearer JWT and return the caller's
#            identity. Raises 401 on missing/invalid/expired token.
#   INPUTS:  credentials: HTTPAuthorizationCredentials — injected by FastAPI
#            from the Authorization header via HTTPBearer.
#   OUTPUTS: dict — {"user_id": uuid.UUID, "role": str}
#   SIDE_EFFECTS: raises HTTPException(401) on decode failure.
#   LINKS:   PDD §4.1 (auth boundary), INV-002 (server-side auth)
# END_CONTRACT: get_current_user
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """FastAPI-зависимость: декодирование JWT из Authorization header."""
    try:
        payload = AuthService.decode_access_token(credentials.credentials)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "user_id": uuid.UUID(payload["sub"]),
        "role": payload["role"],
    }
