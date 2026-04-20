## Context

Phase 3 (`order-checkout`, `order-history`, `order-actions`) landed the customer-facing order surface. Staff (admin + barista) currently reach orders only through `PATCH /api/v1/orders/{order_id}/status` and `POST /api/v1/orders/{order_id}/cancel` (order-actions) — there is no read API they can use to discover which orders are in flight. Without it, the Phase 6 admin UI cannot be built.

The customer routes in `routers/orders.py` and `routers/order_history.py` enforce `Order.user_id == current_user.user_id`. Staff cannot reuse them — either we branch on role inside customer code (leaking INV-010) or we expose staff identity to the ownership filter (wrong). The existing PDD §5.4 partial index `orders (status) WHERE status NOT IN (COMPLETED, CANCELLED)` and the `idx_orders_status_type_created` plan make a staff-only feed cheap to query directly.

This RED change is a pure test-authoring change: it locks the HTTP contract and the service API for `admin-orders-api` before any implementation exists. Per AGENTS.md Two-Change Model, the change MUST end with every new test failing and every pre-existing test still passing.

**Affected modules:** `[core-api]`.

## Goals / Non-Goals

**Goals:**
- Author failing tests that pin every bullet of the `admin-orders-api` capability against PDD §4.5, §5.4, §6.1, INV-010, and INV-013.
- Lock the query semantics: default `status="active"` (NOT IN COMPLETED/CANCELLED), explicit `status` values from `OrderStatus`, optional `type` filter, `page ≥ 1`, `per_page ≤ 100`.
- Lock the ordering semantics: `created_at DESC` for active statuses; `updated_at DESC` for finalized statuses (COMPLETED, CANCELLED).
- Lock the RBAC matrix: `GET /api/v1/admin/orders` and `GET /api/v1/admin/orders/{order_id}` SHALL be allowed for `{ADMIN, BARISTA}` and denied for `{CUSTOMER, COURIER}`.
- Keep the RED signal clean: target-module imports SHALL live inside test bodies or `pytest.importorskip` blocks so a missing implementation fails per test, not at collection.
- Reuse existing `OrderListResponse` / `OrderResponse` (from `schemas.order_history`) — no new DTOs in RED or GREEN.

**Non-Goals:**
- Writing any service function, router, or `main.py` wiring (GREEN phase).
- Modifying the customer-scoped `/api/v1/orders/*` routes — they remain strictly `user_id`-filtered.
- Adding PATCH/POST admin endpoints (cancel, status transitions) — already owned by `order-actions`.
- Introducing new Pydantic schemas or ORM fields.
- Adding migrations or indexes — PDD §5.4 already lists the partial index.
- Courier and customer feeds.
- Frontend work.

## Decisions

### D1 — New capability `admin-orders-api`, not a delta to `order-history`

**Decision:** Introduce `admin-orders-api` as a NEW capability.
**Why:** `order-history` is customer-scoped by construction (`list_orders(user_id=...)`). The staff feed has a different filter set (no `user_id`), different ordering (mixed `created_at`/`updated_at`), a different RBAC row, and a different `per_page` cap. Folding these under `order-history` would require MODIFIED markers on every requirement in that spec. A fresh capability keeps the two surfaces separately reviewable.
**Alternative:** MODIFIED delta on `order-history`. Rejected — the single overlap (the existing `list_orders` function) is intentional (staff SHALL NOT reuse it) and the overlap is narrow.

### D2 — Staff helpers live next to `list_orders` in `services/order_history.py`

**Decision:** `list_orders_for_staff` and `get_order_for_staff` SHALL be added to `core_api.services.order_history`, alongside the existing `list_orders`. The RED tests import them from that module (inside test bodies).
**Why:** They share the `Order`/`OrderItem` ORM wiring, the `OrderListResponse` DTO, and the pagination math with `list_orders`. A sibling file would duplicate imports for no architectural gain. Naming the functions with the `_for_staff` suffix flags the customer-scope/staff-scope split at the call site.
**Alternative:** New file `services/admin_orders.py`. Rejected — adds a module without removing shared code; module boundary sits at the router, not the service.

### D3 — Tests MUST fail via `ImportError`, not via collection failure

**Decision:** Every RED test SHALL import `list_orders_for_staff` / `get_order_for_staff` inside the test body (not at module top-level). Router tests SHALL probe `app.routes` rather than hitting a non-existent path.
**Why:** Module-level imports of missing symbols abort the whole test file and hide which scenarios are unlocked. Body-local imports keep the RED report granular — GREEN flips each test individually.
**Alternative:** Stub empty functions to satisfy imports. Rejected — adds implementation scaffolding to a RED change, blurring the contract.

### D4 — Router tests reuse `db_client` + `admin_headers` / `barista_headers` / `customer_headers` / `courier_headers`

**Decision:** Use the existing `db_client` fixture (migrated Postgres + `TestClient`) and the role-keyed header fixtures from `tests/conftest.py` and the `db_client` pattern from `test_route_order_history.py`. For isolation proofs, tests SHALL seed orders under multiple users (via `_factories.orders.make_user` + `seed_n_orders_for_user`) and hit the endpoint as admin/barista, asserting they see both users' orders.
**Why:** Matches the existing router-test style; no new auth harness. The admin feed does NOT filter by `sub` so random-`sub` JWTs are fine.

### D5 — "active" meta-status SHALL be wired to the existing partial index

**Decision:** RED tests SHALL assert that `status="active"` corresponds to `status NOT IN (COMPLETED, CANCELLED)`, matching the PDD §5.4 partial index `orders (status) WHERE status NOT IN (COMPLETED, CANCELLED)`. The tests SHALL NOT assert the EXPLAIN plan, but they SHALL pin the semantics — GREEN is then free to use the ORM `not_in_` clause that the planner maps to the index.
**Why:** The index is the reason the admin feed is cheap. Locking the semantics at the service boundary prevents GREEN from sliding into a wider filter (e.g. "status != CANCELLED") that would skip the index.

### D6 — Ordering: `created_at DESC` for active, `updated_at DESC` for finalized

**Decision:** The RED tests SHALL assert:
- When `status="active"` (default) OR an active concrete status — rows SHALL be ordered `created_at DESC`.
- When `status` is COMPLETED or CANCELLED — rows SHALL be ordered `updated_at DESC`.
**Why:** An active-orders feed is an event stream (newest arrivals first). A finalized feed is a history audit (most recently touched first, e.g. recently cancelled). Mixing the two under one ordering hides just-cancelled orders at the bottom of the list.
**Alternative:** Single `created_at DESC` for every status. Rejected — cancellations from last week would outrank a cancellation two minutes ago.

### D7 — Pagination contract: default 20, max 100

**Decision:** `page: int = Query(1, ge=1)`, `per_page: int = Query(20, ge=1, le=100)`. `per_page=101` SHALL return HTTP 422 at the router layer. `total_count` SHALL ignore `page`/`per_page`.
**Why:** The admin UI often scrolls a kitchen feed; raising the cap from the customer-scope 50 to 100 reduces pagination chatter without opening the door to full-table dumps.

### D8 — RBAC matrix row is part of the RED contract

**Decision:** RED tests SHALL assert `("GET", "/api/v1/admin/orders")` and `("GET", "/api/v1/admin/orders/{order_id}")` are present in `ROUTE_MATRIX` with role set `{ADMIN, BARISTA}`, and ABSENT from `PUBLIC_ROUTES`.
**Why:** INV-010 lives in the matrix; locking the row at the RED layer catches accidental role widening (e.g. allowing COURIER) during GREEN.

### D9 — Reuse `OrderListResponse` / `OrderResponse` from `schemas.order_history`

**Decision:** The admin endpoints SHALL return the existing DTOs from `core_api.schemas.order_history` — `OrderListResponse` with `orders`, `total_count`, `page`, `per_page`, and `OrderResponse` with `user_id` populated.
**Why:** Staff see the same core order data that the customer history exposes; the `user_id` field is already in the customer DTO and is exactly what the admin UI needs to group orders by customer. No bespoke admin DTO is necessary.
**Caveat:** `schemas.order.OrderResponse` (used by `routers/orders.py::get_order`) omits `user_id`. The admin detail route SHALL NOT use that variant — it SHALL return the `schemas.order_history.OrderResponse` variant. Tests assert this by checking the `user_id` key in the detail response.

## Risks / Trade-offs

- **[Risk]** Staff inadvertently rely on the customer `OrderResponse` shape via code reuse, losing `user_id`. → **Mitigation:** D9 pins the schema source. The RED detail test asserts `user_id` is present in the response body.
- **[Risk]** The ordering split (created_at vs updated_at) makes the ORM query two code paths. → **Mitigation:** D6 is locked in tests, so GREEN cannot silently collapse to one path without breaking tests.
- **[Risk]** `Order.updated_at` might not exist in the model. → **Mitigation:** The RED tests import and set `updated_at` explicitly on seeded Orders; if the column is missing, tests fail clearly, which is a signal for GREEN to either migrate or fall back to `created_at` (decision deferred to GREEN design).
- **[Risk]** Tests coupled to random-`sub` JWTs might miss isolation-violation regressions. → **Mitigation:** The admin feed is not isolation-filtered, so this risk applies inversely: tests SHALL seed orders under multiple users and assert ALL are visible.
- **[Trade-off]** Locking `per_page ≤ 100` in RED forbids future expansion without a spec delta. Accepted — spec deltas are cheap; silent widening is not.

## 152-FZ Compliance

Staff access to customer order data is a legitimate business purpose under 152-FZ (fulfilment, dispute resolution, kitchen ops). Access is gated by ADMIN/BARISTA role (INV-010) and logged at the transport layer via standard request logging. The admin endpoints SHALL return the same `OrderResponse` shape that the customer already sees for their own orders — no new PII surface. `user_id` is an opaque UUID (INV-013) and does not expose phone/email without a separate profile lookup (not in scope here).

## Migration Plan

No schema change, no data migration. The partial index from PDD §5.4 already exists.

## Open Questions

- **Naming of the meta-status string**: `"active"` vs `"in_progress"` vs `"open"`. The RED tests will pin `"active"` per the task spec; GREEN MAY propose a change-of-name only via a spec delta.
- **Behaviour when both `type` and `status` filter are set**: the RED tests assert AND semantics (both apply). Confirmed implicitly by the composite `(status, type, created_at DESC)` query plan.
- **`Order.updated_at` availability**: if the column is absent, the ordering decision (D6) for finalized statuses is ambiguous. Tests seed the column; a missing column surfaces as a fixture failure, which GREEN resolves. No blocker for RED.
