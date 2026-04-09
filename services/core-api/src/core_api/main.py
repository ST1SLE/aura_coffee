from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core_api.routers.auth import router as auth_router
from core_api.settings import settings

app = FastAPI(title="Aura Coffee API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
