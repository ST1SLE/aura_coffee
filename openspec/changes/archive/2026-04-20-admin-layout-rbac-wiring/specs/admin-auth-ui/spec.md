## ADDED Requirements

### Requirement: Admin useCurrentRole hook

The admin SPA SHALL expose `useCurrentRole(): StaffRole | null` from `web/admin/src/lib/auth.ts`. The hook SHALL return the value of `getRole()` captured once at component mount via `useMemo(() => getRole(), [])`. It MUST NOT subscribe to the `storage` event, MUST NOT use `useState`, and MUST NOT trigger re-renders when `localStorage.staffRole` changes mid-session.

Consumers that are rendered inside `ProtectedRoute` with a non-empty `allowedRoles` MAY treat a `null` return as unreachable, but MUST still narrow the type (e.g., via an early return) so that TypeScript inference holds without `!` assertions.

Refs: PDD §4.5 (role-filtered admin panel); INV-010 (server-side authoritative); design.md D1 / D3.

#### Scenario: Returns null when no role persisted
- **WHEN** `localStorage` contains no `staffRole` key and a test component calls `useCurrentRole()`
- **THEN** the hook returns `null`

#### Scenario: Returns persisted role after setRole
- **WHEN** `setRole('barista')` is called, then a test component calls `useCurrentRole()` via `renderHook`
- **THEN** the hook returns `'barista'`

#### Scenario: Value is stable across re-renders within a session
- **WHEN** `setRole('admin')` is called, `useCurrentRole()` is read once (returns `'admin'`), then `setRole('barista')` is called in-place, and the consuming component re-renders without un-mounting
- **THEN** the hook STILL returns `'admin'` (the cached value), reflecting the `useMemo(..., [])` contract — no reactive subscription on `localStorage`

### Requirement: Role-filtered admin sidebar

The admin `Layout` component at `web/admin/src/components/Layout.tsx` SHALL filter its `navItems` through a static `NAV_BY_ROLE: Record<StaffRole, readonly string[]>` map, keyed by `StaffRole` and exhaustive at the TypeScript type level. The mapping SHALL be:

- `admin` → `['dashboard', 'orders', 'menu', 'users', 'promos', 'settings']` (all 6 nav items).
- `barista` → `['orders', 'menu']` (orders for queue; menu for stop-list management, PDD §4.5).
- `courier` → `[]` (courier uses `CourierShell`; empty array is a defensive default for edge-case routing).

When `useCurrentRole()` returns `null`, Layout SHALL render zero nav links. Each rendered `<Link>` SHALL carry a `data-testid` attribute of the form `nav-<key>` (e.g., `nav-orders`) to support role-matrix tests independent of i18n labels.

This requirement affects UX only — INV-010 RBAC enforcement remains server-side via `rbac_matrix`, and client-side routing remains gated by `ProtectedRoute.allowedRoles` in `App.tsx`.

Refs: PDD §4.5; INV-010; design.md D2 / D4.

#### Scenario: Admin sees all six nav items
- **WHEN** `setRole('admin')` is called and `<Layout>` renders inside `<MemoryRouter>`
- **THEN** the DOM contains links with `data-testid` values `nav-dashboard`, `nav-orders`, `nav-menu`, `nav-users`, `nav-promos`, `nav-settings`

#### Scenario: Barista sees only orders and menu
- **WHEN** `setRole('barista')` is called and `<Layout>` renders
- **THEN** the DOM contains `nav-orders` and `nav-menu` links, AND does NOT contain `nav-dashboard`, `nav-users`, `nav-promos`, `nav-settings`

#### Scenario: Courier sees zero nav links
- **WHEN** `setRole('courier')` is called and `<Layout>` renders
- **THEN** the DOM contains no element with a `data-testid` prefix of `nav-`

#### Scenario: No persisted role renders zero nav links
- **WHEN** `clearRole()` is called (no `staffRole` in `localStorage`) and `<Layout>` renders
- **THEN** the DOM contains no element with a `data-testid` prefix of `nav-`

#### Scenario: Role map is exhaustive at compile time
- **WHEN** a developer adds a new variant to the `StaffRole` union (e.g., `'manager'`) without updating `NAV_BY_ROLE`
- **THEN** the TypeScript compiler emits an error on the `Record<StaffRole, readonly string[]>` literal (missing property), preventing the build

## MODIFIED Requirements

### Requirement: Admin role storage helpers

The admin SPA SHALL expose role helpers from `web/admin/src/lib/auth.ts`: `getRole(): StaffRole | null`, `setRole(role: StaffRole): void`, `clearRole(): void`, and `useCurrentRole(): StaffRole | null`. `StaffRole` SHALL be the union type `'admin' | 'barista' | 'courier'`. The three non-hook helpers SHALL read and write a single `localStorage` key (`staffRole`). `setRole` SHALL reject any value outside the `StaffRole` union (narrowed at the TypeScript type level; at runtime, `setRole` MAY skip the check since the caller is always `staffLogin` output). `useCurrentRole` SHALL wrap `getRole()` in `useMemo(..., [])` so the value is captured once per component mount and NOT subscribed to `localStorage` changes.

**Previously:** The module exposed only `getRole`, `setRole`, and `clearRole`. Pages that needed the current role (e.g., `Menu/index.tsx`) defined local stub hooks returning hardcoded `'admin'`.

**Now:** A shared `useCurrentRole` hook is available, local stubs are removed, and consumers read role via the public API.

Refs: PDD §4.5 (role-filtered admin panel), INV-010 (client role is a UX hint — server remains the source of truth); design.md D1.

#### Scenario: setRole persists role across a page reload
- **WHEN** `setRole('courier')` is called and the page is reloaded
- **THEN** `getRole()` returns `'courier'`

#### Scenario: clearRole removes the persisted role
- **WHEN** `setRole('courier')` is called, then `clearRole()` is called
- **THEN** `getRole()` returns `null`

#### Scenario: getRole with no persisted value returns null
- **WHEN** `localStorage` contains no `staffRole` key
- **THEN** `getRole()` returns `null` (NOT `undefined`, NOT the string `"null"`)

#### Scenario: getRole narrows to StaffRole at compile time
- **WHEN** TypeScript consumers write `const r = getRole(); if (r === 'courier') { ... }`
- **THEN** the compiler does NOT error on the comparison (i.e. `StaffRole | null` is the inferred return type, not `string | null`)

#### Scenario: useCurrentRole exposed from the module
- **WHEN** a consumer writes `import { useCurrentRole } from '@/lib/auth'`
- **THEN** TypeScript resolves the import and the hook returns `StaffRole | null`
