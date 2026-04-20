## Context

**Affected modules:** `[core-api]`, `[redis]`.

Aura Coffee's delivery checkout (PDD §7.3) needs two external Yandex.Maps calls:
1. **Suggest API** during address entry (every keystroke, debounced on the client) — autocomplete UX only.
2. **Geocoder API** after the customer confirms an address — to pin coordinates for the downstream Haversine radius check (PDD §7.3 step 3).

Both calls MUST be made server-side so that `YANDEX_MAPS_API_KEY` (PDD §8.4) never leaves the backend (INV-015). The SPA therefore talks to `core-api`, which talks to Yandex. The web-customer already treats the backend as the source of truth for address validation; it only needs a JSON contract.

The cache budget is tight: Yandex.Maps free tier is 1000 Suggest + 1000 Geocode requests per day (PDD §8.3). Geocode results are stable over days (coordinates of an address do not move), so Redis caches them for 7 days. Suggest is context-dependent (user typing partial text) and MUST NOT be cached — caching would produce stale autocomplete for incomplete strings and still consume the same daily budget.

This change is the RED half of a two-step TDD pair. It SHALL NOT ship the router/service/schema modules; it only ships tests (all failing) and the minimal PREREQ scaffolding required for the tests to even collect (i.e. `settings.yandex_maps_api_key`, `.env.example` line, RBAC matrix entries referencing the not-yet-existing routes, and `respx` in dev extras).

## Goals / Non-Goals

**Goals:**
- Establish an executable contract (failing tests) for the `GET /api/v1/maps/suggest` and `GET /api/v1/maps/geocode` endpoints that the GREEN change MUST satisfy to pass.
- Pin every PDD §8.3 rule with at least one test: caching vs. no-caching, precision floor, 3000ms timeout → 503, HTTP 5xx → 503, connection error → 503, 80% rate-limit warning log.
- Keep the test suite runnable against `sqlite://` with no external network (via `respx`).
- Add the env var declaration (`YANDEX_MAPS_API_KEY`) without altering any runtime behavior.

**Non-Goals:**
- Shipping any request handler logic — that is GREEN.
- Defining the Haversine radius check (PDD §7.3 step 3) — separate change.
- Exposing the proxy to unauthenticated clients — routes are `CUSTOMER`-gated via `ROUTE_MATRIX`.
- Changing the production Yandex endpoint URLs — tests mock at the httpx transport level via `respx`, so the exact URL chosen in GREEN is not pinned by RED.

## Decisions

### D1 — Transport: sync `httpx.Client`, mocked by `respx`

`core-api` uses synchronous SQLAlchemy and synchronous request handlers throughout (see `services/core-api/src/core_api/routers/*`). The GREEN Yandex client MUST therefore use `httpx.Client` (sync), matching the `payment-worker/yukassa_client.py` pattern. `respx` (already used by `payment-worker/tests/test_yukassa_client.py`) transparently intercepts httpx requests in tests; `pytest-httpx` and raw `httpx.MockTransport` were rejected because the project already standardises on `respx` and mixing libraries would fracture the test infra.

**Alternatives considered:**
- `httpx.AsyncClient` + async endpoints — would force an async migration of just these two handlers, creating the sole async path in core-api. Rejected: inconsistency outweighs the negligible latency benefit (Yandex calls are the bottleneck either way, not the event loop).
- Real Yandex sandbox in CI — rate-limited, flaky, would need a separate test API key. Rejected in favor of `respx`.

### D2 — Timeout: `httpx.Timeout(3.0)` total

PDD §8.3 defines "timeout" as ≥ 3000ms. We SHALL configure httpx with a single `timeout=3.0` applied to the full request/response round-trip (connect + read), not per-phase. Tests assert that a simulated `respx.post(...).mock(side_effect=httpx.ReadTimeout)` (or `httpx.ConnectError`) maps to HTTP 503 `{"reason": "maps_unavailable"}`.

### D3 — Cache key: `sha256(text.strip().lower())`, TTL `604800` s

Normalization MUST be `text.strip().casefold()` (Python `str.casefold()` is locale-independent and handles Cyrillic correctly). Hash with SHA-256 and store as lowercase hex; the Redis key is `yandex:geocode:<hex>`. TTL is exactly 7 days. `json.dumps` the response body; no compression (payloads are ~1 KB, not worth zstd/lz4).

**Why hash at all?** Address strings can be arbitrarily long and contain characters that would need escaping. A fixed 64-char hex key is simpler to reason about and avoids any injection concerns.

**Alternatives considered:**
- Raw text as key — viable but requires escaping, length-limiting, and leaks the query into operational logs of Redis. Rejected.
- MD5/SHA-1 — collision-resistant enough for a cache key but adds zero value over SHA-256 which is already imported for other uses. Rejected for consistency.

### D4 — Precision enum and floor

PDD §7.3 step 2: reject when `precision < street`. Yandex Geocoder returns one of: `exact`, `number`, `near`, `range`, `street`, `other` (documented order, best-to-worst). We SHALL define an ordered tuple in `services/yandex_maps.py` (GREEN):

```python
PRECISION_ORDER = ("other", "near", "range", "street", "number", "exact")
MIN_PRECISION_INDEX = PRECISION_ORDER.index("street")
```

Reject when `PRECISION_ORDER.index(got) < MIN_PRECISION_INDEX` → `HTTPException(422, {"reason": "low_precision"})`.

Tests assert `precision="other"` → 422 and `precision="street"` / `"number"` / `"exact"` → 200.

### D5 — 503 fallback classification

Three error classes collapse to HTTP 503 `{"reason": "maps_unavailable"}`:
1. `httpx.TimeoutException` (includes `ReadTimeout`, `ConnectTimeout`).
2. `httpx.ConnectError`, `httpx.NetworkError`.
3. `httpx.HTTPStatusError` with `500 <= status_code < 600` (raised via `resp.raise_for_status()`).

Any `4xx` from Yandex is NOT 503 — it is a programming error on our side (bad API key, malformed query) and SHOULD surface as HTTP 500 so ops notice. Tests pin this: 4xx is not silently mapped to 503.

### D6 — Rate-limit tracking: Redis counter with daily rollover

Redis key: `yandex:rate:{YYYY-MM-DD}`, incremented on every successful Yandex call (both Suggest and Geocode — they share the 1000/day limit each in reality, but PDD §8.3 treats them as one observability channel). After increment, the service reads the counter; if it crosses 800 (80% of 1000) for the first time that day, it logs a WARNING via Python `logging`. The counter has a 48h TTL so it auto-expires.

**Why not per-endpoint counters?** Each Yandex API has its own 1000/day quota, but for an 80% warning signal the combined cadence is what operators want to see. Splitting into two counters adds complexity for no observability gain. GREEN MAY refine this if PDD §8.3 is later amended.

The RED test asserts: when the counter reaches exactly 800, a WARNING log record MUST be emitted containing the substring `"yandex"` and `"80%"`. No second warning on 801, 802, … — a "first crossing" flag lives in Redis too (`yandex:rate:{date}:warned`, TTL 48h).

### D7 — RBAC: `CUSTOMER` role, not public

Both `GET /api/v1/maps/suggest` and `GET /api/v1/maps/geocode` are called only from the authenticated checkout flow. We register them in `ROUTE_MATRIX` as `{CUSTOMER}`. They SHALL NOT be added to `PUBLIC_ROUTES`.

**Alternatives considered:**
- Public (no auth) — would waste the tight Yandex daily quota on unauthenticated hits; also misaligns with INV-002. Rejected.
- `ALL_ROLES` — admins/baristas/couriers have no reason to geocode; restricting to `CUSTOMER` narrows the attack surface. Accepted.

### D8 — No module-level env reads in tests

`services/core-api/tests/conftest.py` already pre-populates `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET_KEY`, `ENCRYPTION_KEY` before importing the app. `YANDEX_MAPS_API_KEY` MUST have a default of `""` in `Settings` so that `conftest.py` remains untouched; tests that exercise the service SHALL `monkeypatch.setenv("YANDEX_MAPS_API_KEY", "test-key")` locally and re-instantiate the service client. This keeps the PREREQ non-invasive.

## Risks / Trade-offs

- **[Risk]** Yandex API response shape drift — if Yandex changes the Geocoder JSON, RED-style tests hard-coded to the response shape will silently pass while prod fails. → **Mitigation:** Snapshot the response shape in a fixture file (GREEN); RED only pins our outward contract, not Yandex's shape. The parsing code in GREEN SHOULD be defensive (use `.get()` chains, default `"other"` for missing precision).
- **[Risk]** `respx` leaks between tests if not scoped with the decorator. → **Mitigation:** Use `@respx.mock` on each test (matches `test_yukassa_client.py` style), never the global router. Verified in RED by running the full core-api suite after the RED lands and confirming only the new tests fail.
- **[Risk]** Adding `httpx` as a runtime dep might pull in a conflicting version with another service's constraints. → **Mitigation:** Constraint is `httpx>=0.27` (same floor used by `payment-worker` and `sms-worker`). No transitive conflict expected — httpx has no upper-bound deps in the monorepo.
- **[Trade-off]** Returning 503 for both timeout and 5xx loses fidelity for operators (was it a slow Yandex or a down Yandex?). → We log the underlying exception at WARNING with a `yandex_failure_mode` field so the observability signal is not lost; the HTTP contract stays binary (503 or success) because the client-side fallback is identical.
- **[Trade-off]** Combined rate-limit counter (D6) may under-warn if Suggest dominates usage. → Acceptable for the MVP; a future proposal can split when usage data justifies it.

## Migration Plan

No schema migration (no DB impact). Deployment is:
1. Merge `yandex-maps-proxy-red` → all new tests fail as expected (ImportError / 404). CI is green because failing tests are allowed in RED changes per the project's TDD contract.
2. Merge `yandex-maps-proxy-green` → tests pass, endpoints go live.
3. Operator sets `YANDEX_MAPS_API_KEY` in the prod env before deploying GREEN. Empty key is a config error in prod (tests use `""` default); GREEN SHOULD guard with a startup warning when the key is empty AND the endpoints are registered.

**Rollback:** `git revert` of either change leaves the codebase runnable. Redis keys auto-expire (7d / 48h) — no cleanup needed.

## Open Questions

- None. The PDD is unambiguous on caching (Geocode yes, Suggest no), precision floor (street), timeout (3000ms), and fallback semantics (503 → client degrades). GREEN may refine the rate-limit split per D6 if real-world telemetry says so.
