from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

import core_api.services.menu_public as menu_public_service
from core_api.deps.database import get_db
from core_api.schemas.menu import PublicMenuResponse
from core_api.services.menu_public import Language

router = APIRouter(prefix="/api/v1/menu", tags=["menu-public"])


def _parse_language(header: str | None) -> Language:
    """Выбирает язык по первому токену Accept-Language; по умолчанию RU."""
    if header and header.strip().lower().startswith("en"):
        return Language.EN
    return Language.RU


@router.get("", response_model=PublicMenuResponse)
def get_menu(
    db: Session = Depends(get_db),
    available: bool | None = Query(None),
    accept_language: str | None = Header(None, alias="Accept-Language"),
) -> PublicMenuResponse:
    return menu_public_service.get_public_menu(
        db,
        only_available=bool(available),
        language=_parse_language(accept_language),
    )
