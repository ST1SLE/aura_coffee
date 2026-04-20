## 1. GREEN — Schemas

- [x] 1.1 [core-api] GREEN: Create `services/core-api/src/core_api/schemas/yandex_maps.py` with three Pydantic v2 models:
  - `Suggestion(BaseModel)`: fields `text: str`, `lat: float`, `lon: float`, `precision: str`. `model_config = ConfigDict(extra="forbid")` so RED's "exactly these keys" assertion holds.
  - `GeocodeResult(BaseModel)`: fields `lat: float`, `lon: float`, `precision: str`, `canonical_text: str`. Same `extra="forbid"`.
  - `MapsErrorReason`: a string enum (or `Literal["maps_unavailable", "low_precision"]`) — keep simple, used only in error responses.
  Satisfies contract-shape assertions in RED tests 2.1 and 3.1.

## 2. GREEN — Service module

- [x] 2.1 [core-api] GREEN: Create `services/core-api/src/core_api/services/yandex_maps.py`:
  - `PRECISION_ORDER: tuple[str, ...] = ("other", "near", "range", "street", "number", "exact")`.
  - `MIN_PRECISION_INDEX = PRECISION_ORDER.index("street")`.
  - `class MapsUnavailableError(RuntimeError): ...` — raised on timeout / connect error / 5xx.
  - `class YandexMapsClient:` with `__init__(self, api_key: str, timeout: float = 3.0)`. Constructs `self._client = httpx.Client(timeout=httpx.Timeout(timeout))`. Exposes `self.timeout = self._client.timeout` (so RED test 4.7 can assert `client.timeout.connect == 3.0`).
  - `def suggest(self, text: str, lang: str) -> list[Suggestion]:` — GET `https://suggest-maps.yandex.ru/v1/suggest` with params `{"text": text, "lang": lang, "apikey": self.api_key, "print_address": 1}`. Parse response (`results[]` array, each with `title.text` / `address.formatted_address` / `distance` / `tags`). Re-read `settings.yandex_maps_api_key` on every call — do NOT cache the key in `__init__`.
  - `def geocode(self, text: str) -> GeocodeResult | None:` — GET `https://geocode-maps.yandex.ru/1.x` with params `{"geocode": text, "apikey": self.api_key, "format": "json", "results": 1}`. Parse `response.GeoObjectCollection.featureMember[0].GeoObject`. Extract `Point.pos` ("lon lat" space-separated), `metaDataProperty.GeocoderMetaData.precision`, `metaDataProperty.GeocoderMetaData.text` as canonical_text. Return `None` if no matches.
  - Error classification inside both methods: wrap httpx call in `try/except`. Catch `httpx.TimeoutException`, `httpx.ConnectError`, `httpx.NetworkError` → raise `MapsUnavailableError`. Then call `resp.raise_for_status()` and catch `httpx.HTTPStatusError` where `500 <= status < 600` → raise `MapsUnavailableError`. 4xx from `raise_for_status` propagates unchanged (bubbles to FastAPI as 500).
  - Helper `is_low_precision(precision: str) -> bool` OR inline the `PRECISION_ORDER.index(p) < MIN_PRECISION_INDEX` check; keep it in this module.
  Satisfies RED tests 4.1–4.7 (error classification, timeout budget) and the geocode-parsing logic consumed by 3.x.

## 3. GREEN — Router module

- [x] 3.1 [core-api] GREEN: Create `services/core-api/src/core_api/routers/yandex_maps.py`:
  - `router = APIRouter(prefix="/api/v1/maps", tags=["maps"])`.
  - Module-level lazy client: `_CLIENT: YandexMapsClient | None = None` + `_get_client() -> YandexMapsClient` that reads `settings.yandex_maps_api_key` and constructs on first use.
  - Helper `_bump_daily_rate(redis, logger) -> None`: computes `yandex:rate:{UTC YYYY-MM-DD}`, `INCR`, sets 48h TTL if count==1, then `SET NX EX` on the `:warned` sibling key if `count >= 800` and logs `"yandex daily quota crossed 80%% (...)"` on successful NX. Log message MUST contain the substrings `"yandex"` and `"80%"` (RED 5.3).
  - `GET /suggest` handler: accepts `text: str = Query(..., min_length=1)` and `lang: str = Query("ru_RU")`. Depends on `Depends(get_redis)`. Try `client.suggest(text, lang)`; on `MapsUnavailableError` return `JSONResponse(status_code=503, content={"reason": "maps_unavailable"})`. On success, call `_bump_daily_rate`, return the list of `Suggestion` objects.
  - `GET /geocode` handler: accepts `text: str = Query(..., min_length=1)`. Depends on Redis. Compute `cache_key = f"yandex:geocode:{sha256(text.strip().casefold().encode()).hexdigest()}"`. If `cached = redis.get(cache_key)` → return `Response(content=cached, media_type="application/json")` (do NOT bump counter on cache hit, do NOT re-parse). Else call `client.geocode(text)`; on `MapsUnavailableError` → 503 JSONResponse; on `None` or `PRECISION_ORDER.index(result.precision) < MIN_PRECISION_INDEX` → raise `HTTPException(422, detail={"reason": "low_precision"})`. On success: `serialized = result.model_dump_json()`; `redis.setex(cache_key, 604800, serialized)`; `_bump_daily_rate(...)`; return `Response(content=serialized, media_type="application/json")`.
  - The `HTTPException(422, detail={"reason": "low_precision"})` flow goes through FastAPI's default handler, which wraps detail as `{"detail": {"reason": "..."}}`. RED test 3.5 expects `body == {"reason": "low_precision"}` — so use `JSONResponse(status_code=422, content={"reason": "low_precision"})` instead of `HTTPException` for that branch.
  Satisfies RED tests 2.1–2.5, 3.1–3.7, 4.1–4.7, 5.1–5.5.

## 4. GREEN — Wiring

- [x] 4.1 [core-api] GREEN: `services/core-api/src/core_api/rbac_matrix.py` — add two entries:
  ```python
  ("GET", "/api/v1/maps/suggest"):  {CUSTOMER},
  ("GET", "/api/v1/maps/geocode"):  {CUSTOMER},
  ```
  Place in a new block with a short Russian comment (`# Yandex.Maps-прокси (PDD §7.3, §8.3) — только CUSTOMER`).
  Satisfies RED test `test_rbac_matrix.py::TestYandexMapsRbac::test_yandex_maps_routes_registered_for_customer_only`.

- [x] 4.2 [core-api] GREEN: `services/core-api/src/core_api/main.py`:
  - Import `from core_api.routers.yandex_maps import router as yandex_maps_router`.
  - Add `{"name": "maps"}` to `openapi_tags`.
  - Add `app.include_router(yandex_maps_router)` after the last existing `include_router` call.
  Satisfies RED test `test_main_includes_maps_router.py`.

- [x] 4.3 [core-api] GREEN: `services/core-api/tests/test_main_includes_menu_routers.py::test_main_include_router_call_count` — update the assertion from `== 9` to `== 10`. Exempt from "write tests first" because it is a counter tracking the include_router invocation count, not a behavioral assertion.

## 5. VERIFY — All RED tests flip to green

- [x] 5.1 [core-api] VERIFY: `docker compose exec core-api pytest services/core-api/tests/test_yandex_maps_suggest.py services/core-api/tests/test_yandex_maps_geocode.py services/core-api/tests/test_rbac_matrix.py services/core-api/tests/test_main_includes_maps_router.py services/core-api/tests/test_main_includes_menu_routers.py -q` — all 23 new tests PASS; the call-count test passes with `== 10`.

- [x] 5.2 [core-api] VERIFY: Run full core-api suite: `docker compose exec core-api pytest services/core-api/tests -q`. Confirm the number of failures equals the 19 pre-existing baseline failures (no new regressions introduced by GREEN). Any new failure MUST be triaged before archive.

- [x] 5.3 [core-api] VERIFY: `docker compose exec core-api python -c "from core_api.main import app; print(sorted({r.path for r in app.routes if r.path.startswith('/api/v1/maps')}))"` — prints `['/api/v1/maps/geocode', '/api/v1/maps/suggest']`.

- [x] 5.4 [core-api] VERIFY: `openspec validate yandex-maps-proxy-green --strict` — passes.
