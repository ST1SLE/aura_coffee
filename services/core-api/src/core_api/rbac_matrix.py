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
    # Сохранённые адреса доставки — только customer (PDD §3, §5.2)
    ("GET",    "/api/v1/profile/addresses"):              {CUSTOMER},
    ("POST",   "/api/v1/profile/addresses"):              {CUSTOMER},
    ("PATCH",  "/api/v1/profile/addresses/{address_id}"): {CUSTOMER},
    ("DELETE", "/api/v1/profile/addresses/{address_id}"): {CUSTOMER},
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
    # Заказы — только CUSTOMER (INV-010: изоляция ролей, PDD §7.1 item 2)
    ("POST", "/api/v1/orders"):              {CUSTOMER},
    ("GET",  "/api/v1/orders/{order_id}"):   {CUSTOMER},
    # ── Staff-действия над заказом (PDD §6.1, §7.6) ─────────────────────────
    ("PATCH", "/api/v1/orders/{order_id}/status"): {BARISTA, COURIER, ADMIN},
    ("POST",  "/api/v1/orders/{order_id}/cancel"): {CUSTOMER, ADMIN},
    # История заказов и repeat (PDD §7.7) — только CUSTOMER
    ("GET",  "/api/v1/orders"):                       {CUSTOMER},
    ("POST", "/api/v1/orders/{order_id}/repeat"):     {CUSTOMER},
    # Yandex.Maps-прокси (PDD §7.3, §8.3) — только CUSTOMER
    ("GET", "/api/v1/maps/suggest"):                  {CUSTOMER},
    ("GET", "/api/v1/maps/geocode"):                  {CUSTOMER},
    # ── Admin orders feed (PDD §4.5, INV-010) — admin + barista ───────────
    ("GET", "/api/v1/admin/orders"):              {ADMIN, BARISTA},
    ("GET", "/api/v1/admin/orders/{order_id}"):   {ADMIN, BARISTA},
    # ── Курьерская панель (PDD §6.3, INV-010) — только COURIER ─────────────
    ("GET",  "/api/v1/courier/assignments/available"):                {COURIER},
    ("GET",  "/api/v1/courier/assignments/mine"):                     {COURIER},
    ("POST", "/api/v1/courier/assignments/{assignment_id}/take"):     {COURIER},
    ("POST", "/api/v1/courier/assignments/{assignment_id}/pickup"):   {COURIER},
    ("POST", "/api/v1/courier/assignments/{assignment_id}/deliver"):  {COURIER},
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
