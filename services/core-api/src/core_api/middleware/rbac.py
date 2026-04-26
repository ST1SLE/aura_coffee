# START_MODULE_CONTRACT
#   PURPOSE: Centralised ASGI middleware that enforces the route-level RBAC
#            matrix on every non-OPTIONS request. Decodes the Bearer JWT,
#            looks up the longest-matching matrix rule, and replies with 401
#            (no/invalid auth) or 403 (role denied / unmapped route).
#   SCOPE:   RBACMiddleware class + private route-matching helpers.
#   DEPENDS: M-CORE-API (rbac_matrix, services.auth), Starlette.
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §4.1, INV-002,
#            INV-010 (role isolation), INV-011
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   RBACMiddleware - Starlette BaseHTTPMiddleware enforcing ROUTE_MATRIX
# END_MODULE_MAP

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


# START_CONTRACT: RBACMiddleware
#   PURPOSE: ASGI middleware enforcing route-level RBAC for every request.
#            Skips OPTIONS (CORS preflight), FastAPI internal docs, and
#            PUBLIC_ROUTES. Otherwise requires a valid Bearer JWT and a
#            ROUTE_MATRIX entry whose role set contains the caller.
#   INPUTS:  Inherited Starlette BaseHTTPMiddleware __init__(app, ...).
#   OUTPUTS: RBACMiddleware instance; .dispatch returns the wrapped Response
#            or a JSONResponse(401/403) on auth/role failure.
#   SIDE_EFFECTS: parses Authorization header; calls AuthService.decode_access_token;
#                 returns 401 on missing/invalid token, 403 on role denial or
#                 default-deny when no matrix rule matches.
#   LINKS:   PDD §4.1, INV-002, INV-010
# END_CONTRACT: RBACMiddleware
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
