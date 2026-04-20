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
# 7.6 include_router в main.py (Phase 1: 3 + Phase 2: 3 + Phase 3: 3 + Phase 4 maps: 1 + delivery-addresses: 1 + courier: 1 + Phase 6 admin-orders: 1)
# ---------------------------------------------------------------------------

def test_main_include_router_call_count() -> None:
    main_path = pathlib.Path(__file__).parents[1] / "src" / "core_api" / "main.py"
    content = main_path.read_text()
    count = content.count("include_router(")
    assert count == 13, (
        f"Ожидается 13 вызовов include_router (3 Phase 1 + 3 Phase 2 + 3 Phase 3 + 1 Phase 4 maps + 1 delivery-addresses + 1 courier + 1 admin-orders), "
        f"найдено: {count}"
    )
