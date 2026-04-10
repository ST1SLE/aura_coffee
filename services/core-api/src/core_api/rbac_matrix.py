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
    # ── Admin menu: categories ──────────────────────────────────────────────
    ("POST",   "/api/v1/admin/menu/categories"):               {ADMIN},
    ("GET",    "/api/v1/admin/menu/categories"):               {ADMIN, BARISTA},
    ("PUT",    "/api/v1/admin/menu/categories/{category_id}"): {ADMIN},
    ("DELETE", "/api/v1/admin/menu/categories/{category_id}"): {ADMIN},
    # ── Admin menu: items ──────────────────────────────────────────────────
    ("POST",   "/api/v1/admin/menu/items"):                          {ADMIN},
    ("GET",    "/api/v1/admin/menu/items"):                          {ADMIN, BARISTA},
    ("GET",    "/api/v1/admin/menu/items/{item_id}"):                {ADMIN, BARISTA},
    ("PUT",    "/api/v1/admin/menu/items/{item_id}"):                {ADMIN},
    ("DELETE", "/api/v1/admin/menu/items/{item_id}"):                {ADMIN},
    ("PATCH",  "/api/v1/admin/menu/items/{item_id}/availability"):   {ADMIN, BARISTA},
    ("PUT",    "/api/v1/admin/menu/items/{item_id}/modifiers"):      {ADMIN},
    # ── Admin menu: modifiers ─────────────────────────────────────────────
    ("POST",   "/api/v1/admin/menu/modifiers"):                            {ADMIN},
    ("GET",    "/api/v1/admin/menu/modifiers"):                            {ADMIN, BARISTA},
    ("PUT",    "/api/v1/admin/menu/modifiers/{modifier_id}"):              {ADMIN},
    ("DELETE", "/api/v1/admin/menu/modifiers/{modifier_id}"):              {ADMIN},
    ("PATCH",  "/api/v1/admin/menu/modifiers/{modifier_id}/availability"): {ADMIN, BARISTA},
    # ── Admin menu: sizes ─────────────────────────────────────────────────
    ("POST",   "/api/v1/admin/menu/sizes"):            {ADMIN},
    ("PUT",    "/api/v1/admin/menu/sizes/{size_id}"):  {ADMIN},
    ("DELETE", "/api/v1/admin/menu/sizes/{size_id}"):  {ADMIN},
    # Корзина — только CUSTOMER (INV-002, design D6)
    ("GET",    "/api/v1/cart"):                 {CUSTOMER},
    ("DELETE", "/api/v1/cart"):                 {CUSTOMER},
    ("POST",   "/api/v1/cart/items"):            {CUSTOMER},
    ("PATCH",  "/api/v1/cart/items/{line_id}"): {CUSTOMER},
    ("DELETE", "/api/v1/cart/items/{line_id}"): {CUSTOMER},
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
