# START_MODULE_CONTRACT
#   PURPOSE: Declarative single source of truth for route-level RBAC: maps
#            (HTTP method, path pattern) → allowed role set, plus the public
#            (no-auth) route allowlist.
#   SCOPE:   Role constants, ROUTE_MATRIX, PUBLIC_ROUTES. No runtime logic —
#            consumed by core_api.middleware.rbac.
#   DEPENDS: stdlib only.
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §6, PDD §7.1, INV-002,
#            INV-010 (role isolation), INV-011 (promo admin)
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   CUSTOMER       - role string constant for end-user role
#   ADMIN          - role string constant for shop administrator
#   BARISTA        - role string constant for in-shop staff
#   COURIER        - role string constant for delivery courier
#   ALL_STAFF      - frozenset-like {ADMIN, BARISTA, COURIER}
#   ALL_ROLES      - {CUSTOMER} | ALL_STAFF
#   ROUTE_MATRIX   - dict[(method, path_pattern), set[role]] — RBAC matrix
#   PUBLIC_ROUTES  - set[(method, path_pattern)] — no-auth routes
# END_MODULE_MAP

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
    ("DELETE", "/api/v1/profile"): {CUSTOMER},
    # Лояльность личного кабинета (PDD §3, §7.1 Phase 5 item 2) — только customer
    ("GET", "/api/v1/profile/loyalty"):              {CUSTOMER},
    ("GET", "/api/v1/profile/loyalty/transactions"): {CUSTOMER},
    # Лента уведомлений клиента — только customer, только свои строки
    ("GET", "/api/v1/profile/notifications"):        {CUSTOMER},
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
    ("PATCH",  "/api/v1/admin/menu/items/{item_id}/inventory"):      {ADMIN, BARISTA},
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
    ("POST", "/api/v1/orders/estimate"):     {CUSTOMER},
    ("GET",  "/api/v1/orders/{order_id}"):   {CUSTOMER},
    # ── Staff-действия над заказом (PDD §6.1, §7.6) ─────────────────────────
    ("PATCH", "/api/v1/orders/{order_id}/status"): {BARISTA, COURIER, ADMIN},
    ("POST",  "/api/v1/orders/{order_id}/cancel"): {CUSTOMER, ADMIN},
    # История заказов и repeat (PDD §7.7) — только CUSTOMER
    ("GET",  "/api/v1/orders"):                       {CUSTOMER},
    ("POST", "/api/v1/orders/{order_id}/repeat"):     {CUSTOMER},
    # Yandex.Maps-прокси (PDD §7.3, §8.3) — только CUSTOMER
    ("GET", "/api/v1/maps/suggest"):                  {CUSTOMER},
    ("POST", "/api/v1/maps/suggest"):                 {CUSTOMER},
    ("GET", "/api/v1/maps/geocode"):                  {CUSTOMER},
    ("POST", "/api/v1/maps/geocode"):                 {CUSTOMER},
    # ── Admin orders feed (PDD §4.5, INV-010) — admin + barista ───────────
    ("GET", "/api/v1/admin/orders"):              {ADMIN, BARISTA},
    ("GET", "/api/v1/admin/orders/{order_id}"):   {ADMIN, BARISTA},
    # ── Admin refund recovery (PDD §6.2, INV-016) — только ADMIN ──────────
    ("POST", "/api/v1/admin/orders/{order_id}/refund/retry"): {ADMIN},
    # ── Admin dashboard stats (PDD §4.5, §7.1 Phase 6 item 1, INV-010) — только ADMIN ──
    ("GET", "/api/v1/admin/stats"): {ADMIN},
    # ── Admin users (PDD §6.5, §7.1 Phase 6 item 2, INV-010) — только ADMIN ──
    ("GET",  "/api/v1/admin/users"):                                   {ADMIN},
    ("GET",  "/api/v1/admin/users/{user_id}"):                         {ADMIN},
    ("POST", "/api/v1/admin/users/{user_id}/block"):                   {ADMIN},
    ("POST", "/api/v1/admin/users/{user_id}/unblock"):                 {ADMIN},
    ("DELETE", "/api/v1/admin/users/{user_id}"):                       {ADMIN},
    ("POST", "/api/v1/admin/users/{user_id}/loyalty/adjust"):          {ADMIN},
    # ── Admin promocodes (PDD §6.6, INV-010, INV-011) — только ADMIN ──────
    ("POST",  "/api/v1/admin/promocodes"):                            {ADMIN},
    ("GET",   "/api/v1/admin/promocodes"):                            {ADMIN},
    ("GET",   "/api/v1/admin/promocodes/{promocode_id}"):             {ADMIN},
    ("PATCH", "/api/v1/admin/promocodes/{promocode_id}"):             {ADMIN},
    ("POST",  "/api/v1/admin/promocodes/{promocode_id}/activate"):    {ADMIN},
    ("POST",  "/api/v1/admin/promocodes/{promocode_id}/deactivate"):  {ADMIN},
    # ── Admin shop settings (PDD §5.2, §6.1, §7.1 Phase 6 item 3) — только ADMIN ──
    ("GET", "/api/v1/admin/settings"): {ADMIN},
    ("PUT", "/api/v1/admin/settings"): {ADMIN},
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
