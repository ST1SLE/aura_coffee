# START_MODULE_CONTRACT
#   PURPOSE: SQLAlchemy 2.0 engine + sessionmaker for core-api request handlers.
#            Provides the auto-commit get_db() generator used by legacy callers
#            outside the deps/ package.
#   SCOPE:   Module-level engine, SessionLocal factory, get_db generator.
#   DEPENDS: M-SHARED (settings), SQLAlchemy.
#   LINKS:   docs/development-plan.xml M-CORE-API, M-DATABASE; PDD §4.1
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   engine        - SQLAlchemy Engine bound to settings.database_url
#   SessionLocal  - sessionmaker factory producing Session objects bound to engine
#   get_db        - generator dependency yielding a Session, auto-commits on success
# END_MODULE_MAP

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from core_api.settings import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine)


# START_CONTRACT: get_db
#   PURPOSE: Yield a SQLAlchemy Session for the current request, commit on
#            normal completion, rollback on any exception, always close.
#   INPUTS:  none
#   OUTPUTS: Generator[Session, None, None] — single Session yielded once
#   SIDE_EFFECTS: opens DB connection, commits transaction on success,
#                 rolls back and re-raises on exception, closes session.
#   LINKS:   PDD §4.1, INV-004 (financial atomicity expects a single tx scope)
# END_CONTRACT: get_db
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
