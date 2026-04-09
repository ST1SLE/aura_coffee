from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core_api.middleware.rbac import RBACMiddleware
from core_api.routers.auth import router as auth_router
from core_api.routers.profile import router as profile_router
from core_api.routers.staff_auth import router as staff_auth_router
from core_api.settings import settings

app = FastAPI(title="Aura Coffee API")

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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
