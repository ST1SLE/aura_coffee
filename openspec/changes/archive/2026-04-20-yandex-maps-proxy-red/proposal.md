## Why

Phase 4 (Delivery, PDD §7.1 item 5) requires customers to enter a delivery address with server-side validation (PDD §7.3). The current codebase has no endpoint for address autocomplete or geocoding — the web-customer would have to call Yandex.Maps directly, which would leak the API key into the SPA bundle and violate **INV-015** (secrets exclusively in environment variables). PDD §8.3 mandates that Yandex.Maps requests be proxied through Core API so the `YANDEX_MAPS_API_KEY` never leaves the server. Without this proxy, the delivery checkout flow cannot move past data entry.

This is the RED half of a two-change TDD pair (`yandex-maps-proxy-red` → `yandex-maps-proxy-green`). It ships only failing tests and PREREQ scaffolding (settings attribute, env var declaration); implementation lands in `-green`.

**MVP phase:** Phase 4 (Delivery) — PDD §7.1 step 1 ("Implement Yandex.Maps integration: autocomplete (Suggest API, proxied via Core API), server-side geocoding (Geocoder API)").

## What Changes

- Introduce a new `yandex-maps-proxy` capability covering two endpoints on `core-api`:
  - `GET /api/v1/maps/suggest?text=<q>&lang=<ru_RU|en_US>` — address autocomplete (uncached per PDD §8.3).
  - `GET /api/v1/maps/geocode?text=<address>` — address → coordinates (cached in Redis, TTL 7 days per PDD §8.3).
- Declare `YANDEX_MAPS_API_KEY` in `services/core-api/src/core_api/settings.py` and `.env.example`. PDD §8.4 already lists this variable; this change wires it into code (PREREQ).
- Add failing pytest cases covering, per PDD §8.3: successful Suggest + Geocode responses, low-precision Geocode rejection (HTTP 422 `{"reason":"low_precision"}`), Redis cache hit/idempotency for Geocode, timeout/5xx/connection-error → HTTP 503 `{"reason":"maps_unavailable"}`, and daily rate-limit 80% warning log (§8.3 "80% порог").
- Extend `rbac_matrix.py` with the two new routes (CUSTOMER role). The routes are not "public" — only authenticated customers drive the delivery checkout that calls them.
- No implementation of routers/services/schemas in this change — those come in `yandex-maps-proxy-green`. PREREQ-only code (settings field + env var) ships here so the tests can even import `core_api.settings` without an env-var crash.

## Capabilities

### New Capabilities
- `yandex-maps-proxy`: Core-API proxy for Yandex.Maps Suggest and Geocoder APIs, with Redis caching of Geocode results, precision gating, external-failure fallback (503), and daily-rate-limit observability. Keeps `YANDEX_MAPS_API_KEY` server-side (INV-015).

### Modified Capabilities
(none — no existing spec under `openspec/specs/` owns Yandex.Maps behavior; PDD §8.3 is the prior art but not yet captured as an OpenSpec spec)

## Impact

- **Code:** New test files `services/core-api/tests/test_yandex_maps_suggest.py`, `services/core-api/tests/test_yandex_maps_geocode.py`. Minimal PREREQ edits to `services/core-api/src/core_api/settings.py` (add `yandex_maps_api_key: str = ""`). RBAC matrix update in `services/core-api/src/core_api/rbac_matrix.py` so the new routes resolve to `{CUSTOMER}` once the router is added in GREEN (routes are referenced in tests; matrix lines are inert without the router).
- **Config:** `.env.example` gains a `YANDEX_MAPS_API_KEY=` placeholder under a new `# Yandex Maps` block.
- **Dependencies:** Add `respx` to `services/core-api/pyproject.toml` dev extras (already used by payment-worker tests; this change reuses the same mocking library). `httpx` is promoted from dev-only to a runtime dependency of core-api, because the GREEN implementation will call Yandex over HTTP from request handlers.
- **Runtime:** No new endpoints exposed yet — tests fail because the router does not exist. Zero production impact until `-green` merges.
- **Out of scope (covered by `-green`):** actual router/service/schema modules, cache wiring, rate-limit counter, timeout handling, `main.py` `include_router(...)` call.

## Non-Goals

- **Integrating the proxy into `POST /api/v1/orders` delivery validation.** That is PDD §7.3 step 3 (radius check via Haversine) — a separate change once the proxy exists.
- **Caching Suggest results.** PDD §8.3 explicitly forbids this (contextually dependent). The test suite actively asserts that Suggest does NOT touch Redis.
- **Client-side debouncing of the Suggest endpoint.** That belongs to `[web-customer]`, not `[core-api]`.
- **Switching to Yandex Places API or any non-Yandex provider.** PDD §8.3 pins Yandex.Maps as the sole geocoder. Revisit only if PDD changes.
- **Automatic fallback from Geocoder to another provider when 503s happen.** PDD §8.3 explicitly mandates rejecting the delivery order with a clear message — no silent degradation of radius checks.
- **Mocking Yandex at integration level (real HTTP test server).** `respx` in-process mocking is sufficient; a real fake server would duplicate infra with no additional coverage.
