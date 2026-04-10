## Why

Manual Phase 2 testing of the admin menu surfaced two unbuilt features that block the Admin Panel milestone: admins cannot reorder existing categories (the edit form omits `sort_order`), and admins cannot attach modifiers to a menu item from the UI — the M:N relationship exists in the database and is serialized in `MenuItemResponse`, but there is no backend endpoint to mutate it and no UI surface to pick modifiers. Without these two pieces, menu curation requires direct SQL, which is not acceptable for Phase 6 hand-off.

This is the **GREEN phase** of the backend work paired with `admin-menu-phase2-gaps-red`, plus all frontend IMPL/TEST work (frontend changes are single-change per project convention). The RED change pins the contract of the new backend endpoint as failing tests; this change makes them pass and adds the API client helper, UI picker, and category `sort_order` input. The two changes MUST be applied back-to-back.

MVP phase: **Phase 6 — Admin Panel** (PDD §7.1).

## What Changes

- Add an inline numeric `sort_order` input to the category edit row in `CategoryList.tsx`; pass the value through `updateCategory`. Backend `CategoryUpdate` already accepts the field — no schema work.
- Add a new backend endpoint `PUT /api/v1/admin/menu/items/{item_id}/modifiers` that replaces the full set of attached modifiers with the supplied list. Bulk set-replacement (not per-link POST/DELETE) because each link carries no payload of its own, and the form UX is "check boxes, save".
- Add a new Pydantic request model `MenuItemModifierSet { modifier_ids: list[int] }` in `core_api.schemas.menu`.
- Add `MenuAdminService.set_item_modifiers(item_id, modifier_ids)` with 404 on missing item, 422 on any unknown modifier id, full replacement semantics, and a reload via `get_item` for the response.
- Extend `api/menu.ts` with a `setItemModifiers(id, modifier_ids)` helper.
- Add a `ModifiersPicker.tsx` component next to `SizeOptionsEditor.tsx`: checkbox list of all modifiers, disabled until the item exists (mirrors `SizeOptionsEditor`'s gating), saves on every toggle by calling the new endpoint.
- Extend `MenuItemFormDialog.tsx` to accept a `modifiers: ModifierResponse[]` prop and render `ModifiersPicker` below `SizeOptionsEditor`.
- Lift modifier loading into `MenuPage` (`pages/Menu/index.tsx`) so the list is fetched once and passed to both `ModifiersPanel` and `MenuItemFormDialog`.
- Register the new route in `ROUTE_MATRIX` as `{admin}` only (matches the rest of `/items` mutations).

## Capabilities

### New Capabilities
_None._

### Modified Capabilities
- `menu-admin-crud`: add a new requirement for the item-modifiers set-replacement endpoint and extend the RBAC matrix requirement to cover it.
- `menu-admin-ui`: add a requirement for the item form's modifier picker, extend the category form requirement to cover `sort_order` editing, and extend the API client requirement to cover the new `setItemModifiers` helper.

## Non-Goals

- Per-link attach/detach endpoints (`POST /items/{id}/modifiers/{mod_id}`). A set-replacement PUT is chosen and the granular variant is explicitly out of scope.
- Category reorder via drag-and-drop or up/down arrow buttons. A plain numeric input is sufficient for Phase 2; richer reorder UX is deferred.
- Modifier attach through the public customer menu surface (this change only affects admin CRUD and admin UI).
- Any changes to `web/admin/src/api/client.ts` or `pages/Login/` — Thread 1's lane, already merged, untouched here.
- Any changes to the admin items list category filter — Thread 4's lane (backend).
- Error-message hygiene sweep for `t('common.sessionExpired')` — re-audit of `CategoryList.tsx`, `ModifiersPanel.tsx`, and `MenuItemFormDialog.tsx` confirms every call is already guarded by `err instanceof ApiError && err.status === 401`. No-op for this change.

## Impact

- **MVP phase:** Phase 6 (Admin Panel) per PDD §7.1. Closes two gaps that block Phase 2 manual sign-off of the admin menu flow.
- **Affected code:**
  - `services/core-api/src/core_api/schemas/menu.py` — new `MenuItemModifierSet` model.
  - `services/core-api/src/core_api/services/menu_admin.py` — new `set_item_modifiers` method.
  - `services/core-api/src/core_api/routers/menu_admin.py` — new `PUT /items/{item_id}/modifiers` route.
  - `services/core-api/src/core_api/rbac_matrix.py` — new entry for the route, `{admin}` only.
  - `web/admin/src/api/menu.ts` — new `setItemModifiers` helper.
  - `web/admin/src/pages/Menu/CategoryList.tsx` — `sort_order` input in edit row.
  - `web/admin/src/pages/Menu/MenuItemFormDialog.tsx` — new `modifiers` prop, renders `ModifiersPicker`.
  - `web/admin/src/pages/Menu/ModifiersPicker.tsx` — new component.
  - `web/admin/src/pages/Menu/index.tsx` — lift modifier fetch, pass down.
  - i18n locale files — new keys for modifier picker strings and category sort order label.
- **APIs:** one new admin route; no customer-facing API change.
- **Data:** no schema or migration changes. The `menu_item_modifiers` junction and `MenuItem.modifiers` relationship already exist.
- **Dependencies:** none added.
- **Inviolable rules touched:** INV-002 (auth on mutations — covered by RBAC matrix entry), INV-010 (role isolation — admin-only for modifier linking).
