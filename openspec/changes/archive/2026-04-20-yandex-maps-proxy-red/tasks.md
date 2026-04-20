## 1. PREREQ — Environment, settings, dependencies

- [x] 1.1 [core-api] PREREQ: Add `yandex_maps_api_key: str = ""` to `Settings` in `services/core-api/src/core_api/settings.py` (single-field addition; no behavior change). Exempt from TDD — a smoke import-time assertion is enough.
- [x] 1.2 [core-api] PREREQ: Add `YANDEX_MAPS_API_KEY=` under a new `# Yandex Maps` section in `.env.example`. Placeholder empty string; production overrides in real `.env`.
- [x] 1.3 [core-api] PREREQ: Promote `httpx>=0.27,<1.0` from `[dev]` extras to the main `dependencies` list in `services/core-api/pyproject.toml` AND add `respx>=0.21,<1.0` to `[dev]`. Done when `pip show httpx` resolves and `respx` is importable in tests.

## 2. RED — Suggest endpoint contract

- [x] 2.1 [core-api] RED: `services/core-api/tests/test_yandex_maps_suggest.py::test_suggest_happy_path_returns_four_field_items` — `respx.get` Yandex suggest URL returning two canned matches; call `GET /api/v1/maps/suggest?text=Москва&lang=ru_RU` with `customer_headers`; assert status 200 and body is a list whose items each have exactly the keys `text`, `lat`, `lon`, `precision` (superset rejected). Fails today: router module does not exist (ImportError from `main.py` if added, else 404 because endpoint is unregistered).
- [x] 2.2 [core-api] RED: `test_yandex_maps_suggest.py::test_suggest_forwards_api_key_in_outbound_request` — assert `respx` captured request includes `apikey=<settings.yandex_maps_api_key>` in its query string AND the inbound response body does NOT contain the key literal. Pins INV-015. Fails same as 2.1.
- [x] 2.3 [core-api] RED: `test_yandex_maps_suggest.py::test_suggest_is_not_cached` — set `respx` mock once; call endpoint twice with identical `text` + `lang`; assert `respx.calls.call_count == 2`; query `fakeredis` for any key starting with `yandex:suggest` and assert the list is empty. Fails same as 2.1.
- [x] 2.4 [core-api] RED: `test_yandex_maps_suggest.py::test_suggest_missing_text_param_422` — call without `text`; assert 422 and `respx` has zero outbound calls. Fails today: no endpoint → 404 instead of 422.
- [x] 2.5 [core-api] RED: `test_yandex_maps_suggest.py::test_suggest_requires_customer_auth` — call with no `Authorization` header → assert 401; call with `admin_headers` → assert 403. Fails today: route absent from `ROUTE_MATRIX` so middleware default-denies with 403 regardless of role; the "no auth → 401" branch is the failing one pre-GREEN.

## 3. RED — Geocode endpoint contract

- [x] 3.1 [core-api] RED: `services/core-api/tests/test_yandex_maps_geocode.py::test_geocode_happy_path_returns_canonical_fields` — `respx.get` Yandex geocoder returns one match with `precision="exact"`; `GET /api/v1/maps/geocode?text=Moscow,%20Red%20Square` with customer auth; assert 200 and body has exactly the keys `lat`, `lon`, `precision`, `canonical_text` (no `api_key`, no `yandex_raw`). Fails: endpoint does not exist.
- [x] 3.2 [core-api] RED: `test_yandex_maps_geocode.py::test_geocode_cache_miss_then_hit_one_yandex_call` — make two identical geocode requests back-to-back; assert `respx.calls.call_count == 1`; assert response bytes of both calls are byte-identical. Fails same as 3.1.
- [x] 3.3 [core-api] RED: `test_yandex_maps_geocode.py::test_geocode_cache_key_is_sha256_of_normalized_text` — call with `text="  Moscow, Red Square  "`; inspect `fakeredis` keys; assert exactly one key matches `yandex:geocode:<hex>` where `<hex>` equals `sha256("moscow, red square".encode()).hexdigest()` (lower/stripped/casefolded). Fails same as 3.1.
- [x] 3.4 [core-api] RED: `test_yandex_maps_geocode.py::test_geocode_cache_ttl_is_seven_days` — after a successful geocode, assert `fakeredis.ttl("yandex:geocode:<hex>") == 604800`. Fails same as 3.1.
- [x] 3.5 [core-api] RED: `test_yandex_maps_geocode.py::test_geocode_low_precision_returns_422_with_reason` — Yandex returns `precision="other"`; assert 422 and body `{"reason": "low_precision"}`; assert cache is NOT populated (no `yandex:geocode:*` key). Fails same as 3.1.
- [x] 3.6 [core-api] RED: `test_yandex_maps_geocode.py::test_geocode_precision_street_is_accepted` — Yandex returns `precision="street"`; assert 200 and cache populated. Pins the inclusive floor. Fails same as 3.1.
- [x] 3.7 [core-api] RED: `test_yandex_maps_geocode.py::test_geocode_requires_customer_auth` — 401 without token, 403 with `admin_headers`. Same shape as 2.5.

## 4. RED — External-failure fallback (503)

- [x] 4.1 [core-api] RED: `test_yandex_maps_suggest.py::test_suggest_timeout_returns_503_maps_unavailable` — `respx.get(...).mock(side_effect=httpx.ReadTimeout("slow"))`; assert 503 with body `{"reason": "maps_unavailable"}`. Fails same as 2.1.
- [x] 4.2 [core-api] RED: `test_yandex_maps_suggest.py::test_suggest_connection_error_returns_503` — `side_effect=httpx.ConnectError("dns fail")`; assert 503 + same body. Fails same as 2.1.
- [x] 4.3 [core-api] RED: `test_yandex_maps_suggest.py::test_suggest_5xx_returns_503` — `respx.get(...).mock(return_value=httpx.Response(502))`; assert 503 + same body. Fails same as 2.1.
- [x] 4.4 [core-api] RED: `test_yandex_maps_suggest.py::test_suggest_4xx_bubbles_up_as_500_not_503` — `httpx.Response(403)`; assert 500 (not 503). Pins D5 from design.md. Fails same as 2.1.
- [x] 4.5 [core-api] RED: `test_yandex_maps_geocode.py::test_geocode_timeout_returns_503_and_skips_cache` — simulate `ReadTimeout`; assert 503 + body; assert `fakeredis` has no `yandex:geocode:*` key for this text. Fails same as 3.1.
- [x] 4.6 [core-api] RED: `test_yandex_maps_geocode.py::test_geocode_5xx_returns_503_and_skips_cache` — `httpx.Response(500)`; assert 503 and no cache key. Fails same as 3.1.
- [x] 4.7 [core-api] RED: `test_yandex_maps_geocode.py::test_geocode_timeout_budget_is_three_seconds` — inspect the httpx client (or capture the request's `timeout` in `respx`) and assert `request.extensions.get("timeout", {}).get("connect") <= 3.0` and `... .get("read") <= 3.0`, OR via a parallel unit test on the service object: `client.timeout.connect == 3.0 and client.timeout.read == 3.0`. Prefer the direct client-attribute assertion for stability. Fails same as 3.1.

## 5. RED — Daily rate-limit observability

- [x] 5.1 [core-api] RED: `test_yandex_maps_geocode.py::test_successful_call_increments_daily_counter` — freeze date to `2026-05-01` via `freezegun` OR directly assert `fakeredis.get("yandex:rate:<today>")` is incremented by 1 after one successful call. Fails: endpoint missing AND counter logic unimplemented.
- [x] 5.2 [core-api] RED: `test_yandex_maps_geocode.py::test_counter_expires_in_48h` — after a successful call, assert `fakeredis.ttl("yandex:rate:<today>")` is ≤ 172800 and > 86400. Fails same as 5.1.
- [x] 5.3 [core-api] RED: `test_yandex_maps_geocode.py::test_first_crossing_of_80_percent_emits_one_warning` — pre-seed `fakeredis.set("yandex:rate:<today>", 799)`; call endpoint once with `caplog` at `WARNING`; assert exactly one record whose message contains both `"yandex"` and `"80%"`. Fails same as 5.1.
- [x] 5.4 [core-api] RED: `test_yandex_maps_geocode.py::test_subsequent_crossings_do_not_reemit_warning` — pre-seed counter at 800 AND set `yandex:rate:<today>:warned` = `1`; make a call; assert `caplog` has zero matching records. Fails same as 5.1.
- [x] 5.5 [core-api] RED: `test_yandex_maps_geocode.py::test_cache_hit_does_not_increment_counter` — first call populates cache; pre-seed counter at 42; second (cache-hit) call; assert counter still 42. Fails same as 5.1.

## 6. RED — RBAC matrix registration

- [x] 6.1 [core-api] RED: `services/core-api/tests/test_rbac_matrix.py` — extend the existing test file (or add a new test inside it) `test_yandex_maps_routes_registered_for_customer_only`: assert both `("GET", "/api/v1/maps/suggest")` and `("GET", "/api/v1/maps/geocode")` are present in `ROUTE_MATRIX` and map to exactly `{CUSTOMER}`; assert neither appears in `PUBLIC_ROUTES`. Fails today: entries not yet in the matrix.

## 7. RED — Router wiring

- [x] 7.1 [core-api] RED: `services/core-api/tests/test_main_includes_menu_routers.py` (or a new peer file `test_main_includes_maps_router.py`) — import `core_api.main` and assert the app has routes `GET /api/v1/maps/suggest` and `GET /api/v1/maps/geocode` registered. Fails today: `main.py` does not include the router. Keep the assertion style consistent with the existing menu-router test.

## 8. VERIFY — All RED tests fail for the right reason

- [x] 8.1 [core-api] VERIFY: `docker compose exec core-api pytest services/core-api/tests/test_yandex_maps_suggest.py services/core-api/tests/test_yandex_maps_geocode.py services/core-api/tests/test_rbac_matrix.py services/core-api/tests/test_main_includes_menu_routers.py -x --no-header -q` — confirm every new test fails with `ImportError`, `AttributeError`, `AssertionError`, or `404`/`403`. NO collection errors on pre-existing files. Any unexpected failure in unrelated tests MUST be triaged before closing the RED change.
