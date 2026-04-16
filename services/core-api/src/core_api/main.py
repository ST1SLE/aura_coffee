from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core_api.middleware.rbac import RBACMiddleware
from core_api.routers.auth import router as auth_router
from core_api.routers.profile import router as profile_router
from core_api.routers.staff_auth import router as staff_auth_router

from core_api.routers.menu_admin import router as menu_admin_router
from core_api.routers.menu_public import router as menu_public_router
from core_api.routers.cart import router as cart_router
from core_api.routers.orders import orders_router
from core_api.settings import settings

app = FastAPI(
    title="Aura Coffee API",
    openapi_tags=[
        {"name": "menu-admin"},
        {"name": "menu-public"},
        {"name": "cart"},
        {"name": "orders"},
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
app.include_router(staff_auth_router)
app.include_router(menu_admin_router)
app.include_router(menu_public_router)
app.include_router(cart_router)
app.include_router(orders_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
