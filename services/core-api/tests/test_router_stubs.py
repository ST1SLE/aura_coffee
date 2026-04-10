"""RED: тесты stub-роутеров меню и корзины.

Тесты 7.1–7.3 ДОЛЖНЫ падать с ImportError до создания файлов.
Тест 7.4 ДОЛЖЕН падать с AssertionError (файлов нет — нечего сканировать).

Примечание (add-public-menu): stub-проверка «routes is empty» для menu_public
заменена проверкой «GET /api/v1/menu зарегистрирован» — после реализации
эндпоинта роутер больше не должен быть пустым.
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
    # menu_admin больше не stub: endpoints добавлены в menu-admin-crud
    assert len(list(router.routes)) > 0, "Роутер menu_admin должен содержать endpoints"


# ---------------------------------------------------------------------------
# 7.2 menu_public router
# ---------------------------------------------------------------------------

def test_menu_public_router_exists() -> None:
    from core_api.routers.menu_public import router

    assert isinstance(router, APIRouter)
    assert router.prefix == "/api/v1/menu"
    assert router.tags == ["menu-public"]


def test_menu_public_router_has_get_route() -> None:
    """RED (add-public-menu): GET / зарегистрирован в роутере.

    Падает до реализации (роутер пуст), проходит после GREEN.
    """
    from core_api.routers.menu_public import router

    methods = {
        method
        for route in router.routes
        for method in getattr(route, "methods", set())
    }
    assert "GET" in methods, "GET / не зарегистрирован в menu_public router"


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
    # menu_admin больше не stub (см. menu-router-stubs delta spec)
    routers_dir = pathlib.Path(__file__).parents[1] / "src" / "core_api" / "routers"
    # menu_admin.py и menu_public.py больше не stubs (menu-admin-crud + add-public-menu) —
    # остаётся только cart.py
    stub_files = ["cart.py"]

    for filename in stub_files:
        path = routers_dir / filename
        if not path.exists():
            pytest.fail(f"Файл {filename} не найден — создайте stub-файл")
        content = path.read_text()
        assert "@router." not in content, (
            f"{filename} содержит endpoint-декоратор (@router.*) — stub должен быть пустым"
        )
