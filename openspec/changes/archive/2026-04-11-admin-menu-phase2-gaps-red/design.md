## Context

This is the RED half of a RED/GREEN pair for adding a menu item → modifier attach endpoint to the admin API. It contains only failing tests. The comprehensive technical design — decisions, alternatives, risks — lives in `admin-menu-phase2-gaps-green/design.md`; this file only documents what the RED tests need in order to be meaningful failing tests.

**Affected modules:** `[core-api]` only (tests). No `[web-admin]`, no `[shared]`, no `[database]`.

**Current state of the addressed endpoint:** nonexistent. `routers/menu_admin.py` has no `PUT /items/{item_id}/modifiers` route, `MenuAdminService` has no `set_item_modifiers` method, `schemas/menu.py` has no `MenuItemModifierSet` model, and `rbac_matrix.py` has no entry for the path. Every test in this RED change SHALL fail for one of these reasons when run against `main`.

## Goals / Non-Goals

**Goals:**
- Pin down the exact contract of the new endpoint (method, path, request shape, response shape, status codes) as executable tests before any production code is written.
- Every test MUST run against SQLite without skip. Seed data through the admin API, not raw SQL.
- Every test MUST fail cleanly against `main` — either as HTTP 404/405 from the missing route, or as a clear AssertionError on response shape, never as a flaky environment error.

**Non-Goals:**
- No production code changes.
- No fixture additions — reuse `client`, `admin_headers`, `barista_headers` from `conftest.py`.
- No tests for the frontend `ModifiersPicker` or the category `sort_order` input — the GREEN change covers those via IMPL/TEST tasks.

## Decisions

### D-1. One test function, multiple sub-assertions

The RED phase SHALL add a single new test function `test_admin_set_item_modifiers` to `services/core-api/tests/test_menu_admin.py`. All eight scenarios live in that one function, sharing a seeded set of modifiers and one menu item. Rationale: mirrors the precedent set by `test_admin_items_list_filters_by_category` in the `fix-admin-items-category-filter-red` change; avoids duplicated seeding and keeps the RED delta small.

### D-2. Seeding via admin API

The test SHALL seed one category, one menu item in that category, and at least three modifiers by calling `POST /api/v1/admin/menu/categories`, `POST /api/v1/admin/menu/items`, and `POST /api/v1/admin/menu/modifiers` with `admin_headers`. No direct DB writes. Rationale: project convention (per `fix-admin-items-category-filter-red`) — tests that use raw SQL diverge from SQLite-safe execution.

### D-3. Expected RED state

When run against `main`, the test SHALL fail on the first scenario assertion because `PUT /api/v1/admin/menu/items/{item_id}/modifiers` returns HTTP 405 (Method Not Allowed) or 404, never 200. The assertion message SHALL make this clear. No `pytest.skip`, no `xfail` — a straight failing test.

## Risks / Trade-offs

- **[Risk] Test depends on the GREEN change landing immediately.** If this RED change is merged alone, CI turns red on `main`. → **Mitigation:** the two changes MUST be applied back-to-back. Stated in the proposal's Non-Goals.

- **[Trade-off] Single test function vs one-per-scenario.** One function is less granular but matches precedent and minimizes seeding overhead. If a scenario fails and a later scenario also would have failed, the developer only sees the first failure — acceptable, since fixing them in order is the intended workflow.
