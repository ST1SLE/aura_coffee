from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core_api.middleware.rbac import RBACMiddleware
from core_api.routers.auth import router as auth_router
from core_api.routers.delivery_addresses import router as delivery_addresses_router
from core_api.routers.profile import router as profile_router
from core_api.routers.profile_loyalty import router as profile_loyalty_router
from core_api.routers.staff_auth import router as staff_auth_router

from core_api.routers.menu_admin import router as menu_admin_router
from core_api.routers.menu_public import router as menu_public_router
from core_api.routers.cart import router as cart_router
from core_api.routers.orders import orders_router
from core_api.routers.courier import router as courier_router
from core_api.routers.order_actions import router as order_actions_router
from core_api.routers.order_history import router as order_history_router
from core_api.routers.admin_orders import router as admin_orders_router
from core_api.routers.admin_users import router as admin_users_router
from core_api.routers.admin_promocodes import router as admin_promocodes_router
from core_api.routers.admin_stats import router as admin_stats_router
from core_api.routers.yandex_maps import router as yandex_maps_router
from core_api.settings import settings

app = FastAPI(
    title="Aura Coffee API",
    openapi_tags=[
        {"name": "menu-admin"},
        {"name": "menu-public"},
        {"name": "cart"},
        {"name": "orders"},
        {"name": "maps"},
    ],
)

# Starlette LIFO: последний добавленный middleware обрабатывает запрос первым.
# CORS добавляется после RBAC → CORS перехватывает preflight до RBAC.
app.add_middleware(RBACMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(profile_loyalty_router)
app.include_router(
    delivery_addresses_router, prefix="/api/v1/profile/addresses"
)
app.include_router(staff_auth_router)
app.include_router(menu_admin_router)
app.include_router(menu_public_router)
app.include_router(cart_router)
app.include_router(orders_router)
app.include_router(order_actions_router)
app.include_router(order_history_router)
app.include_router(admin_orders_router)
app.include_router(admin_users_router)
app.include_router(admin_promocodes_router)
app.include_router(admin_stats_router)
app.include_router(yandex_maps_router)
app.include_router(courier_router)


@app.get("/health")
def health() -> dict[str, str]:
    # yukassa_backend читаем напрямую из env: core-api не импортирует
    # payment_worker — сохраняем независимость модулей.
    import os

    return {
        "status": "ok",
        "yukassa_backend": os.getenv("YUKASSA_BACKEND", "live"),
    }
