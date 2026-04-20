## Context

**Affected modules:** `[core-api]`, `[redis]`.

The RED change `yandex-maps-proxy-red` already landed the contract: 23 failing tests across `test_yandex_maps_suggest.py`, `test_yandex_maps_geocode.py`, `test_rbac_matrix.py::TestYandexMapsRbac`, and `test_main_includes_maps_router.py`, plus PREREQ scaffolding (`settings.yandex_maps_api_key`, `.env.example`, `httpx` promoted to main deps, `respx` in dev extras). This GREEN change implements the three missing modules — service, schemas, router — and the two wiring edits (RBAC matrix + `main.py` include_router) so that every RED test passes, and nothing else.

The design decisions were fully settled in the archived RED change's `design.md` (D1–D8). GREEN is the mechanical realization of those decisions. This document records only the GREEN-specific choices: module layout, dependency shape between the service and the router, and the exact points where caching vs. rate-limit counting interleave.

## Goals / Non-Goals

**Goals:**
- Implement `core_api.services.yandex_maps`, `core_api.schemas.yandex_maps`, and `core_api.routers.yandex_maps` so that all 23 RED tests pass.
- Keep the layering clean: the service owns Yandex HTTP + parsing + error classification; the router owns caching, rate-limit counter, and HTTP response shaping. No cross-dependency on Redis inside the service.
- Promote the `yandex-maps-proxy` capability into `openspec/specs/` on archive (same ADDED delta as RED).

**Non-Goals:**
- Any code outside the modules listed above and the two wiring files.
- Haversine radius check (PDD §7.3 step 3) — separate Phase-4 change.
- Async migration of core-api.
- Partial-rollout toggles — presence/absence of `YANDEX_MAPS_API_KEY` is the de facto switch.

## Decisions

### G1 — Module layout (three files, one wire-up)

```
core_api/
  services/yandex_maps.py      # YandexMapsClient + MapsUnavailableError + PRECISION_ORDER
  schemas/yandex_maps.py       # Suggestion, GeocodeResult, MapsErrorReason
  routers/yandex_maps.py       # GET /api/v1/maps/{suggest,geocode} — cache + rate-limit
main.py                        # app.include_router + "maps" tag
rbac_matrix.py                 # two ROUTE_MATRIX entries
```

The split mirrors `cart` (service holds business logic + Redis-free helpers; router wires Redis via `Depends(get_redis)`) rather than `orders` (which couples service to a SQLA session because orders are persisted). Yandex has no DB footprint, so the lighter cart-style split applies.

### G2 — `YandexMapsClient` owns httpx, not Redis

The client constructs a module-level `httpx.Client(timeout=httpx.Timeout(3.0))` lazily on first use (so tests that never import the router don't pay the socket init cost). Its public surface is exactly two methods:

```python
def suggest(self, text: str, lang: str) -> list[Suggestion]: ...
def geocode(self, text: str) -> GeocodeResult | None: ...
```

Both raise `MapsUnavailableError` (a subclass of `RuntimeError`) on any condition listed in RED's D5: `httpx.TimeoutException`, `httpx.ConnectError`, `httpx.NetworkError`, or 5xx. Yandex 4xx bubbles as `httpx.HTTPStatusError` (not caught) → FastAPI converts to 500. The client owns `PRECISION_ORDER` and the `_is_low_precision(precision: str) -> bool` helper; the router only asks yes/no questions.

**Alternatives considered:**
- Exposing httpx errors directly to the router — forces the router to know Yandex-specific failure modes. Rejected: the boundary is cleaner if the service translates them into one domain-level exception.
- Passing the Redis client into the service — couples two orthogonal concerns (HTTP transport + caching policy) and makes the service harder to unit-test. Rejected: the router is the integration point.

### G3 — Router orchestrates cache + counter + response shape

The router holds the Redis-touching logic because the cache key derivation, the daily counter, and the 80% warning flag all require `Depends(get_redis)`. Control flow for `/geocode`:

```
1. compute cache_key = f"yandex:geocode:{sha256(text.strip().casefold()).hexdigest()}"
2. cached = redis.get(cache_key); if cached → return json.loads(cached) (no counter bump)
3. try: result = client.geocode(text) except MapsUnavailableError → JSONResponse(503, {"reason": "maps_unavailable"})
4. if result is None or precision < "street" → raise HTTPException(422, {"reason": "low_precision"})
5. redis.setex(cache_key, 604800, json.dumps(result.model_dump()))
6. _increment_rate_counter(redis, logger)
7. return result
```

For `/suggest` the flow is simpler (no cache, no 422 precision check — Suggest items are raw autocomplete): try/except Yandex → rate-limit bump → return list. The 422-on-missing-`text` comes for free from FastAPI's `Query(...)` validation.

### G4 — Rate-limit counter helper is a router-local function

A small `_bump_daily_rate(redis: Redis, log: Logger) -> None` function lives in `routers/yandex_maps.py` (not a separate module — 20 lines of Redis plumbing, not worth extraction). Logic:

```python
date = datetime.utcnow().strftime("%Y-%m-%d")
key = f"yandex:rate:{date}"
count = redis.incr(key)
if count == 1:
    redis.expire(key, 172800)  # 48 h TTL on first write today
if count >= 800:
    warned_key = f"yandex:rate:{date}:warned"
    if redis.set(warned_key, "1", nx=True, ex=172800):
        log.warning("yandex daily quota crossed 80%% (%d/1000 on %s)", count, date)
```

`SET NX EX` is atomic, so two concurrent crossings never double-emit.

**Alternatives considered:**
- Python-side "first crossing" flag — not durable across worker restarts. Rejected.
- Read-then-set — race condition. Rejected.
- Separate counters per endpoint — overkill per RED D6. Rejected.

### G5 — `include_router` call-count smoke test goes from 9 to 10

`tests/test_main_includes_menu_routers.py::test_main_include_router_call_count` asserts the exact number of `include_router` calls wired in `main.py`. Adding one router means bumping `== 9` to `== 10`. This is a mechanical update — the only reason the RED change didn't do it is that the RED didn't add the include_router line.

### G6 — Module-level client with lazy init, shared across requests

```python
_CLIENT: YandexMapsClient | None = None

def _get_client() -> YandexMapsClient:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = YandexMapsClient(api_key=settings.yandex_maps_api_key, timeout=3.0)
    return _CLIENT
```

httpx.Client is thread-safe for concurrent `GET`s; reusing the underlying connection pool across requests avoids the per-request TCP handshake to `*.yandex.ru` and matches the `payment-worker/yukassa_client.py` pattern. Tests that need to assert `client.timeout` import the client directly via `_get_client()` or reconstruct one — both are fine.

**Alternative considered:** Instantiate per request. Rejected — adds ~30 ms of connection setup to every geocode, wiping the point of caching.

### G7 — Capability promotion on archive

GREEN ships the same `ADDED Requirements` delta as RED. On `openspec archive yandex-maps-proxy-green`, the CLI promotes `yandex-maps-proxy` from `specs/yandex-maps-proxy/spec.md` inside the change into `openspec/specs/yandex-maps-proxy/spec.md` at the repo root. No `MODIFIED` or `REMOVED` sections — this is a pure new capability.

## Risks / Trade-offs

- **[Risk]** RED tests pin httpx client `timeout.connect` and `.read` as `== 3.0`, not `<= 3.0`. → **Mitigation:** construct the client with `httpx.Timeout(3.0)` (scalar form sets every phase to 3.0), not `httpx.Timeout(connect=3.0, read=3.0)` — identical result but the scalar form is idiomatic.
- **[Risk]** `json.dumps(GeocodeResult)` order differs from first-call output, breaking RED's "response bytes byte-identical" assertion. → **Mitigation:** serialize through `model_dump_json()` (Pydantic canonical order) on both the cache-write path and the cache-hit path. Return the cached string verbatim via `Response(content=cached, media_type="application/json")` — don't round-trip through `json.loads`+`JSONResponse` (that may re-order keys).
- **[Risk]** The module-level `_CLIENT` captures `settings.yandex_maps_api_key` at first call; tests that `monkeypatch` after the first call see stale key. → **Mitigation:** the RED autouse fixture patches both `os.environ` and `core_api.settings.settings.yandex_maps_api_key` at module scope before any endpoint call. For safety, `YandexMapsClient` re-reads `settings.yandex_maps_api_key` on every `suggest`/`geocode` call (it's just a `str` lookup; effectively free). This lets tests monkeypatch between calls.
- **[Trade-off]** Storing `canonical_text` in the cached payload means cache hits are identical to fresh calls — good. But if Yandex ever changes canonical formatting, stale cache values persist for up to 7 days. Acceptable for the MVP; a schema version prefix (`yandex:geocode:v1:<hex>`) could be added later without a migration (old keys just expire).

## Migration Plan

1. Merge GREEN. CI runs the full suite; the 23 RED tests flip from fail to pass. Baseline failures (19 pre-existing) remain unchanged.
2. Set `YANDEX_MAPS_API_KEY` in the prod env before the next deploy. With an empty key, Yandex returns 4xx, which bubbles as 500 — ops will notice immediately. The router logs a `WARNING` at startup if the key is empty (G6 lazy init means the warning is emitted on first use, not import).
3. Merge the follow-up `orders-delivery-validation` change that consumes `/api/v1/maps/geocode` from `POST /api/v1/orders`. That change is out of scope here.

**Rollback:** `git revert` of GREEN leaves the router uninstalled and all RED tests failing again (which is the intended RED state — CI allows it for the RED half of a pair). Redis keys auto-expire in 7 d / 48 h.

## Open Questions

- None. Every contract point is pinned by an RED test; GREEN exists solely to make them green.
