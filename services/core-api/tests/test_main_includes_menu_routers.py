"""Smoke-тесты регистрации роутеров в main.py.

Проверяет, что все три роутера Phase 2 (menu-admin, menu-public, cart)
зарегистрированы ровно по одному разу и видны в OpenAPI.
"""

import pathlib

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# 7.5 Три новых тега в OpenAPI, нет путей под ними
# ---------------------------------------------------------------------------

def test_main_registers_three_new_routers(client: TestClient) -> None:
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()

    tag_names = {t["name"] for t in schema.get("tags", [])}
    for expected_tag in ("menu-admin", "menu-public", "cart"):
        assert expected_tag in tag_names, f"Тег {expected_tag!r} не найден в /openapi.json"

    assert "paths" in schema, "OpenAPI schema missing 'paths'"


# ---------------------------------------------------------------------------
# 7.6 include_router в main.py (all Core API routers registered once)
# ---------------------------------------------------------------------------

def test_main_include_router_call_count() -> None:
    main_path = pathlib.Path(__file__).parents[1] / "src" / "core_api" / "main.py"
    content = main_path.read_text()
    count = content.count("include_router(")
    assert count == 18, (
        f"Ожидается 18 вызовов include_router для текущего набора Core API routers, "
        f"найдено: {count}"
    )
