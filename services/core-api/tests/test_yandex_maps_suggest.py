"""RED: GET /api/v1/maps/suggest — прокси к Яндекс.Карты Suggest (PDD §7.3, §8.3).

Тесты должны падать до GREEN: роутер ещё не зарегистрирован, сервис
core_api.services.yandex_maps отсутствует. Ожидаемое поведение RED —
404 на вызовы endpoint'а и AssertionError на поведенческих проверках.

Базовый URL Yandex выбран условно (https://suggest-maps.yandex.ru/v1/suggest):
respx мокает на уровне httpx-транспорта, поэтому фактический URL фиксируется
в GREEN и может быть обновлён без перехода этих тестов в red.
"""

from __future__ import annotations

from typing import Any

import fakeredis
import httpx
import pytest
import respx
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Константы / fixture-локальный API-ключ
# ---------------------------------------------------------------------------

YANDEX_SUGGEST_BASE = "https://suggest-maps.yandex.ru/v1/suggest"
YANDEX_GEOCODER_BASE = "https://geocode-maps.yandex.ru/1.x/"
TEST_SUGGEST_API_KEY = "test-yandex-suggest-key"
TEST_GEOCODER_API_KEY = "test-yandex-geocoder-key"


@pytest.fixture(autouse=True)
def _set_yandex_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Устанавливает тестовый ключ до того, как сервис прочитает settings."""
    monkeypatch.setenv("YANDEX_MAPS_SUGGEST_API_KEY", TEST_SUGGEST_API_KEY)
    monkeypatch.setenv("YANDEX_MAPS_GEOCODER_API_KEY", TEST_GEOCODER_API_KEY)
    monkeypatch.delenv("YANDEX_MAPS_API_KEY", raising=False)
    # Сбрасываем кэш settings, если сервис его кэширует на модульном уровне.
    from core_api import settings as _settings_mod

    _settings_mod.settings.yandex_maps_api_key = ""
    _settings_mod.settings.yandex_maps_suggest_api_key = TEST_SUGGEST_API_KEY
    _settings_mod.settings.yandex_maps_geocoder_api_key = TEST_GEOCODER_API_KEY


# ---------------------------------------------------------------------------
# Канонический ответ Yandex Suggest для happy-path — два валидных совпадения.
# ---------------------------------------------------------------------------

def _suggest_response_two_matches() -> dict[str, Any]:
    return {
        "results": [
            {
                "title": {"text": "Москва, Тверская улица, 1"},
                "subtitle": {"text": "Россия, Москва"},
                "lat": 55.76,
                "lon": 37.62,
                "precision": "exact",
            },
            {
                "title": {"text": "Москва, Тверская улица, 2"},
                "subtitle": {"text": "Россия, Москва"},
                "lat": 55.761,
                "lon": 37.621,
                "precision": "number",
            },
        ]
    }


# ---------------------------------------------------------------------------
# 2.1 Happy-path — форма ответа
# ---------------------------------------------------------------------------

@respx.mock
def test_suggest_happy_path_returns_four_field_items(
    client: TestClient,
    customer_headers: dict[str, str],
    cart_redis: fakeredis.FakeRedis,
) -> None:
    respx.get(YANDEX_SUGGEST_BASE).mock(
        return_value=httpx.Response(200, json=_suggest_response_two_matches())
    )

    resp = client.get(
        "/api/v1/maps/suggest",
        params={"text": "Москва", "lang": "ru_RU"},
        headers=customer_headers,
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 2
    for item in body:
        assert set(item.keys()) == {"text", "lat", "lon", "precision"}, (
            f"Лишние или отсутствующие ключи: {item.keys()}"
        )
        assert isinstance(item["text"], str)
        assert isinstance(item["lat"], (int, float))
        assert isinstance(item["lon"], (int, float))
        assert isinstance(item["precision"], str)


# ---------------------------------------------------------------------------
# 2.2 API-ключ идёт наружу, но не наружу (INV-015)
# ---------------------------------------------------------------------------

@respx.mock
def test_suggest_forwards_api_key_in_outbound_request(
    client: TestClient,
    customer_headers: dict[str, str],
    cart_redis: fakeredis.FakeRedis,
) -> None:
    route = respx.get(YANDEX_SUGGEST_BASE).mock(
        return_value=httpx.Response(200, json=_suggest_response_two_matches())
    )

    resp = client.get(
        "/api/v1/maps/suggest",
        params={"text": "Москва", "lang": "ru_RU"},
        headers=customer_headers,
    )

    assert resp.status_code == 200, resp.text
    assert route.called, "Yandex не был вызван"
    # Ключ ДОЛЖЕН уйти к Yandex (query-string или header).
    request = route.calls.last.request
    outbound = request.url.query.decode() + " " + " ".join(
        f"{k}: {v}" for k, v in request.headers.items()
    )
    assert TEST_SUGGEST_API_KEY in outbound, (
        "Suggest API-ключ должен уходить к Yandex, но не найден в исходящем запросе"
    )
    assert TEST_GEOCODER_API_KEY not in outbound, (
        "Geocoder API-ключ не должен использоваться для Suggest-запроса"
    )

    # Ключ НЕ ДОЛЖЕН утекать в ответ клиенту (INV-015).
    assert TEST_SUGGEST_API_KEY not in resp.text, "API-ключ утёк в ответ клиента"


@respx.mock
def test_suggest_falls_back_to_legacy_yandex_maps_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from core_api import settings as _settings_mod
    from core_api.services.yandex_maps import YandexMapsClient

    legacy_key = "legacy-yandex-key"
    monkeypatch.setenv("YANDEX_MAPS_API_KEY", legacy_key)
    monkeypatch.delenv("YANDEX_MAPS_SUGGEST_API_KEY", raising=False)
    _settings_mod.settings.yandex_maps_api_key = legacy_key
    _settings_mod.settings.yandex_maps_suggest_api_key = ""

    route = respx.get(YANDEX_SUGGEST_BASE).mock(
        return_value=httpx.Response(200, json=_suggest_response_two_matches())
    )

    YandexMapsClient().suggest("Москва", "ru_RU")

    request = route.calls.last.request
    outbound = request.url.query.decode()
    assert legacy_key in outbound


# ---------------------------------------------------------------------------
# 2.3 Suggest НЕ кэшируется (PDD §8.3)
# ---------------------------------------------------------------------------

@respx.mock
def test_suggest_is_not_cached(
    client: TestClient,
    customer_headers: dict[str, str],
    cart_redis: fakeredis.FakeRedis,
) -> None:
    route = respx.get(YANDEX_SUGGEST_BASE).mock(
        return_value=httpx.Response(200, json=_suggest_response_two_matches())
    )

    r1 = client.get(
        "/api/v1/maps/suggest",
        params={"text": "Москва", "lang": "ru_RU"},
        headers=customer_headers,
    )
    r2 = client.get(
        "/api/v1/maps/suggest",
        params={"text": "Москва", "lang": "ru_RU"},
        headers=customer_headers,
    )

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert route.call_count == 2, (
        f"Suggest должен вызывать Yandex каждый раз, вызвал: {route.call_count}"
    )
    suggest_keys = [k for k in cart_redis.keys("yandex:suggest:*")]
    assert suggest_keys == [], f"Обнаружены кэш-ключи suggest: {suggest_keys}"


# ---------------------------------------------------------------------------
# 2.4 Отсутствие обязательного параметра text → 422
# ---------------------------------------------------------------------------

@respx.mock
def test_suggest_missing_text_param_422(
    client: TestClient,
    customer_headers: dict[str, str],
    cart_redis: fakeredis.FakeRedis,
) -> None:
    route = respx.get(YANDEX_SUGGEST_BASE).mock(
        return_value=httpx.Response(200, json=_suggest_response_two_matches())
    )

    resp = client.get(
        "/api/v1/maps/suggest",
        params={"lang": "ru_RU"},
        headers=customer_headers,
    )

    assert resp.status_code == 422
    assert route.call_count == 0, "Не должно быть внешних вызовов при 422"


# ---------------------------------------------------------------------------
# 2.5 Маршрут требует CUSTOMER-аутентификации
# ---------------------------------------------------------------------------

def test_suggest_requires_customer_auth(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    # Без токена — 401
    resp_unauth = client.get(
        "/api/v1/maps/suggest",
        params={"text": "Москва", "lang": "ru_RU"},
    )
    assert resp_unauth.status_code == 401, resp_unauth.text

    # Админ — 403 (не CUSTOMER)
    resp_admin = client.get(
        "/api/v1/maps/suggest",
        params={"text": "Москва", "lang": "ru_RU"},
        headers=admin_headers,
    )
    assert resp_admin.status_code == 403, resp_admin.text


# ---------------------------------------------------------------------------
# 4.1–4.4 Fallback'и при недоступности Yandex (PDD §8.3)
# ---------------------------------------------------------------------------

@respx.mock
def test_suggest_timeout_returns_503_maps_unavailable(
    client: TestClient,
    customer_headers: dict[str, str],
    cart_redis: fakeredis.FakeRedis,
) -> None:
    respx.get(YANDEX_SUGGEST_BASE).mock(
        side_effect=httpx.ReadTimeout("slow")
    )

    resp = client.get(
        "/api/v1/maps/suggest",
        params={"text": "Москва", "lang": "ru_RU"},
        headers=customer_headers,
    )
    assert resp.status_code == 503
    assert resp.json() == {"reason": "maps_unavailable"}


@respx.mock
def test_suggest_connection_error_returns_503(
    client: TestClient,
    customer_headers: dict[str, str],
    cart_redis: fakeredis.FakeRedis,
) -> None:
    respx.get(YANDEX_SUGGEST_BASE).mock(
        side_effect=httpx.ConnectError("dns fail")
    )

    resp = client.get(
        "/api/v1/maps/suggest",
        params={"text": "Москва", "lang": "ru_RU"},
        headers=customer_headers,
    )
    assert resp.status_code == 503
    assert resp.json() == {"reason": "maps_unavailable"}


@respx.mock
def test_suggest_5xx_returns_503(
    client: TestClient,
    customer_headers: dict[str, str],
    cart_redis: fakeredis.FakeRedis,
) -> None:
    respx.get(YANDEX_SUGGEST_BASE).mock(
        return_value=httpx.Response(502, json={"error": "bad gateway"})
    )

    resp = client.get(
        "/api/v1/maps/suggest",
        params={"text": "Москва", "lang": "ru_RU"},
        headers=customer_headers,
    )
    assert resp.status_code == 503
    assert resp.json() == {"reason": "maps_unavailable"}


@respx.mock
def test_suggest_4xx_bubbles_up_as_500_not_503(
    client: TestClient,
    customer_headers: dict[str, str],
    cart_redis: fakeredis.FakeRedis,
) -> None:
    """403 от Yandex — программная ошибка (плохой ключ), не 503."""
    respx.get(YANDEX_SUGGEST_BASE).mock(
        return_value=httpx.Response(403, json={"error": "forbidden"})
    )

    resp = client.get(
        "/api/v1/maps/suggest",
        params={"text": "Москва", "lang": "ru_RU"},
        headers=customer_headers,
    )
    assert resp.status_code == 500, (
        "4xx от Yandex не должен тихо маппиться в 503 — это программная ошибка"
    )
    # Тело НЕ должно содержать "maps_unavailable" — это 503-маркер.
    assert "maps_unavailable" not in resp.text
