# START_MODULE_CONTRACT
#   PURPOSE: FastAPI dependency factory enforcing per-route role checks at
#            the handler signature level (complementary to the global
#            RBACMiddleware). INV-002 + INV-010 enforcement point.
#   SCOPE:   require_role factory.
#   DEPENDS: M-CORE-API (deps.auth.get_current_user), FastAPI.
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §4.1, INV-002,
#            INV-010 (role isolation)
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   require_role - factory(*roles) -> FastAPI dep that 403s callers without role
# END_MODULE_MAP

from fastapi import Depends, HTTPException, status

from core_api.deps.auth import get_current_user


# START_CONTRACT: require_role
#   PURPOSE: Build a FastAPI dependency that allows only the listed roles.
#            Returns the resolved user dict on success, raises 403 otherwise.
#   INPUTS:  *allowed_roles: str — variadic role names that may access route
#   OUTPUTS: Callable[..., dict] — FastAPI dependency callable
#   SIDE_EFFECTS: dependency raises HTTPException(403) when role not allowed.
#   LINKS:   PDD §4.1, INV-002, INV-010
# END_CONTRACT: require_role
def require_role(*allowed_roles: str):
    """Фабрика FastAPI-зависимости для проверки роли пользователя."""

    def _check_role(
        current_user: dict = Depends(get_current_user),
    ) -> dict:
        if current_user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return _check_role
