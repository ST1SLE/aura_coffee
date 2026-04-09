import re

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from core_api.rbac_matrix import PUBLIC_ROUTES, ROUTE_MATRIX
from core_api.services.auth import AuthService


def _compile_pattern(path_pattern: str) -> re.Pattern[str]:
    """Конвертация паттерна с {param} в regex."""
    regex = re.sub(r"\{[^}]+\}", r"[^/]+", path_pattern)
    return re.compile(f"^{regex}$")


def _match_route(
    method: str, path: str, matrix: dict[tuple[str, str], set[str]]
) -> set[str] | None:
    """Поиск подходящего правила: longest-prefix (самый специфичный паттерн)."""
    best_match: set[str] | None = None
    best_length = -1

    for (rule_method, rule_pattern), roles in matrix.items():
        if rule_method != method:
            continue
        compiled = _compile_pattern(rule_pattern)
        if compiled.match(path) and len(rule_pattern) > best_length:
            best_match = roles
            best_length = len(rule_pattern)

    return best_match


def _is_public(method: str, path: str) -> bool:
    """Проверка, является ли маршрут публичным."""
    for rule_method, rule_pattern in PUBLIC_ROUTES:
        if rule_method != method:
            continue
        if _compile_pattern(rule_pattern).match(path):
            return True
    return False


# Внутренние маршруты FastAPI — не подлежат RBAC
_INTERNAL_PREFIXES = ("/docs", "/redoc", "/openapi.json")


class RBACMiddleware(BaseHTTPMiddleware):
    """Middleware для централизованной проверки ролей по матрице доступа."""

    async def dispatch(self, request: Request, call_next) -> Response:
        method = request.method
        path = request.url.path

        # OPTIONS — пропускаем для CORS preflight
        if method == "OPTIONS":
            return await call_next(request)

        # Внутренние маршруты FastAPI (docs, redoc, openapi)
        if path.startswith(_INTERNAL_PREFIXES):
            return await call_next(request)

        # Публичные маршруты — без аутентификации
        if _is_public(method, path):
            return await call_next(request)

        # Извлечение токена из Authorization header
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Not authenticated"},
            )

        token = auth_header[len("Bearer "):]

        try:
            payload = AuthService.decode_access_token(token)
        except Exception:
            return JSONResponse(
                status_code=401,
                content={"detail": "Not authenticated"},
            )

        role = payload.get("role", "")

        # Поиск правила в матрице
        allowed_roles = _match_route(method, path, ROUTE_MATRIX)

        if allowed_roles is None:
            # Default-deny: маршрут не найден ни в матрице, ни в публичных
            return JSONResponse(
                status_code=403,
                content={"detail": "Insufficient permissions"},
            )

        if role not in allowed_roles:
            return JSONResponse(
                status_code=403,
                content={"detail": "Insufficient permissions"},
            )

        return await call_next(request)
