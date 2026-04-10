## Why

The admin SPA (`web/admin/`) currently ships `MenuPage.tsx` as a placeholder stub while the backend already exposes a full admin CRUD surface under `/api/v1/admin/menu/...` (see spec `menu-admin-crud`). Without a UI, admins and baristas cannot manage categories, items, modifiers, size options, or operate the stop list during a shift — blocking PDD §7.1 Phase 6 (Admin Panel) from being usable. This change delivers the first functional screen of the admin panel so real staff can run the menu end-to-end.

## What Changes

- Replace the placeholder `web/admin/src/pages/MenuPage.tsx` stub with a real `Menu/` page module tree that renders two coordinated panes: a **Categories** sidebar and a **Menu Items** table for the selected category.
- Add a typed API client module `web/admin/src/api/menu.ts` covering every endpoint in `menu-admin-crud` (categories, items, modifiers, sizes, availability PATCH) using the existing `authenticatedFetch` pattern adopted by the customer app.
- Implement CRUD for categories (create / rename / delete, with 409-on-referenced surfaced as a user error).
- Implement CRUD for menu items via a modal form (name, description, category, base price, archived), reusing `MenuItemCreate` / `MenuItemUpdate` shapes from the backend.
- Implement an availability toggle on each menu item row that calls `PATCH .../items/{id}/availability` and reflects the three-state `availability` badge (`AVAILABLE` / `STOP_LIST` / `ARCHIVED`) returned by the server — this is the operational stop-list control for baristas (INV-006).
- Implement management of per-item modifiers and size options from inside the item form (add / edit / delete rows), including the modifier availability toggle.
- Enforce role-aware UI: mutation controls are hidden for `barista` except the two availability toggles, mirroring the RBAC matrix in `menu-admin-crud`.
- Wire the page into the existing admin router and i18n (RU + EN strings).

## Capabilities

### New Capabilities
- `menu-admin-ui`: Admin SPA page and API client for managing menu categories, items, modifiers, size options, and the stop list, backed by `/api/v1/admin/menu/...`.

### Modified Capabilities
<!-- None. This change consumes the existing menu-admin-crud API without changing its requirements. -->

## Non-Goals

- **Photo / image upload.** The backend spec `menu-admin-crud` has no image storage endpoint and the schema has no image column; adding it would require a new backend change and object storage. Out of scope here.
- **Bulk import / CSV export** of menu items.
- **Reordering** categories or items via drag-and-drop (sort_order is editable via the form only, not by dragging).
- **Audit log / change history** UI for menu edits.
- **Admin-side authentication screens.** This change assumes an access token is already present in the admin app's auth state; wiring admin login is tracked separately under the `staff-auth` spec.
- **Customer-facing menu browsing** — that is `web/customer/`, not `web/admin/`.
- **Modifier ↔ item many-to-many assignment UI** beyond what `menu-admin-crud` already supports on the item payload; if the backend contract treats modifiers as standalone entities only, the UI mirrors that and does not invent a link table.

## Impact

- **MVP phase**: Phase 6 (Admin Panel), per PDD §7.1.
- **Affected code**:
  - `web/admin/src/pages/Menu/` — new page module (replaces the stub `MenuPage.tsx`; the old file is removed and its route re-pointed).
  - `web/admin/src/api/menu.ts` — new API client module (the `api/` directory does not exist yet and will be created).
  - `web/admin/src/api/client.ts` — new shared `authenticatedFetch` helper (port of the pattern from `authenticated-fetch` spec into the admin app; admin currently has none).
  - `web/admin/src/App.tsx` — update the `/menu` route to the new page module.
  - `web/admin/src/i18n/` — new RU + EN keys under `pages.menu.*` and `menu.*`.
  - `web/admin/src/components/ui/` — may add small shadcn primitives (`dialog`, `input`, `table`, `switch`) that are not yet vendored; only what this page needs.
- **APIs consumed** (read-only contract, no backend changes):
  - `GET|POST|PUT|DELETE /api/v1/admin/menu/categories[/{id}]`
  - `GET|POST|PUT|DELETE /api/v1/admin/menu/items[/{id}]`
  - `GET|POST|PUT|DELETE /api/v1/admin/menu/modifiers[/{id}]`
  - `POST|PUT|DELETE /api/v1/admin/menu/sizes[/{id}]`
  - `PATCH /api/v1/admin/menu/items/{id}/availability`
  - `PATCH /api/v1/admin/menu/modifiers/{id}/availability`
- **Dependencies**: no new runtime deps expected beyond shadcn primitive files; data fetching uses plain `authenticatedFetch` + React state (no TanStack Query introduction in this change, to stay within scope — can be revisited later if the page grows).
- **Inviolable rules touched**: INV-002 (auth on mutations — enforced by `authenticatedFetch`), INV-006 (stop list — the item/modifier availability toggles ARE the stop-list UI), INV-010 (role isolation — mutation controls hidden for non-admins).
- **Risk**: low. No schema, migration, or payment-path changes. All risk is confined to the admin SPA bundle.
