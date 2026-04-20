## ADDED Requirements

<!-- Source: PDD §7.3 (Address Validation Chain), §8.3 (Yandex.Maps), §8.4 (Secrets table), INV-015 (secrets out of code). -->

### Requirement: Suggest proxy endpoint

The system SHALL expose `GET /api/v1/maps/suggest?text=<q>&lang=<ru_RU|en_US>` as an authenticated (CUSTOMER) proxy to the Yandex.Maps Suggest API. The endpoint SHALL NOT accept any parameter other than `text` and `lang`. Server-side debouncing SHALL NOT be applied — the server SHALL forward every accepted request to Yandex and return the result as-is (per PDD §8.3, Suggest is context-dependent and MUST NOT be cached). The response body SHALL be a JSON list of objects with exactly the keys `text`, `lat`, `lon`, `precision`.

#### Scenario: Valid query returns suggestions with coordinates

- **WHEN** an authenticated customer calls `GET /api/v1/maps/suggest?text=Москва,%20Тверская&lang=ru_RU` and Yandex returns two matches
- **THEN** the response is `200 OK` with body `[{"text": "Москва, Тверская улица, 1", "lat": 55.76, "lon": 37.62, "precision": "exact"}, ...]`
- **AND** `YANDEX_MAPS_API_KEY` appears in the outgoing request to Yandex but NEVER in the response to the client.

#### Scenario: Suggest results are not cached

- **WHEN** the same `text` is requested twice within a minute
- **THEN** Yandex SHALL be called twice (no Redis read/write involving the suggest path).
- **AND** no key matching the pattern `yandex:suggest:*` SHALL exist in Redis after either call.

#### Scenario: Missing required parameters → 422

- **WHEN** the request omits `text` (empty or absent)
- **THEN** the response is `422 Unprocessable Entity` (FastAPI default) and no outbound Yandex call is made.

#### Scenario: Unauthenticated access is denied

- **WHEN** a request arrives without a `Bearer` token of role `customer`
- **THEN** the response is `401` (no token) or `403` (non-customer role), consistent with `ROUTE_MATRIX` in `rbac_matrix.py`.

### Requirement: Geocode proxy endpoint with Redis cache

The system SHALL expose `GET /api/v1/maps/geocode?text=<address>` as an authenticated (CUSTOMER) proxy to the Yandex.Maps Geocoder API. Results SHALL be cached in Redis under key `yandex:geocode:<sha256(text.strip().casefold())>` with a TTL of exactly 604800 seconds (7 days), per PDD §8.3. The response body SHALL be a JSON object with keys `lat`, `lon`, `precision`, `canonical_text`.

#### Scenario: Fresh address triggers Yandex call and populates cache

- **WHEN** an authenticated customer calls `GET /api/v1/maps/geocode?text=Moscow,%20Red%20Square` for the first time
- **THEN** the response is `200 OK` with the coordinates and `precision` returned by Yandex
- **AND** Redis key `yandex:geocode:<sha256(...)>` is populated with the serialized response and a TTL of 604800 s.

#### Scenario: Second call for the same address is served from cache

- **WHEN** the same address is requested a second time within 7 days
- **THEN** Yandex SHALL NOT be called (0 outbound HTTP requests)
- **AND** the response bytes are identical to the first call.

#### Scenario: Low precision → 422

- **WHEN** Yandex returns a match with `precision` strictly below `street` (i.e. one of `other`, `near`, `range`)
- **THEN** the response is `422 Unprocessable Entity` with JSON body `{"reason": "low_precision"}`
- **AND** the cache SHALL NOT be populated for that query (only successful lookups are cached).

#### Scenario: High precision is accepted

- **WHEN** Yandex returns `precision ∈ {street, number, exact}`
- **THEN** the response is `200 OK` and the result is cached.

### Requirement: External failure fallback — HTTP 503

The Yandex external call SHALL have a total timeout of 3.0 seconds (connect + read). On any of: `httpx.TimeoutException`, `httpx.ConnectError`, `httpx.NetworkError`, or HTTP response with status `5xx`, both proxy endpoints SHALL return HTTP `503 Service Unavailable` with JSON body `{"reason": "maps_unavailable"}`. This enables the documented fallbacks from PDD §8.3 (Suggest-503 → client shows plain text input; Geocoder-503 on checkout → reject the delivery order).

#### Scenario: Yandex timeout → 503

- **WHEN** the Yandex call exceeds 3.0 seconds (simulated via `respx` side-effect `httpx.ReadTimeout`)
- **THEN** the response is `503` with body `{"reason": "maps_unavailable"}`
- **AND** the Redis cache is not populated.

#### Scenario: Yandex 500 → 503

- **WHEN** Yandex responds with HTTP `502 Bad Gateway`
- **THEN** the response is `503` with body `{"reason": "maps_unavailable"}`.

#### Scenario: Yandex connection error → 503

- **WHEN** the Yandex call fails with `httpx.ConnectError` (e.g. DNS failure)
- **THEN** the response is `503` with body `{"reason": "maps_unavailable"}`.

#### Scenario: Yandex 4xx is NOT silently downgraded

- **WHEN** Yandex responds with HTTP `403 Forbidden` (bad API key)
- **THEN** the response is `500 Internal Server Error`, NOT `503`. This preserves the operational signal that the API key is misconfigured and avoids the client falling through to the degraded-UX path for a programming error.

### Requirement: Daily rate-limit observability

On every successful Yandex call (from either proxy endpoint), the system SHALL increment a Redis counter keyed by the UTC date (`yandex:rate:{YYYY-MM-DD}`, 48 h TTL). When the counter first crosses 800 in a day (80 % of the 1000-request free tier documented in PDD §8.3), the system SHALL emit exactly one `WARNING`-level log record containing the substrings `"yandex"` and `"80%"`. Subsequent crossings on the same day SHALL NOT re-emit the warning.

#### Scenario: Counter increments on success

- **WHEN** the Suggest or Geocode proxy makes a successful Yandex call on `2026-05-01`
- **THEN** Redis key `yandex:rate:2026-05-01` is incremented by exactly 1 (TTL 48 h).

#### Scenario: First crossing of 80% emits one warning

- **WHEN** the counter goes from 799 to 800 in a single request
- **THEN** a `WARNING` log record is emitted containing the substrings `"yandex"` and `"80%"`.
- **AND** the 801st and 802nd requests on the same day SHALL NOT emit additional warnings.

#### Scenario: Cache hit does not increment the counter

- **WHEN** a Geocode request is served from the Redis cache
- **THEN** `yandex:rate:{date}` is NOT incremented (no Yandex call occurred).

### Requirement: API key secrecy (INV-015)

`YANDEX_MAPS_API_KEY` SHALL be loaded exclusively from `Settings` (via environment variables). It SHALL NOT be returned in any HTTP response body or error message. The proxy response SHALL NOT mirror Yandex error payloads verbatim; on upstream errors the response body SHALL be the fixed shape defined by the 503/500 requirements above.

#### Scenario: API key is never leaked in responses

- **WHEN** Yandex returns an error payload that happens to echo the API key (e.g., in a `url` field)
- **THEN** the proxy response body SHALL NOT contain the API-key value at any path (checked against `settings.yandex_maps_api_key` literal).
