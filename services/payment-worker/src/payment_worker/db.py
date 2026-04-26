"""Ленивая инициализация SQLAlchemy-движка и сессии.

Разнесено в отдельный модуль, чтобы tasks/webhook могли патчиться в тестах
через ``payment_worker.tasks.get_engine`` / ``payment_worker.webhook.get_engine``
(см. RED-тесты).
"""

# START_MODULE_CONTRACT
#   PURPOSE: Provide a lazy SQLAlchemy engine + transactional session scope so
#            Celery tasks and the webhook FastAPI app share one DB access pattern
#            without importing Settings on module load (Settings has live-mode
#            safety-rails that must NOT fire on test imports).
#   SCOPE:   Engine factory + session context manager. Re-exported by tasks.py
#            and webhook.py as patch targets for tests.
#   DEPENDS: SQLAlchemy 2.x, stdlib os
#   LINKS:   docs/development-plan.xml M-PAYMENT-WORKER, PDD §4.2, INV-004
#            (atomic compensation requires single-transaction scope)
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   get_engine    - lazy SQLAlchemy Engine factory (singleton per-process)
#   session_scope - context manager yielding a Session with auto commit/rollback
# END_MODULE_MAP

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.engine import Engine

_engine: Engine | None = None


# START_CONTRACT: get_engine
#   PURPOSE: Lazily build the per-process SQLAlchemy Engine; reads DATABASE_URL
#            on first call so tests can patch this symbol without triggering
#            Settings-validation side-effects.
#   INPUTS:  none
#   OUTPUTS: sqlalchemy.engine.Engine — process-singleton engine
#   SIDE_EFFECTS: caches the engine in a module-level global; opens a connection
#                 pool against DATABASE_URL on first invocation.
#   LINKS:   docs/development-plan.xml M-PAYMENT-WORKER, PDD §4.2
# END_CONTRACT: get_engine
def get_engine() -> Engine:
    """Ленивое создание engine: читаем DATABASE_URL из env на первый вызов.

    Не тянем Settings на import — у Settings есть safety-rail на YuKassa-creds,
    который не должен падать во время import db.py (тесты патчат get_engine).
    """
    global _engine
    if _engine is None:
        import os

        database_url = os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://postgres:postgres@postgres:5432/aura",
        )
        _engine = create_engine(database_url, future=True)
    return _engine


# START_CONTRACT: session_scope
#   PURPOSE: Yield a SQLAlchemy Session that auto-commits on clean exit and
#            rolls back on any exception — required for INV-004 atomic
#            compensation (Payment + Order + LoyaltyTransaction must succeed
#            or fail together).
#   INPUTS:  engine: Engine | None — optional override (tests inject SQLite);
#                                    defaults to get_engine().
#   OUTPUTS: Iterator[Session] — context-managed Session
#   SIDE_EFFECTS: opens a Session bound to the engine; commits or rolls back
#                 the underlying DB transaction on context exit.
#   LINKS:   PDD §4.2, INV-004 (atomic), INV-016 (explicit transitions)
# END_CONTRACT: session_scope
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
