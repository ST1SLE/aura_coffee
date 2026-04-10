# Декларативная матрица доступа: маршрут → допустимые роли.
# Единственный источник истины для авторизации на уровне маршрутов.

# Все роли в системе
CUSTOMER = "customer"
ADMIN = "admin"
BARISTA = "barista"
COURIER = "courier"

ALL_STAFF = {ADMIN, BARISTA, COURIER}
ALL_ROLES = {CUSTOMER, *ALL_STAFF}

# (HTTP-метод, паттерн пути) → множество допустимых ролей
ROUTE_MATRIX: dict[tuple[str, str], set[str]] = {
    # Профиль — только customer
    ("GET", "/api/v1/profile"): {CUSTOMER},
    ("PATCH", "/api/v1/profile"): {CUSTOMER},
    # Logout — любой аутентифицированный пользователь
    ("POST", "/api/v1/auth/logout"): ALL_ROLES,
    ("POST", "/api/v1/staff/auth/logout"): ALL_STAFF,
}

# Маршруты без аутентификации
PUBLIC_ROUTES: set[tuple[str, str]] = {
    ("GET", "/health"),
    ("POST", "/api/v1/auth/send-code"),
    ("POST", "/api/v1/auth/verify-code"),
    ("POST", "/api/v1/auth/refresh"),
    ("POST", "/api/v1/staff/auth/login"),
    ("POST", "/api/v1/staff/auth/refresh"),
    # Публичное меню — доступно без авторизации
    ("GET", "/api/v1/menu"),
}
