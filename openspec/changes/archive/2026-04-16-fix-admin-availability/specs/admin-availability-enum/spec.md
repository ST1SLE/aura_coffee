## ADDED Requirements

### Requirement: Admin frontend availability enum values MUST match backend serialisation

The `Availability` type in `web/admin/src/api/menu.ts` and all string comparisons in `web/admin/src/pages/Menu/MenuItemsTable.tsx` SHALL use lowercase enum values (`'available'`, `'stop_list'`, `'archived'`) consistent with `shared/enums.py` → `MenuItemAvailability`.

Reference: PDD section 7.1 Phase 6 (Admin Panel), backend enum defined in `packages/shared/`.

#### Scenario: Switch reflects real availability state
- **WHEN** the backend returns `availability: "available"` for a menu item
- **THEN** the toggle switch in the admin menu table SHALL be checked (on)

#### Scenario: Stop-list badge renders
- **WHEN** the backend returns `availability: "stop_list"` for a menu item
- **THEN** the admin menu table SHALL display a warning badge with the stop-list label

#### Scenario: Archived badge renders and switch is disabled
- **WHEN** the backend returns `availability: "archived"` for a menu item
- **THEN** the admin menu table SHALL display a muted badge with the archived label AND the toggle switch SHALL be disabled
