from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from core_api.settings import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI-зависимость: сессия БД."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Алиас — тесты патчат core_api.deps.database.get_session
get_session = get_db
