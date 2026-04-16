## Context

**Affected modules:** [web-admin]

The admin panel's `MenuItemsTable` component renders availability badges and a toggle switch by comparing `item.availability` against string literals. The `Availability` type and all comparisons use UPPERCASE values (`'AVAILABLE'`, `'STOP_LIST'`, `'ARCHIVED'`), but the backend (`shared/enums.py` → `MenuItemAvailability`) serialises lowercase values (`'available'`, `'stop_list'`, `'archived'`). The mismatch causes:

1. Switch is never checked (always off) regardless of real state.
2. STOP_LIST / ARCHIVED badges never render.
3. The switch is never disabled for archived items.

## Goals / Non-Goals

**Goals:**
- Align frontend enum literals with backend response values so the admin menu table reflects real availability state.

**Non-Goals:**
- Introducing shared enum codegen or a runtime validation layer.
- Changing backend enum casing.
- Touching customer-facing frontend.

## Decisions

### Decision 1: Fix frontend literals to match backend (not the other way around)

The backend enum is the source of truth (`shared/enums.py`). Changing backend casing would require a migration and affect all consumers. Fixing the two frontend files is the minimal, safe change.

**Alternatives considered:**
- Add a normalisation layer in the API client (`toUpperCase` on response) — adds runtime overhead and a hidden transform for a problem that only exists because of a typo.

## Risks / Trade-offs

- **[Risk]** Other admin frontend files may also compare against uppercase availability values. → **Mitigation**: Grep the codebase for `'AVAILABLE'`, `'STOP_LIST'`, `'ARCHIVED'` to confirm the two files are the only occurrences.
- **[Risk]** TypeScript type change may cause compile errors elsewhere. → **Mitigation**: Run `tsc --noEmit` after the fix.
