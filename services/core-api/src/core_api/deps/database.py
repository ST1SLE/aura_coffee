# START_MODULE_CONTRACT
#   PURPOSE: FastAPI dependency providing a SQLAlchemy Session per request
#            (no auto-commit — handlers/services own their transactions).
#   SCOPE:   engine, SessionLocal, get_db generator + get_session test alias.
#   DEPENDS: M-SHARED (settings), M-DATABASE (ORM models), SQLAlchemy.
#   LINKS:   docs/development-plan.xml M-CORE-API, M-DATABASE; PDD §4.1
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   engine        - SQLAlchemy Engine bound to settings.database_url
#   SessionLocal  - sessionmaker factory producing Session objects
#   get_db        - FastAPI dep yielding a Session, no auto-commit
#   get_session   - alias of get_db; kept stable for test monkey-patching
# END_MODULE_MAP

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from core_api.settings import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine)


# START_CONTRACT: get_db
#   PURPOSE: Yield a SQLAlchemy Session for one request and close it at the
#            end. Does NOT auto-commit — caller controls the transaction.
#   INPUTS:  none
#   OUTPUTS: Generator[Session, None, None]
#   SIDE_EFFECTS: opens DB connection, closes it on teardown.
#   LINKS:   PDD §4.1, INV-004 (financial mutations need explicit single tx)
# END_CONTRACT: get_db
def get_db() -> Generator[Session, None, None]:
    """FastAPI-зависимость: сессия БД."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Алиас — тесты патчат core_api.deps.database.get_session
get_session = get_db
