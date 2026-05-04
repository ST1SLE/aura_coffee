"""RED: GET /api/v1/maps/geocode — прокси к Яндекс.Карты Geocoder (PDD §7.3, §8.3).

До GREEN: роутер отсутствует, тесты падают на 404 и структурных
проверках. Покрывает кэш в Redis (TTL 7 дней), precision < street → 422,
timeout/5xx/connection → 503, rate-limit (80% порог) → WARNING.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

import fakeredis
import httpx
import pytest
import respx
from fastapi.testclient import TestClient


YANDEX_GEOCODER_BASE = "https://geocode-maps.yandex.ru/1.x/"
TEST_API_KEY = "test-yandex-key"
TEST_SUGGEST_API_KEY = "test-yandex-suggest-key"
TEST_GEOCODER_API_KEY = "test-yandex-geocoder-key"
SEVEN_DAYS_SECONDS = 604800


@pytest.fixture(autouse=True)
def _set_yandex_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YANDEX_MAPS_SUGGEST_API_KEY", TEST_SUGGEST_API_KEY)
    monkeypatch.setenv("YANDEX_MAPS_GEOCODER_API_KEY", TEST_GEOCODER_API_KEY)
    monkeypatch.delenv("YANDEX_MAPS_API_KEY", raising=False)
    from core_api import settings as _settings_mod

    _settings_mod.settings.yandex_maps_api_key = ""
    _settings_mod.settings.yandex_maps_suggest_api_key = TEST_SUGGEST_API_KEY
    _settings_mod.settings.yandex_maps_geocoder_api_key = TEST_GEOCODER_API_KEY


# ---------------------------------------------------------------------------
# Канонические ответы Yandex Geocoder
# ---------------------------------------------------------------------------

def _geocoder_response(
    *,
    precision: str = "exact",
    lat: float = 55.753,
    lon: float = 37.620,
    canonical: str = "Россия, Москва, Красная площадь",
) -> dict[str, Any]:
    """Упрощённая форма Yandex GeocoderResponse, достаточная для контрактных тестов."""
    return {
        "response": {
            "GeoObjectCollection": {
                "featureMember": [
                    {
                        "GeoObject": {
                            "metaDataProperty": {
                                "GeocoderMetaData": {
                                    "precision": precision,
                                    "text": canonical,
                                }
                            },
                            "Point": {"pos": f"{lon} {lat}"},
                        }
                    }
                ]
            }
        }
    }


def _expected_cache_key(text: str) -> str:
    normalized = text.strip().casefold()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"yandex:geocode:{digest}"


def _today_rate_key() -> str:
    return f"yandex:rate:{datetime.now(UTC).strftime('%Y-%m-%d')}"


# ---------------------------------------------------------------------------
# 3.1 Happy-path — форма ответа
# ---------------------------------------------------------------------------

@respx.mock
def test_geocode_happy_path_returns_canonical_fields(
    client: TestClient,
    customer_headers: dict[str, str],
    cart_redis: fakeredis.FakeRedis,
) -> None:
    respx.get(YANDEX_GEOCODER_BASE).mock(
        return_value=httpx.Response(200, json=_geocoder_response())
    )

    resp = client.get(
        "/api/v1/maps/geocode",
        params={"text": "Moscow, Red Square"},
        headers=customer_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == {"lat", "lon", "precision", "canonical_text"}
    assert isinstance(body["lat"], (int, float))
    assert isinstance(body["lon"], (int, float))
    assert body["precision"] == "exact"
    assert isinstance(body["canonical_text"], str)
    # Ключ API не должен утечь в ответ.
    assert TEST_GEOCODER_API_KEY not in resp.text


@respx.mock
def test_geocode_forwards_geocoder_api_key(
    client: TestClient,
    customer_headers: dict[str, str],
    cart_redis: fakeredis.FakeRedis,
) -> None:
    route = respx.get(YANDEX_GEOCODER_BASE).mock(
        return_value=httpx.Response(200, json=_geocoder_response())
    )

    resp = client.get(
        "/api/v1/maps/geocode",
        params={"text": "Moscow, Red Square"},
        headers=customer_headers,
    )

    assert resp.status_code == 200, resp.text
    request = route.calls.last.request
    outbound = request.url.query.decode()
    assert TEST_GEOCODER_API_KEY in outbound
    assert TEST_SUGGEST_API_KEY not in outbound


@respx.mock
def test_geocode_falls_back_to_legacy_yandex_maps_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from core_api import settings as _settings_mod
    from core_api.services.yandex_maps import YandexMapsClient

    legacy_key = "legacy-yandex-key"
    monkeypatch.setenv("YANDEX_MAPS_API_KEY", legacy_key)
    monkeypatch.delenv("YANDEX_MAPS_GEOCODER_API_KEY", raising=False)
    _settings_mod.settings.yandex_maps_api_key = legacy_key
    _settings_mod.settings.yandex_maps_geocoder_api_key = ""

    route = respx.get(YANDEX_GEOCODER_BASE).mock(
        return_value=httpx.Response(200, json=_geocoder_response())
    )

    YandexMapsClient().geocode("Moscow, Red Square")

    request = route.calls.last.request
    outbound = request.url.query.decode()
    assert legacy_key in outbound


# ---------------------------------------------------------------------------
# 3.2 Второй запрос обслуживается из кэша (один внешний вызов)
# ---------------------------------------------------------------------------

@respx.mock
def test_geocode_cache_miss_then_hit_one_yandex_call(
    client: TestClient,
    customer_headers: dict[str, str],
    cart_redis: fakeredis.FakeRedis,
) -> None:
    route = respx.get(YANDEX_GEOCODER_BASE).mock(
        return_value=httpx.Response(200, json=_geocoder_response())
    )

    r1 = client.get(
        "/api/v1/maps/geocode",
        params={"text": "Moscow, Red Square"},
        headers=customer_headers,
    )
    r2 = client.get(
        "/api/v1/maps/geocode",
        params={"text": "Moscow, Red Square"},
        headers=customer_headers,
    )

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert route.call_count == 1, (
        f"Кэш должен обслужить второй запрос, Yandex вызван {route.call_count} раз"
    )
    assert r1.content == r2.content, "Ответы должны быть байтово идентичны"


# ---------------------------------------------------------------------------
# 3.3 Ключ кэша — sha256 нормализованного (strip + casefold) текста
# ---------------------------------------------------------------------------

@respx.mock
def test_geocode_cache_key_is_sha256_of_normalized_text(
    client: TestClient,
    customer_headers: dict[str, str],
    cart_redis: fakeredis.FakeRedis,
) -> None:
    respx.get(YANDEX_GEOCODER_BASE).mock(
        return_value=httpx.Response(200, json=_geocoder_response())
    )

    resp = client.get(
        "/api/v1/maps/geocode",
        params={"text": "  Moscow, Red Square  "},
        headers=customer_headers,
    )
    assert resp.status_code == 200, resp.text

    expected_key = _expected_cache_key("Moscow, Red Square")
    all_keys = [k.decode() if isinstance(k, bytes) else k for k in cart_redis.keys("yandex:geocode:*")]
    assert all_keys == [expected_key], (
        f"Ожидался единственный ключ {expected_key}, обнаружено: {all_keys}"
    )


# ---------------------------------------------------------------------------
# 3.4 TTL ровно 7 дней
# ---------------------------------------------------------------------------

@respx.mock
def test_geocode_cache_ttl_is_seven_days(
    client: TestClient,
    customer_headers: dict[str, str],
    cart_redis: fakeredis.FakeRedis,
) -> None:
    respx.get(YANDEX_GEOCODER_BASE).mock(
        return_value=httpx.Response(200, json=_geocoder_response())
    )

    resp = client.get(
        "/api/v1/maps/geocode",
        params={"text": "Moscow, Red Square"},
        headers=customer_headers,
    )
    assert resp.status_code == 200

    key = _expected_cache_key("Moscow, Red Square")
    ttl = cart_redis.ttl(key)
    # Допуск в 1 секунду: между setex в роутере и ttl-проверкой здесь
    # проходит ~сотни мс в pytest-сессии; контракт PDD — "7 дней".
    assert SEVEN_DAYS_SECONDS - 1 <= ttl <= SEVEN_DAYS_SECONDS, (
        f"Ожидался TTL {SEVEN_DAYS_SECONDS} (±1с), получен {ttl}"
    )


# ---------------------------------------------------------------------------
# 3.5 Низкая точность → 422, без записи в кэш
# ---------------------------------------------------------------------------

@respx.mock
def test_geocode_low_precision_returns_422_with_reason(
    client: TestClient,
    customer_headers: dict[str, str],
    cart_redis: fakeredis.FakeRedis,
) -> None:
    respx.get(YANDEX_GEOCODER_BASE).mock(
        return_value=httpx.Response(200, json=_geocoder_response(precision="other"))
    )

    resp = client.get(
        "/api/v1/maps/geocode",
        params={"text": "Random field somewhere"},
        headers=customer_headers,
    )
    assert resp.status_code == 422
    assert resp.json() == {"reason": "low_precision"}

    cache_keys = [k for k in cart_redis.keys("yandex:geocode:*")]
    assert cache_keys == [], f"Кэш не должен заполняться при 422, обнаружено: {cache_keys}"


# ---------------------------------------------------------------------------
# 3.6 precision=street — минимально допустимый уровень, принимается
# ---------------------------------------------------------------------------

@respx.mock
def test_geocode_precision_street_is_accepted(
    client: TestClient,
    customer_headers: dict[str, str],
    cart_redis: fakeredis.FakeRedis,
) -> None:
    respx.get(YANDEX_GEOCODER_BASE).mock(
        return_value=httpx.Response(200, json=_geocoder_response(precision="street"))
    )

    resp = client.get(
        "/api/v1/maps/geocode",
        params={"text": "Moscow, Tverskaya"},
        headers=customer_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["precision"] == "street"

    key = _expected_cache_key("Moscow, Tverskaya")
    assert cart_redis.exists(key) == 1, "Кэш должен заполняться при precision=street"


# ---------------------------------------------------------------------------
# 3.7 RBAC — CUSTOMER-only
# ---------------------------------------------------------------------------

def test_geocode_requires_customer_auth(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    # Без токена — 401
    resp_unauth = client.get(
        "/api/v1/maps/geocode",
        params={"text": "Москва, Тверская"},
    )
    assert resp_unauth.status_code == 401

    # Админ — 403
    resp_admin = client.get(
        "/api/v1/maps/geocode",
        params={"text": "Москва, Тверская"},
        headers=admin_headers,
    )
    assert resp_admin.status_code == 403


# ---------------------------------------------------------------------------
# 4.5–4.6 Fallback 503 при timeout / 5xx — и кэш НЕ заполняется
# ---------------------------------------------------------------------------

@respx.mock
def test_geocode_timeout_returns_503_and_skips_cache(
    client: TestClient,
    customer_headers: dict[str, str],
    cart_redis: fakeredis.FakeRedis,
) -> None:
    respx.get(YANDEX_GEOCODER_BASE).mock(
        side_effect=httpx.ReadTimeout("slow")
    )

    resp = client.get(
        "/api/v1/maps/geocode",
        params={"text": "Moscow, Red Square"},
        headers=customer_headers,
    )
    assert resp.status_code == 503
    assert resp.json() == {"reason": "maps_unavailable"}
    assert list(cart_redis.keys("yandex:geocode:*")) == []


@respx.mock
def test_geocode_5xx_returns_503_and_skips_cache(
    client: TestClient,
    customer_headers: dict[str, str],
    cart_redis: fakeredis.FakeRedis,
) -> None:
    respx.get(YANDEX_GEOCODER_BASE).mock(
        return_value=httpx.Response(500, json={"error": "oops"})
    )

    resp = client.get(
        "/api/v1/maps/geocode",
        params={"text": "Moscow, Red Square"},
        headers=customer_headers,
    )
    assert resp.status_code == 503
    assert resp.json() == {"reason": "maps_unavailable"}
    assert list(cart_redis.keys("yandex:geocode:*")) == []


# ---------------------------------------------------------------------------
# 4.7 Таймаут внешнего вызова — 3.0 секунды (проверка прямо на сервисе)
# ---------------------------------------------------------------------------

def test_geocode_timeout_budget_is_three_seconds() -> None:
    """Сервисный клиент должен иметь timeout 3.0s (connect/read)."""
    from core_api.services.yandex_maps import YandexMapsClient

    c = YandexMapsClient(api_key=TEST_API_KEY)
    timeout = c.timeout
    # Допускаем обе формы хранения: httpx.Timeout или pair of floats.
    read = float(getattr(timeout, "read", timeout))
    connect = float(getattr(timeout, "connect", timeout))
    assert read <= 3.0, f"read timeout {read} > 3.0"
    assert connect <= 3.0, f"connect timeout {connect} > 3.0"


# ---------------------------------------------------------------------------
# 5.1 Успешный вызов инкрементит дневной счётчик
# ---------------------------------------------------------------------------

@respx.mock
def test_successful_call_increments_daily_counter(
    client: TestClient,
    customer_headers: dict[str, str],
    cart_redis: fakeredis.FakeRedis,
) -> None:
    respx.get(YANDEX_GEOCODER_BASE).mock(
        return_value=httpx.Response(200, json=_geocoder_response())
    )

    before = cart_redis.get(_today_rate_key()) or b"0"
    before_val = int(before)

    resp = client.get(
        "/api/v1/maps/geocode",
        params={"text": "Moscow, Red Square"},
        headers=customer_headers,
    )
    assert resp.status_code == 200

    after = cart_redis.get(_today_rate_key())
    assert after is not None, "Счётчик rate-limit не создан"
    assert int(after) == before_val + 1


# ---------------------------------------------------------------------------
# 5.2 TTL счётчика ~48 часов
# ---------------------------------------------------------------------------

@respx.mock
def test_counter_expires_in_48h(
    client: TestClient,
    customer_headers: dict[str, str],
    cart_redis: fakeredis.FakeRedis,
) -> None:
    respx.get(YANDEX_GEOCODER_BASE).mock(
        return_value=httpx.Response(200, json=_geocoder_response())
    )

    client.get(
        "/api/v1/maps/geocode",
        params={"text": "Moscow, Red Square"},
        headers=customer_headers,
    )

    ttl = cart_redis.ttl(_today_rate_key())
    assert 86400 < ttl <= 172800, (
        f"Ожидается TTL в диапазоне (24ч, 48ч], получено {ttl}"
    )


# ---------------------------------------------------------------------------
# 5.3 Первое пересечение 80% — один WARNING с 'yandex' и '80%'
# ---------------------------------------------------------------------------

@respx.mock
def test_first_crossing_of_80_percent_emits_one_warning(
    client: TestClient,
    customer_headers: dict[str, str],
    cart_redis: fakeredis.FakeRedis,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Предзасев: 799 → после запроса станет 800 (первый raise).
    cart_redis.set(_today_rate_key(), 799)

    respx.get(YANDEX_GEOCODER_BASE).mock(
        return_value=httpx.Response(200, json=_geocoder_response())
    )

    import logging

    with caplog.at_level(logging.WARNING):
        resp = client.get(
            "/api/v1/maps/geocode",
            params={"text": "Moscow, Red Square"},
            headers=customer_headers,
        )
    assert resp.status_code == 200

    matching = [
        r for r in caplog.records
        if r.levelname == "WARNING"
        and "yandex" in r.getMessage().lower()
        and "80%" in r.getMessage()
    ]
    assert len(matching) == 1, (
        f"Ожидается ровно 1 WARNING с 'yandex' и '80%', найдено: "
        f"{[r.getMessage() for r in caplog.records]}"
    )


# ---------------------------------------------------------------------------
# 5.4 Повторные пересечения не триггерят warning
# ---------------------------------------------------------------------------

@respx.mock
def test_subsequent_crossings_do_not_reemit_warning(
    client: TestClient,
    customer_headers: dict[str, str],
    cart_redis: fakeredis.FakeRedis,
    caplog: pytest.LogCaptureFixture,
) -> None:
    cart_redis.set(_today_rate_key(), 800)
    cart_redis.set(f"{_today_rate_key()}:warned", 1)

    respx.get(YANDEX_GEOCODER_BASE).mock(
        return_value=httpx.Response(200, json=_geocoder_response())
    )

    import logging

    with caplog.at_level(logging.WARNING):
        resp = client.get(
            "/api/v1/maps/geocode",
            params={"text": "Moscow, Red Square"},
            headers=customer_headers,
        )
    assert resp.status_code == 200

    matching = [
        r for r in caplog.records
        if "yandex" in r.getMessage().lower() and "80%" in r.getMessage()
    ]
    assert matching == [], (
        f"Повторный WARNING не должен эмититься, найдено: "
        f"{[r.getMessage() for r in matching]}"
    )


# ---------------------------------------------------------------------------
# 5.5 Попадание в кэш — НЕ инкрементит счётчик
# ---------------------------------------------------------------------------

@respx.mock
def test_cache_hit_does_not_increment_counter(
    client: TestClient,
    customer_headers: dict[str, str],
    cart_redis: fakeredis.FakeRedis,
) -> None:
    respx.get(YANDEX_GEOCODER_BASE).mock(
        return_value=httpx.Response(200, json=_geocoder_response())
    )

    # Первый запрос — cache miss, счётчик +1.
    client.get(
        "/api/v1/maps/geocode",
        params={"text": "Moscow, Red Square"},
        headers=customer_headers,
    )

    after_first = int(cart_redis.get(_today_rate_key()) or b"0")
    # Жёстко ставим в 42 — чтобы однозначно увидеть отсутствие инкремента.
    cart_redis.set(_today_rate_key(), 42)

    # Второй запрос — cache hit, инкремент НЕ ожидается.
    client.get(
        "/api/v1/maps/geocode",
        params={"text": "Moscow, Red Square"},
        headers=customer_headers,
    )

    after_second = int(cart_redis.get(_today_rate_key()) or b"0")
    assert after_second == 42, (
        f"Cache-hit не должен инкрементить счётчик: было 42, стало {after_second} "
        f"(после первого запроса счётчик был {after_first})"
    )
