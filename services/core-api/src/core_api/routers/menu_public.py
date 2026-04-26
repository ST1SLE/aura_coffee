# START_MODULE_CONTRACT
#   PURPOSE: Public read-only menu endpoint under /api/v1/menu — no auth.
#   SCOPE:   Returns the customer-facing menu, optionally filtered to
#            only-available items, localized via Accept-Language header.
#   DEPENDS: M-DATABASE (Session), core_api.services.menu_public,
#            core_api.deps.database.
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §5 menu, §7.1 menu.
#            INV-002 does not apply — endpoint is read-only and public.
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   router    - APIRouter("/api/v1/menu", tags=["menu-public"])
#   get_menu  - GET /api/v1/menu
# END_MODULE_MAP

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


# START_CONTRACT: get_menu
#   PURPOSE: Return the public localized menu.
#   INPUTS:  Session, available: bool|None (query),
#            Accept-Language header.
#   OUTPUTS: 200 PublicMenuResponse.
#   SIDE_EFFECTS: none (read-only DB query).
#   LINKS:   PDD §5, services.menu_public.
# END_CONTRACT: get_menu
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
