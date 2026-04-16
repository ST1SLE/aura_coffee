## Context

Phase 3 adds Order & Payment. The `phase3-schema` change introduced `orders` and `order_items` tables, with `order_items.menu_item_id` and `order_items.size_option_id` stored as non-FK `BigInteger` references (PDD §7.7, INV-014). The `order-checkout` feature owns `GET /api/v1/orders/{order_id}` (single detail) in `routers/orders.py`.

The RED change here is a pure test-authoring change: it locks the contract for two new services and two new HTTP endpoints before any implementation exists. Per the Two-Change Model (AGENTS.md), this change MUST end with all new tests failing and the suite's unrelated tests still passing.

**Affected modules:** `[core-api]`.

## Goals / Non-Goals

**Goals:**
- Author failing tests that pin every bullet in PDD §7.7 for both `list_orders` and `repeat_order`.
- Cover auth (INV-002), per-user isolation (INV-013), and non-duplication of the existing single-order route.
- Provide reusable test helpers/fixtures for seeding historical orders with `order_items` where `menu_item_id` may be stale, archived, stop-listed, or missing.
- Tests MUST import target service modules/routes inside test bodies (or via `pytest.importorskip` at module scope) so that missing implementation produces a clean `ImportError` per test, not a collection failure.

**Non-Goals:**
- Service and router implementation (GREEN phase).
- Schema/DTO design beyond what the tests MUST assert (the RED tests MAY reference placeholder DTO names — but the DTO modules themselves do NOT need to exist yet; tests MAY also assert the DTO contract by constructing dicts/JSON responses and validating shape).
- Changes to `order_items` schema or migrations.
- Registering new routers in `main.py`.
- Frontend work.

## Decisions

### D1 — Two new capability specs, not a delta

**Decision:** Introduce `order-history` and `order-repeat` as NEW capabilities rather than modifying an existing one.
**Why:** No prior spec owns paginated customer order listing or the repeat chain. The phase3-schema specs cover models only. Splitting keeps scenarios focused.
**Alternative:** Fold into `order-schema` or into the order-checkout capability. Rejected — order-checkout is about creating an order from the cart; history and repeat are read + re-cart flows with distinct requirements.

### D2 — Tests MUST fail via `ImportError`, not via assertion

**Decision:** Each RED test SHALL import the under-test module inside its body. If the implementation file does not exist yet, the test fails at import — which is exactly the RED signal the GREEN phase must flip.
**Why:** Collection-level imports of nonexistent modules abort the entire test file, hiding which scenarios are unlocked. Body-local imports keep the RED report granular.
**Alternative:** Stub empty modules to satisfy imports, then assert behavior. Rejected — adds implementation scaffolding to a RED change, muddying the contract.

### D3 — Service tests SHALL run against the PostgreSQL `db_session` fixture

**Decision:** `list_orders` and `repeat_order` tests MUST use the existing `db_session` fixture (PostgreSQL + Alembic head) so JSONB columns (`modifiers_snapshot`, `delivery_address_snapshot`) round-trip correctly.
**Why:** SQLite lacks JSONB and native Enums; phase3-schema tests already follow this pattern. Fixture skip on SQLite is acceptable.
**Alternative:** Mock SQLAlchemy. Rejected — mocks would not catch the joined-load requirement or the ORM relationship for `order.items`.

### D4 — Router tests SHALL use `db_client` with the existing JWT fixtures

**Decision:** Reuse `db_client` (migrated_db_session + TestClient) and the `customer_headers` / `barista_headers` fixtures. For per-user isolation, the `customer_headers` JWT's `sub` SHALL be the seeded order's `user_id` (or a known-other `user_id`).
**Why:** Matches the existing router test style (`test_route_cart.py`). Avoids inventing a new auth harness.
**Caveat:** Current `customer_headers` fixture issues a random `sub`. Tests requiring a specific `sub` SHALL construct their own JWT inline (helper `_make_jwt` pattern is already in `conftest.py`), and tests SHALL seed a matching `users` row to satisfy the `orders.user_id → users.id` FK (phase3-schema).

### D5 — `repeat_order` SHALL delegate cart writes to `CartService.add_item`

**Decision:** RED tests SHALL assert that each reconstructed item is pushed through `CartService.add_item(CartItemCreate(...))` (monkeypatch/spy on the method). No direct Redis writes in the new service.
**Why:** `CartService` already enforces INV-006 (stop-list), quantity caps, and line-id merging. Re-implementing these rules in `repeat_order` would duplicate invariants.
**Alternative:** Bypass CartService and write to Redis directly. Rejected — re-introduces validation duplication and breaks INV-006 guarantees.

### D6 — Notification shape

**Decision:** RED tests SHALL fix the shape of entries in `RepeatOrderResult.skipped`: each entry is a dict (or Pydantic model) with `reason: str` (one of `menu_item_unavailable`, `menu_item_archived`, `menu_item_deleted`, `size_unavailable`, `modifier_unavailable`) and `message_ru: str` matching the exact wording from PDD §7.7 (`"Размер {label} для {name} недоступен"`, `"{name} сейчас недоступен"`, `"{name} больше не в меню"`, `"Позиция больше не в меню"`). Tests assert the `reason` code AND the rendered Russian message.
**Why:** The PDD wording is normative; the `reason` code is machine-readable for future i18n and analytics.

### D7 — Pagination contract

**Decision:** `list_orders` tests SHALL assert:
- `page` defaults to 1, `per_page` defaults to 20, `per_page` max = 50 (422 on exceed at the router layer; service layer MAY silently clamp OR validate — RED tests pin the **router-layer 422** on `per_page > 50`).
- `total_count` is the full count ignoring page/per_page.
- Empty-result request returns `total_count=0` and `orders=[]` with HTTP 200 (not 404).
- Order is `created_at DESC`.

### D8 — State machine touchpoints

**Decision:** `list_orders` is read-only — no state transitions. `repeat_order` writes to the cart only; it does NOT create a new `Order` row. No PDD §6.1 transition is taken by this feature. Tests SHALL assert that NO `Order` row is inserted during a repeat (DB count unchanged except for fixture seeding).

## Risks / Trade-offs

- **[Risk]** Stale `menu_item_id` references may collide with newly inserted menu items that reused the deleted id. → **Mitigation:** The data contract uses surrogate ids, not phone-number-style identifiers; test seeds use distinct integer ids for deleted-vs-current menu items.
- **[Risk]** Router tests coupled to `customer_headers` random-`sub` might accidentally pass cross-user leakage tests. → **Mitigation:** Tests that check isolation SHALL build explicit JWTs with a known `sub` that matches (or intentionally mismatches) the seeded `user_id`.
- **[Risk]** Adding tests that import a module-that-does-not-exist yet could poison `pytest` collection if done at module scope. → **Mitigation:** D2 — all target-module imports live inside test bodies.
- **[Trade-off]** Seeding a full historical order with JSONB modifier snapshots requires more fixture code than Menu fixtures. Accepted: this fixture is reusable in the GREEN phase and future order features.

## Atomicity Analysis

Not applicable. This feature does not touch payments, loyalty, or promocodes. `repeat_order` only reads from Postgres and writes to Redis via `CartService`. Per D5 and D8, there is no DB transaction spanning multiple financial mutations. INV-004 is not engaged.

## 152-FZ Compliance

`list_orders` returns per-user order history. Orders reference users by opaque UUID (INV-013 preserved). The response DTO SHALL NOT embed PII beyond what the existing single-order detail route already exposes (`delivery_address_snapshot` is JSONB and already part of phase3-schema). RED tests SHALL NOT assert new PII fields — they assert the same shape as the existing single-order response, extended with pagination metadata.

## Migration Plan

No schema change. No data migration.

## Open Questions

- None known. The PDD §7.7 text and the phase3-schema model shape fully specify the contract. If the GREEN phase uncovers ambiguity in DTO naming (e.g. `OrderListResponse` vs `OrderHistoryResponse`), the GREEN change MAY adjust names — RED tests SHOULD use the `OrderListResponse` / `RepeatOrderResult` names from the task description so the GREEN phase can implement exactly those symbols.
