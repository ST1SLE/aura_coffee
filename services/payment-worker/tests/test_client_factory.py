"""RED: контракт get_yukassa_client() factory в payment_worker.tasks.

Фабрика должна выбирать live/fake клиент по settings.yukassa_backend и
вызываться на каждом исполнении таски (а не один раз на импорт модуля).
"""

from __future__ import annotations

import importlib
from unittest.mock import patch

import pytest


def _reload_tasks():
    import payment_worker.settings as settings_module
    import payment_worker.tasks as tasks_module

    importlib.reload(settings_module)
    importlib.reload(tasks_module)
    return tasks_module


def test_factory_returns_live_client_by_default(monkeypatch) -> None:
    monkeypatch.setenv("YUKASSA_SHOP_ID", "real")
    monkeypatch.setenv("YUKASSA_SECRET_KEY", "real")
    monkeypatch.setenv("YUKASSA_BASE_URL", "https://api.yookassa.ru/v3")

    tasks = _reload_tasks()
    from payment_worker.yukassa_client import YukassaClient

    client = tasks.get_yukassa_client()
    assert isinstance(client, YukassaClient)


def test_factory_returns_fake_when_backend_fake(monkeypatch) -> None:
    monkeypatch.setenv("YUKASSA_BACKEND", "fake")

    tasks = _reload_tasks()
    from payment_worker.yukassa_fake import FakeYukassaClient

    client = tasks.get_yukassa_client()
    assert isinstance(client, FakeYukassaClient)


def test_factory_is_called_per_task_not_at_import(
    monkeypatch, seed_user_order_payment
) -> None:
    """Каждый вызов create_payment должен обращаться к фабрике заново.

    Если клиент создавался один раз на импорт модуля — счётчик останется 1.
    """
    monkeypatch.setenv("YUKASSA_BACKEND", "fake")

    tasks = _reload_tasks()
    order_id = str(seed_user_order_payment["order"].id)

    calls = []

    def _fake_factory():
        calls.append(1)
        # вернём мок с нужными методами
        from unittest.mock import MagicMock

        m = MagicMock()
        m.create_payment.return_value = {
            "payment_id": "fake_1",
            "confirmation_url": "http://localhost:8240/x",
            "status": "pending",
        }
        return m

    with patch.object(tasks, "get_yukassa_client", _fake_factory):
        # Вызываем create_payment дважды напрямую (через .apply для sync).
        tasks.create_payment.apply(args=(order_id, 100, "idem-1")).get(
            disable_sync_subtasks=False
        )
        tasks.create_payment.apply(args=(order_id, 100, "idem-2")).get(
            disable_sync_subtasks=False
        )

    assert len(calls) == 2
