"""RED: Yandex Maps router зарегистрирован в main.py и виден в OpenAPI."""

from fastapi.testclient import TestClient


def test_main_registers_yandex_maps_router(client: TestClient) -> None:
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()

    paths = schema.get("paths", {})
    assert "/api/v1/maps/suggest" in paths, (
        "GET /api/v1/maps/suggest не зарегистрирован в OpenAPI"
    )
    assert "/api/v1/maps/geocode" in paths, (
        "GET /api/v1/maps/geocode не зарегистрирован в OpenAPI"
    )
    # Оба endpoint'а — GET.
    assert "get" in paths["/api/v1/maps/suggest"]
    assert "get" in paths["/api/v1/maps/geocode"]
