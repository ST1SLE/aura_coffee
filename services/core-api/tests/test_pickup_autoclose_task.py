"""RED: тесты Celery-таски `pickup.close_stale`.

Фиксируют контракт тонкой обёртки вокруг
`core_api.services.pickup_autoclose.close_stale_pickups`:
- таска зарегистрирована в `celery_app.tasks` под именем `pickup.close_stale`;
- вызов в eager-mode дергает сервис с `(Session, datetime)` аргументами.

GREEN-цикл добавляет `core_api.tasks.pickup_autoclose` и регистрирует через
`Celery(..., include=["core_api.tasks.pickup_autoclose"])`.
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session


def test_task_registered_under_expected_name() -> None:
    from core_api.celery_app import celery_app

    # Побочный импорт — в GREEN celery_app.include должен автоматически
    # подтянуть модуль tasks.pickup_autoclose; принудительный импорт здесь
    # делает тест независимым от порядка загрузки.
    import core_api.tasks.pickup_autoclose  # noqa: F401

    assert "pickup.close_stale" in celery_app.tasks


def test_task_invokes_service(monkeypatch) -> None:
    from core_api.celery_app import celery_app

    # Импортируем модули сервиса и таски — RED упадёт здесь по ImportError.
    import core_api.services.pickup_autoclose as svc_mod
    from core_api.tasks.pickup_autoclose import close_stale_pickups_task

    mock = MagicMock(return_value=0)
    monkeypatch.setattr(svc_mod, "close_stale_pickups", mock)

    # Eager mode: .apply() исполняет таску в текущем потоке без брокера.
    celery_app.conf.task_always_eager = True
    try:
        result = close_stale_pickups_task.apply().get()
    finally:
        celery_app.conf.task_always_eager = False

    assert result == 0
    assert mock.call_count == 1
    args, kwargs = mock.call_args
    # Первый аргумент — Session, второй — UTC-aware datetime.
    assert isinstance(args[0], Session)
    assert isinstance(args[1], datetime)
    assert args[1].tzinfo is not None
