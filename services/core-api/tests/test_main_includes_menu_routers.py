"""RED: тесты регистрации роутеров в main.py.

Тесты ДОЛЖНЫ падать с AssertionError до добавления include_router в main.py.
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

    paths = schema.get("paths", {})
    # menu_admin и menu_public пока стабы — путей нет; cart реализован в GREEN
    for prefix in ("/api/v1/admin/menu", "/api/v1/menu"):
        matching = [p for p in paths if p.startswith(prefix)]
        assert matching == [], (
            f"Ожидается 0 путей под {prefix!r}, найдено: {matching}"
        )


# ---------------------------------------------------------------------------
# 7.6 Ровно 6 include_router в main.py
# ---------------------------------------------------------------------------

def test_main_include_router_call_count() -> None:
    main_path = pathlib.Path(__file__).parents[1] / "src" / "core_api" / "main.py"
    content = main_path.read_text()
    count = content.count("include_router(")
    assert count == 6, (
        f"Ожидается 6 вызовов include_router (3 Phase 1 + 3 Phase 2), найдено: {count}"
    )
