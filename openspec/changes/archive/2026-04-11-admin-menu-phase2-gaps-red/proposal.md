## Why

Manual Phase 2 testing of the admin menu surfaced two unbuilt features. The first — admins cannot reorder existing categories (`CategoryList.tsx` edit row omits `sort_order`) — is frontend-only, so it lives entirely in the GREEN change. The second — admins cannot attach modifiers to a menu item — requires a new backend endpoint `PUT /api/v1/admin/menu/items/{item_id}/modifiers` that does not exist today. This RED change pins down the expected backend behavior of that endpoint as failing tests before any production code is written.

This is the **RED phase** of the backend work for `admin-menu-phase2-gaps-green`. The GREEN change will make these tests pass, add the `setItemModifiers` API client helper, wire the `ModifiersPicker` UI, and add the category `sort_order` edit input.

MVP phase: **Phase 6 — Admin Panel** (PDD §7.1). Extends the already-delivered `menu-admin-crud` and `menu-admin-ui` capabilities.

## What Changes

- Add failing tests to `services/core-api/tests/test_menu_admin.py` that lock in the contract for the new `PUT /api/v1/admin/menu/items/{item_id}/modifiers` endpoint:
  - Admin attaches a set of modifiers to an item → 200, `MenuItemResponse.modifiers` contains exactly those ids.
  - Admin detaches all modifiers with `{"modifier_ids": []}` → 200, modifiers array is empty.
  - Replacement semantics: item previously had `[1, 2]`, request `[5]` → response contains only modifier `5`.
  - Unknown modifier id → 422, item's modifier set unchanged.
  - Unknown item id → 404.
  - Duplicate ids in input → deduplicated in response (no error).
  - Barista role → 403.
  - Unauthenticated → 401.
- Tests MUST be SQLite-safe and MUST use existing fixtures (`client`, `admin_headers`, `barista_headers`), seeding via the admin API (not raw SQL) so the RED suite runs in the fast path.
- Production code in `routers/menu_admin.py`, `services/menu_admin.py`, `schemas/menu.py`, and `rbac_matrix.py` is NOT touched in this change — the tests will fail against `main` (ImportError on `MenuItemModifierSet`, 404/405 on the route, whichever comes first), which is the RED state.

## Capabilities

### New Capabilities
_None._

### Modified Capabilities
- `menu-admin-crud`: pins the new scenarios for the modifier set-replacement endpoint and the updated RBAC matrix invariant. The spec delta is identical to the delta in `admin-menu-phase2-gaps-green` — the contract is defined once and consumed by both phases.

## Non-Goals

- **No production code changes.** `routers/menu_admin.py`, `services/menu_admin.py`, `schemas/menu.py`, and `rbac_matrix.py` are untouched. The point of this phase is a failing regression suite.
- **No frontend changes.** All UI work (`CategoryList.tsx` sort_order, `ModifiersPicker`, `MenuItemFormDialog` wiring, `api/menu.ts` helper) lives in the GREEN change.
- **No category `sort_order` tests.** Gap 1 is frontend-only; the backend already accepts `sort_order` in `CategoryUpdate` and existing category tests cover it.
- **No `sessionExpired` hygiene work.** Re-audit confirmed all call sites are already guarded.
- **Not merged to `main` alone.** This change ships together with `admin-menu-phase2-gaps-green` — merging RED alone would land failing tests on `main`.

## Impact

- **Code**: `services/core-api/tests/test_menu_admin.py` gets one new test function (or small test class) exercising the eight scenarios listed above.
- **CI**: test run turns red until GREEN lands. The two changes MUST be applied back-to-back on the same branch.
- **Dependencies**: none.
- **Inviolable rules**: INV-002 / INV-010 (admin authorization) — scenarios pin the barista-403 and unauthenticated-401 invariants.
