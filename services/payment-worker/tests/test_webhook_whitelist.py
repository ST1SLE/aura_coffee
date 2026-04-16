"""RED: расширение _is_whitelisted — поддержка hostname'ов и запрет wildcard.

Записи в YUKASSA_WEBHOOK_IPS, не являющиеся IP/CIDR, резолвятся через
socket.gethostbyname (кэшируется). Wildcard "*" НЕ является permissive.
"""

from __future__ import annotations

from unittest.mock import patch


def test_hostname_entry_resolves_and_matches() -> None:
    from payment_worker.webhook import _is_whitelisted

    with patch(
        "payment_worker.webhook.socket.gethostbyname",
        return_value="172.20.0.5",
    ):
        assert _is_whitelisted("172.20.0.5", ["payment-worker"]) is True


def test_wildcard_is_not_permissive() -> None:
    from payment_worker.webhook import _is_whitelisted

    assert _is_whitelisted("1.2.3.4", ["*"]) is False


def test_localhost_default_accepted() -> None:
    from payment_worker.webhook import _is_whitelisted

    assert _is_whitelisted(
        "127.0.0.1", ["127.0.0.1", "payment-worker", "payment-webhook"]
    ) is True
