"""Production deployment hardening regressions for audit findings.

These tests read deploy artifacts directly. They do not need Docker or secrets.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_core_api_production_command_suppresses_uvicorn_access_logs() -> None:
    """Address PII must not enter Core API container access logs."""
    compose = _read("docker-compose.production.yml")

    assert "--no-access-log" in compose


def test_nginx_access_logs_use_no_query_format_per_server() -> None:
    """Nginx must not inherit the default $request access log with query text."""
    expected_server_counts = {
        "deploy/nginx/nginx.production.conf": 1,
        "deploy/nginx/nginx.production.tls.conf.template": 2,
    }

    for relative, server_count in expected_server_counts.items():
        conf = _read(relative)
        assert '"$request_method $uri $server_protocol"' in conf
        assert conf.count("access_log /var/log/nginx/access.log aura_no_query;") == (
            server_count
        )


def test_tls_nginx_template_sets_browser_security_headers() -> None:
    """Public TLS entry point carries baseline browser hardening headers."""
    template = _read("deploy/nginx/nginx.production.tls.conf.template")

    assert 'add_header Content-Security-Policy "' in template
    assert "frame-ancestors 'none'" in template
    assert 'add_header X-Frame-Options "DENY" always;' in template
    assert 'add_header Permissions-Policy "' in template
    assert (
        'add_header Strict-Transport-Security "max-age=15552000" always;'
        in template
    )


def test_nginx_templates_deny_common_sensitive_scanner_paths() -> None:
    """Scanner bait paths should not fall through to SPA HTML."""
    for relative in (
        "deploy/nginx/nginx.production.conf",
        "deploy/nginx/nginx.production.tls.conf.template",
    ):
        conf = _read(relative)
        assert r"location ~ /\.(?!well-known/acme-challenge/)" in conf
        assert r"server-status|docs|redoc|openapi\.json" in conf
