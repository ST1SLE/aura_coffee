from fastapi import Depends, HTTPException, status

from core_api.deps.auth import get_current_user


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
