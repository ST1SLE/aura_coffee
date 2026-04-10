## Context

Phase 2 manual testing of the admin menu exposed two unbuilt features. Both pieces of work live inside already-built modules, so this is a targeted extension, not an architectural change.

**Affected modules:** `[core-api]`, `[web-admin]`, `[shared]` (read-only — the `menu_item_modifiers` junction table and `MenuItem.modifiers` relationship already exist in `packages/shared/src/shared/models/menu.py`).

**Current state:**
- `MenuItemResponse` already serializes `modifiers: list[ModifierResponse]` (schemas/menu.py:146). `MenuAdminService.list_items` / `get_item` already eager-load modifiers via `selectinload` (services/menu_admin.py:111, 119). So the READ side of modifiers works; only the WRITE side is missing.
- `CategoryUpdate` (schemas/menu.py:32-37) already accepts `sort_order: int | None`. The backend accepts updates to `sort_order` today; only the frontend form omits it.
- `MenuItemFormDialog.tsx` already has the "create → switch to edit mode" pattern used by `SizeOptionsEditor` — the same gating will apply to the modifier picker.
- Thread 1 (admin login) merged without touching any `pages/Menu/**` files. Investigation snapshot of `sessionExpired` guard sites was re-verified: all five call sites are already properly gated by `err instanceof ApiError && err.status === 401`, so no hygiene work is needed in this change.

## Goals / Non-Goals

**Goals:**
- Admins MUST be able to reorder existing categories through the menu admin UI without direct DB access.
- Admins MUST be able to attach and detach modifiers on a menu item through the admin UI.
- The backend MUST expose the attach/detach capability as a first-class endpoint.
- Role isolation (INV-010) MUST be preserved: modifier linking is admin-only, matching the rest of `/items` mutations.
- The change MUST stay scoped to the files listed in the proposal; no drive-by refactors.

**Non-Goals:**
- Per-link REST granularity (`POST /items/{id}/modifiers/{mod_id}`). Rejected in decision D-1 below.
- Drag-and-drop or arrow-button reordering for categories. A numeric input is sufficient for Phase 2.
- Any change to the customer-facing menu surface.
- Any change to the admin items list category filter (Thread 4).
- Touching `api/client.ts` or `pages/Login/` (Thread 1).
- sessionExpired hygiene sweep — re-audit showed it's already correct.

## Decisions

### D-1. Modifier set-replacement via a single `PUT` endpoint

The system SHALL expose exactly one new endpoint: `PUT /api/v1/admin/menu/items/{item_id}/modifiers` with request body `MenuItemModifierSet { modifier_ids: list[int] }`, returning the full updated `MenuItemResponse`. The handler SHALL replace the entire set of attached modifiers with the supplied list.

**Alternatives considered:**

| Option | Shape | Verdict |
|---|---|---|
| A. Bulk PUT (chosen) | `PUT /items/{id}/modifiers` with `{modifier_ids: [...]}` — replaces the whole set | Chosen. Idempotent; maps 1:1 to a checkbox-list form submit; one request per save. |
| B. Per-link REST | `POST /items/{id}/modifiers/{mod_id}` + `DELETE .../{mod_id}` | Rejected. The link carries no per-link payload, so per-link endpoints are noise. Forces the client to diff before/after sets. |
| C. Fold into `MenuItemUpdate` | Add `modifier_ids?: list[int]` to `MenuItemUpdate` | Rejected. Blurs field updates with relationship management; `exclude_unset` semantics for "absent vs empty list" become painful; couples the save button of the form to modifier toggling. |

Sizes use granular endpoints because each `SizeOption` row carries its own `label`, `price`, `available` columns. Modifiers have no such per-link data — the junction table is just two FKs. So the sizes pattern does not apply, and bulk replacement is the cleaner fit.

### D-2. Validation returns 422 on unknown modifier IDs

`MenuAdminService.set_item_modifiers` SHALL:
1. Load the `MenuItem` by id; raise HTTP 404 if missing.
2. If `modifier_ids` is non-empty, query `Modifier.id.in_(modifier_ids)` and compare the returned count to `len(set(modifier_ids))`. If any id is missing, raise HTTP 422 with a detail naming the missing ids.
3. Assign the loaded `Modifier` list to `item.modifiers` (SQLAlchemy handles the junction inserts/deletes automatically via `secondary=menu_item_modifiers`).
4. Commit. On `IntegrityError`, rollback and raise HTTP 409 (defensive — should not occur for this endpoint but matches the pattern of the rest of the service).
5. Return `self.get_item(item_id)` so the response includes freshly eager-loaded size options and modifiers.

**Rationale:** 422 (not 404) for unknown modifier ids because the caller's *payload* is invalid, not the addressed resource. This matches how `create_item` handles an unknown `category_id` via a separate 404 on the addressed entity and leaves 422 for payload-level schema validation. The difference is small; 422 is chosen because FastAPI users associate 422 with "your body had bad data", which is what an unknown modifier id is.

Duplicate ids in the input list SHALL be deduplicated server-side (converted to a set before assignment). No error is raised for duplicates — the client may submit `[1, 1, 2]` and get back a clean `[1, 2]`.

### D-3. RBAC matrix entry

The new route SHALL be registered in `core_api.rbac_matrix.ROUTE_MATRIX` as:

```python
("PUT", "/api/v1/admin/menu/items/{item_id}/modifiers"): {"admin"}
```

Barista SHALL NOT be allowed to attach/detach modifiers. Rationale: this is a menu-structure change, not a stop-list toggle. The `menu-admin-crud` spec's "barista only gets GET and `*/availability`" invariant holds.

### D-4. Frontend: lift modifier loading into `MenuPage`

`pages/Menu/index.tsx` already fetches `categories` once and passes them down. It SHALL additionally fetch `modifiers` via `listModifiers()` on mount and pass the array as a prop to both:
- `ModifiersPanel` (which currently fetches its own — it SHALL be updated to accept a `modifiers` prop and an `onChange(next: ModifierResponse[])` callback so the lifted state stays in sync when the panel mutates modifiers).
- `MenuItemFormDialog` (new prop).

**Alternative considered:** have `MenuItemFormDialog` fetch modifiers itself on open. Rejected — it would re-fetch on every dialog open, and would leave `ModifiersPanel` as the only owner of modifier state, making cross-component sync awkward when a user adds a new modifier in the panel and then immediately opens an item form.

### D-5. Frontend: `ModifiersPicker` is a separate component, save-on-toggle

`ModifiersPicker.tsx` SHALL be a new component alongside `SizeOptionsEditor.tsx`. Props:

```ts
interface Props {
  menuItemId: number;          // 0 when disabled
  allModifiers: ModifierResponse[];
  selectedIds: number[];
  onChange: (nextIds: number[]) => void;
  disabled?: boolean;          // true before first save (create mode)
  onError: (msg: string) => void;
}
```

Behavior:
- Renders one checkbox per entry in `allModifiers`, checked when the id is in `selectedIds`.
- Disabled rendering with a hint when `disabled` is true, matching `SizeOptionsEditor`'s "save the item first" pattern.
- On toggle, computes the next id set, calls `setItemModifiers(menuItemId, nextIds)`, and on success calls `onChange(nextIds)` with the server-confirmed list extracted from the returned `MenuItemResponse.modifiers.map(m => m.id)`.
- On error, surfaces via `onError` and does NOT update local state (no optimistic divergence).
- Does NOT re-render unchecked modifiers as hidden; all modifiers are listed so the user can see the full set.

`MenuItemFormDialog` SHALL own the `selectedIds` state (initialized from `item?.modifiers.map(m => m.id)`) and SHALL pass `onChange` that updates both local state and propagates via `onSaved` so the parent table reflects the new modifier set.

### D-6. Category `sort_order` editing — inline numeric input

`CategoryList.tsx`:
- Add `editSortOrder: string` to the edit-row state block, initialized in `startEdit` from `String(cat.sort_order)`.
- Render a narrow numeric `Input` in the edit row next to the type `<select>`.
- In `handleSaveEdit`, parse with `parseInt(editSortOrder, 10)`; on `NaN` fall back to `cat.sort_order`. Include the parsed value in the `updateCategory` body.
- The create form continues to hardcode `sort_order: categories.length` — reordering is only available via edit of an existing row.

After a successful save, the client SHALL re-sort its local `categories` array by `sort_order` ascending (ties broken by `id`) to match the server's ordering (`MenuAdminService.list_categories` already sorts by `(sort_order, id)`).

## Risks / Trade-offs

- **[Risk] Set-replacement endpoint races with concurrent edits.** Two admins editing the same item could clobber each other's modifier selections. → **Mitigation:** accepted. This is a single-shop admin panel with maybe two concurrent admins at most; last-write-wins is fine for Phase 2. If this ever matters we add an `updated_at` precondition header.

- **[Risk] Dedup of duplicate modifier ids silently rewrites the payload.** A client that sends `[1, 1, 2]` gets back `[1, 2]` without warning. → **Mitigation:** accepted. The UI will never submit duplicates, and this matches how set types behave. Not worth a 422 error.

- **[Risk] `ModifiersPanel` and `MenuItemFormDialog` become coupled via the lifted modifier state in `MenuPage`.** Adding a modifier in the panel while the dialog is open could cause the dialog to re-render the picker list. → **Mitigation:** accepted, even desirable — the admin sees new modifiers immediately. The dialog holds its own `selectedIds`, so the list of available modifiers growing does not destabilize user selection.

- **[Trade-off] Save-on-toggle for the picker vs save-on-form-submit.** Save-on-toggle means each checkbox click is a network request; a slow connection flashes briefly. But it's consistent with how `SizeOptionsEditor` behaves today, and avoids the "I toggled modifiers but forgot to click Save on the form and lost them" footgun. Chosen: save-on-toggle.

- **[Trade-off] Numeric `sort_order` input vs arrow buttons.** The numeric input forces the user to know the existing sort values. Arrow buttons are more discoverable. For a coffee shop with ~5-10 categories, the numeric input is acceptable; arrows can be added later without a spec change.

## Migration Plan

Forward-only. No database changes. No data backfill.

- Deploy backend (new route + schema + RBAC entry) before frontend. The new endpoint is additive — old clients are unaffected.
- Deploy frontend (new helper + form wiring). Old browsers that have cached the previous `api/menu.ts` bundle will continue to work (no modifier picker, but no breakage) until they reload.
- Rollback: revert both commits. No data to clean up.

## Open Questions

_None outstanding. Decisions above resolve the open questions from the exploration phase._
