"""Regression tests for public YuKassa webhook ingress configuration."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
NGINX_CONF = REPO_ROOT / "deploy" / "nginx" / "nginx.conf"
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"


def _read_nginx_config() -> str:
    return NGINX_CONF.read_text(encoding="utf-8")


def _read_compose_config() -> str:
    return COMPOSE_FILE.read_text(encoding="utf-8")


def _location_block(config: str, location: str) -> str:
    match = re.search(
        rf"location\s*=\s*{re.escape(location)}\s*\{{(?P<body>.*?)\n\s*\}}",
        config,
        flags=re.DOTALL,
    )
    assert match is not None, f"missing exact nginx location for {location}"
    return match.group("body")


def test_nginx_routes_yukassa_public_path_to_payment_webhook() -> None:
    config = _read_nginx_config()

    assert "upstream payment_webhook" in config
    webhook_location_index = config.index("location = /api/webhooks/yukassa")
    api_location_index = config.index("location /api/")
    assert webhook_location_index < api_location_index

    webhook_block = _location_block(config, "/api/webhooks/yukassa")
    assert "proxy_pass http://payment_webhook/webhooks/yukassa;" in webhook_block


def test_nginx_routes_health_to_core_api() -> None:
    config = _read_nginx_config()

    assert "upstream api" in config
    health_block = _location_block(config, "/health")
    assert "proxy_pass http://api/health;" in health_block


def test_nginx_overwrites_forwarded_for_on_webhook_route() -> None:
    webhook_block = _location_block(_read_nginx_config(), "/api/webhooks/yukassa")

    assert "proxy_set_header X-Real-IP $remote_addr;" in webhook_block
    assert "proxy_set_header X-Forwarded-For $remote_addr;" in webhook_block
    assert "$proxy_add_x_forwarded_for" not in webhook_block


def test_nginx_waits_for_payment_webhook_service() -> None:
    config = _read_compose_config()
    nginx_service = config[config.index("  nginx:") :]

    assert "      - payment-webhook" in nginx_service
