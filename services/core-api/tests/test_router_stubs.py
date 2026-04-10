"""RED: тесты stub-роутеров меню и корзины.

Тесты 7.1–7.3 ДОЛЖНЫ падать с ImportError до создания файлов.
Тест 7.4 ДОЛЖЕН падать с AssertionError (файлов нет — нечего сканировать).
"""

import pathlib

import pytest
from fastapi import APIRouter


# ---------------------------------------------------------------------------
# 7.1 menu_admin router
# ---------------------------------------------------------------------------

def test_menu_admin_router_exists() -> None:
    from core_api.routers.menu_admin import router

    assert isinstance(router, APIRouter)
    assert router.prefix == "/api/v1/admin/menu"
    assert router.tags == ["menu-admin"]
    assert list(router.routes) == [], "Роутер menu_admin должен быть пустым (0 endpoints)"


# ---------------------------------------------------------------------------
# 7.2 menu_public router
# ---------------------------------------------------------------------------

def test_menu_public_router_exists() -> None:
    from core_api.routers.menu_public import router

    assert isinstance(router, APIRouter)
    assert router.prefix == "/api/v1/menu"
    assert router.tags == ["menu-public"]
    assert list(router.routes) == [], "Роутер menu_public должен быть пустым (0 endpoints)"


# ---------------------------------------------------------------------------
# 7.3 cart router
# ---------------------------------------------------------------------------

def test_cart_router_exists() -> None:
    from core_api.routers.cart import router

    assert isinstance(router, APIRouter)
    assert router.prefix == "/api/v1/cart"
    assert router.tags == ["cart"]
    assert list(router.routes) == [], "Роутер cart должен быть пустым (0 endpoints)"


# ---------------------------------------------------------------------------
# 7.4 Нет @router. в файлах-стабах
# ---------------------------------------------------------------------------

def test_stubs_have_no_endpoint_decorators() -> None:
    routers_dir = pathlib.Path(__file__).parents[1] / "src" / "core_api" / "routers"
    stub_files = ["menu_admin.py", "menu_public.py", "cart.py"]

    for filename in stub_files:
        path = routers_dir / filename
        if not path.exists():
            pytest.fail(f"Файл {filename} не найден — создайте stub-файл")
        content = path.read_text()
        assert "@router." not in content, (
            f"{filename} содержит endpoint-декоратор (@router.*) — stub должен быть пустым"
        )
