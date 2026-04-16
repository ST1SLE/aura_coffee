"""Ленивая инициализация SQLAlchemy-движка и сессии.

Разнесено в отдельный модуль, чтобы tasks/webhook могли патчиться в тестах
через ``payment_worker.tasks.get_engine`` / ``payment_worker.webhook.get_engine``
(см. RED-тесты).
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from payment_worker.settings import settings

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.engine import Engine

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(settings.database_url, future=True)
    return _engine


@contextmanager
def session_scope(engine: Engine | None = None) -> Iterator[Session]:
    """Сессия с автоматическим commit/rollback.

    ``engine`` можно прокинуть снаружи (используется в webhook, куда тесты
    подкладывают SQLite через patch ``get_engine``).
    """
    eng = engine or get_engine()
    session = Session(bind=eng, expire_on_commit=False)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
