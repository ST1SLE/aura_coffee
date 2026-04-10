## Context

Affected modules: **[core-api]**.

See `fix-admin-items-category-filter-green/design.md` for the full technical design (router/service wiring, validation strategy, 404 vs empty list decision). This document focuses on the test-phase specifics.

The existing list test in `services/core-api/tests/test_menu_admin.py:258-276` seeds three items in one category and asserts `len >= 3`. That assertion is too loose to catch a filter that silently returns everything — it would pass even if the filter were broken in the way it currently is. We need explicit positive and negative assertions.

References: PDD §5.2 (Menu tables), §7.1 Phase 6, INV-002 / INV-010 (unchanged).

## Goals / Non-Goals

**Goals:**
- Produce a concrete, failing test suite that locks in the new contract for `GET /admin/menu/items` with `category_id`.
- Tests MUST run on both SQLite and PostgreSQL configurations (no `_IS_SQLITE` skip).
- Tests MUST fail against the current `main` in a predictable, diagnosable way (the no-filter regression test passes; the filter-by-A test fails because B's items leak through; the 404/422 tests fail because the route returns 200).

**Non-Goals:**
- No production code in this change.
- No changes to the existing list test at line 258-276; the new tests are additive.
- No parametrized pytest — a single test function per scenario or a single combined function is fine; clarity beats parametrization for six scenarios.

## Decisions

### Decision 1: Single combined test function, not six

The new tests SHALL live in one test function, e.g. `test_admin_items_list_filters_by_category`, that seeds two categories with two items each and then exercises all six scenarios in sequence. Rationale:

- Shared setup (two categories, four items) is expensive to replicate across six tests.
- The scenarios are tightly coupled — they all verify one endpoint contract.
- Failure messages stay clear because each assertion uses a distinct message/line.

**Alternative considered — parametrized test**: Rejected. Parametrization obscures which scenario failed in the pytest output, and the 404/422 cases need different response shape assertions than the 200 cases.

### Decision 2: Use existing fixtures, match the file's style

The new test SHALL use `client`, `migrated_db_session`, and `admin_headers` fixtures already in scope in `test_menu_admin.py`. It SHALL NOT use `db_client` (which is Postgres-only via `_IS_SQLITE`) — the filter logic is pure SQL `WHERE`, identical on both backends, so the fast SQLite path is correct here.

### Decision 3: Do not modify or delete the existing list test

The existing `test_admin_lists_items` (or whatever it is named at line 258) stays as-is. It's a Postgres-only regression and it covers a different concern (that the endpoint returns items at all). Deleting it would lose coverage.

## Risks / Trade-offs

- **Risk**: Landing RED alone on `main` breaks CI. → **Mitigation**: RED and GREEN MUST be merged together (same PR or stacked PRs merged back-to-back). The proposal's Non-Goals section calls this out explicitly.
- **Trade-off**: One fat test function vs. six small ones. We chose one for setup cost and coupling reasons (Decision 1); if it grows beyond the six scenarios listed here, split it.

## Migration Plan

N/A for a test-only change. Rollback = revert the test commit.
