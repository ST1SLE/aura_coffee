## Why

The RED change `yandex-maps-proxy-red` has landed: 23 tests pin the contract for `GET /api/v1/maps/suggest` and `GET /api/v1/maps/geocode` (caching, precision floor, 3000ms timeout → 503, rate-limit WARNING, RBAC, INV-015). Those tests currently fail because the router, service, and schemas are absent. This change is the GREEN half of the pair — it implements `core_api.routers.yandex_maps`, `core_api.services.yandex_maps`, and `core_api.schemas.yandex_maps` until every RED test passes, and no more.

The motivation has not changed from the RED proposal: Phase 4 (Delivery, PDD §7.1 step 1) cannot proceed without a server-side Yandex.Maps proxy (PDD §8.3, INV-015). This change unblocks `POST /api/v1/orders` delivery validation (PDD §7.3 step 3), which will be a subsequent proposal.

**MVP phase:** Phase 4 (Delivery).

## What Changes

- Create `services/core-api/src/core_api/services/yandex_maps.py` — sync `YandexMapsClient` (timeout 3.0s) with two methods: `suggest(text, lang) -> list[Suggestion]` and `geocode(text) -> GeocodeResult | None`. The client owns the httpx.Client, normalization helpers, `PRECISION_ORDER`, and the error-classification logic (timeout/connection/5xx → raise `MapsUnavailableError`; 4xx → bubble up). No caching logic lives in the client — that belongs to the router, because the cache key + rate-limit counter depend on Redis which is a FastAPI dependency.
- Create `services/core-api/src/core_api/schemas/yandex_maps.py` — Pydantic models `Suggestion`, `GeocodeResult`, `MapsErrorReason`. Each enforces the exact key set asserted by the RED tests (no extras).
- Create `services/core-api/src/core_api/routers/yandex_maps.py` — two GET endpoints. Both read `settings.yandex_maps_api_key`, instantiate (or reuse a module-level) `YandexMapsClient`, acquire Redis via `Depends(get_redis)`, and orchestrate: cache-lookup → Yandex call → precision gate → cache-store → rate-limit increment + WARNING. On `MapsUnavailableError` return `JSONResponse(status_code=503, content={"reason": "maps_unavailable"})`.
- Register the two routes in `ROUTE_MATRIX` (`{CUSTOMER}`, not public) — `services/core-api/src/core_api/rbac_matrix.py`.
- Wire the router in `services/core-api/src/core_api/main.py` via `app.include_router(yandex_maps_router)` AND add the `maps` tag to `openapi_tags`.
- Update `services/core-api/tests/test_main_includes_menu_routers.py::test_main_include_router_call_count` from `== 9` to `== 10` so the smoke assertion tracks the new router.
- Promote the `yandex-maps-proxy` capability spec from the archived `-red` change into `openspec/specs/yandex-maps-proxy/spec.md` (archive of GREEN will do this automatically via `openspec archive`).

## Capabilities

### New Capabilities
- `yandex-maps-proxy`: Core-API proxy for Yandex.Maps Suggest and Geocoder APIs (same capability as defined in `yandex-maps-proxy-red`; promoted to `openspec/specs/` on archive of GREEN).

### Modified Capabilities
(none — the RED spec was a pure ADDED delta, so GREEN re-applies the same ADDED delta and the capability enters main specs at archive time.)

## Impact

- **Code:** New modules under `services/core-api/src/core_api/{services,routers,schemas}/yandex_maps.py`. Small edits to `main.py`, `rbac_matrix.py`, and the router-count smoke test.
- **Runtime:** Two new HTTP endpoints reachable by authenticated customers. Outbound HTTP to `suggest-maps.yandex.ru` and `geocode-maps.yandex.ru`. Redis keyspace gains two families: `yandex:geocode:*` (7 d TTL) and `yandex:rate:{YYYY-MM-DD}` (48 h TTL) + companion `:warned` flags.
- **Config:** No env var additions beyond what RED already declared (`YANDEX_MAPS_API_KEY`). In production, an unset key causes every call to produce 503 `maps_unavailable` (Yandex rejects the empty apikey with 4xx → bubble → 500, or the request fails upstream → 503). The router SHALL log a warning at startup if the key is empty.
- **Docs:** No PDD changes (§8.3/§8.4 already describe the behavior). The archived `design.md` captures the decisions.
- **Out of scope:** Haversine radius check (PDD §7.3 step 3); Suggest result caching (forbidden by PDD §8.3); client-side debouncing (owned by `[web-customer]`); switching geocoding providers; partial-rollout flags — the feature is toggled by presence/absence of `YANDEX_MAPS_API_KEY` effectively, which is sufficient.

## Non-Goals

- Integrating the proxy into order creation. That is a separate Phase-4 change.
- Adding retries or circuit breakers around Yandex. The PDD §8.3 fallback (Suggest-503 → plain input; Geocoder-503 → reject delivery) is the only failure strategy; client-side UX does the degradation.
- Caching Suggest responses. PDD §8.3 forbids this explicitly; RED asserts zero `yandex:suggest:*` keys.
- Building an administrative dashboard for daily-rate usage. Observability is a single WARNING log at 80 % — anything richer waits for real traffic.
- Migrating to async httpx. Core-API is fully synchronous; a partial async migration for two endpoints would fragment the codebase with no measurable latency win.
- Covering the real Yandex API in integration tests. `respx` in-process mocking is sufficient; a real sandbox test would need a separate prod-like key and would be rate-limited.
