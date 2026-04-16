## Why

Admin panel's menu items table does not correctly display availability state (switch, badges) because the frontend uses UPPERCASE enum values (`'AVAILABLE'`, `'STOP_LIST'`, `'ARCHIVED'`) while the backend (`shared/enums.py` → `MenuItemAvailability`) returns lowercase (`'available'`, `'stop_list'`, `'archived'`). This is MVP Phase 6 (Admin Panel) — the bug blocks baristas from managing the stop-list.

## What Changes

- Fix the `Availability` type alias in `web/admin/src/api/menu.ts` to use lowercase enum values matching the backend.
- Fix all string comparisons against availability values in `web/admin/src/pages/Menu/MenuItemsTable.tsx` (badge rendering, switch checked/disabled state).

## Non-Goals

- No changes to backend enum definitions — the backend is the source of truth.
- No introduction of a shared enum codegen pipeline (that's a separate initiative).
- No changes to customer-facing frontend — this is admin-panel only.

## Capabilities

### New Capabilities

_None — this is a bug fix, not a new capability._

### Modified Capabilities

_None — no spec-level behavior changes, only correcting a frontend value mismatch._

## Impact

- **Files**: `web/admin/src/api/menu.ts`, `web/admin/src/pages/Menu/MenuItemsTable.tsx`
- **APIs**: No API changes. Frontend now correctly interprets existing API responses.
- **Dependencies**: None.
- **MVP Phase**: Phase 6 — Admin Panel.
