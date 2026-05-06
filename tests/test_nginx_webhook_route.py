"""Regression tests for public YuKassa webhook ingress configuration."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
NGINX_CONF = REPO_ROOT / "deploy" / "nginx" / "nginx.conf"
NGINX_PRODUCTION_CONF = REPO_ROOT / "deploy" / "nginx" / "nginx.production.conf"
NGINX_PRODUCTION_TLS_CONF = (
    REPO_ROOT / "deploy" / "nginx" / "nginx.production.tls.conf.template"
)
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"
COMPOSE_PRODUCTION_FILE = REPO_ROOT / "docker-compose.production.yml"
COMPOSE_PRODUCTION_TLS_FILE = REPO_ROOT / "docker-compose.production.tls.yml"
COMPOSE_PRODUCTION_STAGING_AUTH_FILE = (
    REPO_ROOT / "docker-compose.production.staging-auth.yml"
)


def _read_nginx_config() -> str:
    return NGINX_CONF.read_text(encoding="utf-8")


def _read_production_nginx_config() -> str:
    return NGINX_PRODUCTION_CONF.read_text(encoding="utf-8")


def _read_production_tls_nginx_config() -> str:
    return NGINX_PRODUCTION_TLS_CONF.read_text(encoding="utf-8")


def _read_compose_config() -> str:
    return COMPOSE_FILE.read_text(encoding="utf-8")


def _read_production_compose_config() -> str:
    return COMPOSE_PRODUCTION_FILE.read_text(encoding="utf-8")


def _read_production_tls_compose_config() -> str:
    return COMPOSE_PRODUCTION_TLS_FILE.read_text(encoding="utf-8")


def _read_production_staging_auth_compose_config() -> str:
    return COMPOSE_PRODUCTION_STAGING_AUTH_FILE.read_text(encoding="utf-8")


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


def test_production_nginx_routes_static_spas_and_media() -> None:
    config = _read_production_nginx_config()

    assert "server web-customer:5173" not in config
    assert "server web-admin:5174" not in config
    assert "alias /usr/share/nginx/html/admin/" in config
    assert "root /usr/share/nginx/html;" in config
    assert "alias /srv/aura-coffee/media/menu/" in config


def test_production_nginx_routes_yukassa_before_generic_api() -> None:
    config = _read_production_nginx_config()

    webhook_location_index = config.index("location = /api/webhooks/yukassa")
    api_location_index = config.index("location /api/")
    assert webhook_location_index < api_location_index

    webhook_block = _location_block(config, "/api/webhooks/yukassa")
    assert "proxy_pass http://payment_webhook/webhooks/yukassa;" in webhook_block
    assert "proxy_set_header X-Forwarded-For $remote_addr;" in webhook_block
    assert "$proxy_add_x_forwarded_for" not in webhook_block


def test_production_compose_removes_dev_public_services() -> None:
    config = _read_production_compose_config()

    assert "ports: !reset []" in config
    assert "target: base" in config
    assert "dockerfile: deploy/nginx/Dockerfile" in config
    assert "profiles:" in config
    assert "dev-only" in config


def test_production_tls_nginx_terminates_https_and_keeps_acme_http() -> None:
    config = _read_production_tls_nginx_config()

    assert "listen 80;" in config
    assert "location /.well-known/acme-challenge/" in config
    assert "return 301 https://$host$request_uri;" in config
    assert "listen 443 ssl;" in config
    assert "http2 on;" in config
    assert (
        "ssl_certificate /etc/letsencrypt/live/${AURA_PUBLIC_DOMAIN}/fullchain.pem;"
        in config
    )
    assert (
        "ssl_certificate_key /etc/letsencrypt/live/${AURA_PUBLIC_DOMAIN}/privkey.pem;"
        in config
    )
    assert "auth_basic ${AURA_BASIC_AUTH_REALM};" in config
    assert "auth_basic_user_file ${AURA_BASIC_AUTH_USER_FILE};" in config


def test_production_tls_nginx_routes_yukassa_before_generic_api() -> None:
    config = _read_production_tls_nginx_config()

    webhook_location_index = config.index("location = /api/webhooks/yukassa")
    api_location_index = config.index("location /api/")
    assert webhook_location_index < api_location_index

    webhook_block = _location_block(config, "/api/webhooks/yukassa")
    assert "proxy_pass http://payment_webhook/webhooks/yukassa;" in webhook_block
    assert "proxy_set_header X-Forwarded-For $remote_addr;" in webhook_block
    assert "$proxy_add_x_forwarded_for" not in webhook_block


def test_production_tls_compose_publishes_https_and_mounts_cert_paths() -> None:
    config = _read_production_tls_compose_config()

    assert '"${NGINX_HTTP_PORT:-80}:80"' in config
    assert '"${NGINX_HTTPS_PORT:-443}:443"' in config
    assert "AURA_PUBLIC_DOMAIN is required for TLS" in config
    assert "/var/www/certbot:ro" in config
    assert "/etc/letsencrypt:ro" in config
    assert "nginx.production.tls.conf.template" in config
    assert "AURA_BASIC_AUTH_REALM: ${AURA_BASIC_AUTH_REALM:-off}" in config


def test_staging_auth_compose_mounts_htpasswd_and_enables_basic_auth() -> None:
    config = _read_production_staging_auth_compose_config()

    assert "AURA_BASIC_AUTH_REALM: Aura-Staging" in config
    assert "AURA_BASIC_AUTH_USER_FILE: /etc/nginx/staging.htpasswd" in config
    assert "AURA_STAGING_HTPASSWD_FILE is required for staging auth" in config
    assert "/etc/nginx/staging.htpasswd:ro" in config
