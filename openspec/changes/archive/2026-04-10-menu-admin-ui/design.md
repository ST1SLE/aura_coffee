## Context

**Affected modules:** [web-admin].

The admin SPA (`web/admin/`) is a minimal scaffold: React 19 + Vite + Tailwind + shadcn/ui + react-i18next, with a `Layout` shell, an i18n config (RU + EN), a single vendored shadcn primitive (`button`), and one-line placeholder pages per route. Crucially, there is currently **no `api/` directory, no auth-aware fetch wrapper, and no data-fetching library** in the admin app. The customer app already ships an `authenticatedFetch` pattern (see spec `authenticated-fetch`), but that module lives under `web/customer/` and is not shared across the two SPAs — `packages/shared` is Python-only today.

Meanwhile the backend side of menu admin is complete: spec `menu-admin-crud` fully defines CRUD for categories, items, modifiers, size options, and the two availability PATCH endpoints. The Pydantic response shapes (`CategoryResponse`, `MenuItemResponse`, `ModifierResponse`, `SizeOptionResponse`, `AvailabilityPatch`) are the contract this UI consumes. RBAC is enforced server-side: `admin` mutates everything, `barista` may list and toggle availability, everyone else gets 403.

Stakeholders: shop admin (full mutation), barista (runs the stop list during a shift — INV-006), developer reviewing Phase 6 readiness.

Constraints:
- Bilingual UI (RU + EN) via `react-i18next` — no hard-coded Russian or English strings in JSX.
- Prices are integers in kopecks end-to-end; the form MUST render them as rubles for humans and convert on submit.
- INV-002: every write goes through authenticated requests.
- INV-010: role isolation is enforced server-side, but the UI SHOULD hide controls the current role cannot use to avoid generating 403s the user cannot interpret.
- Scope: this is one page of a larger admin; decisions MUST be reversible — no framework lock-in that would block introducing TanStack Query, Zod, or OpenAPI codegen later.

## Goals / Non-Goals

**Goals:**
- Ship a working Menu admin page that covers categories, items (with modifiers and sizes managed inline), and the availability toggle — usable in production by a real barista on shift.
- Establish a thin, typed API client (`src/api/menu.ts` + `src/api/client.ts`) that future admin pages can copy without pulling in a data-fetching framework in this change.
- Keep the blast radius inside `web/admin/` — no backend, no shared package, no migration, no other SPA.

**Non-Goals:**
- Introducing TanStack Query, SWR, Zustand, Redux, or an OpenAPI code generator in this change. (Plain `useState` + `useEffect` + typed `fetch` is enough for one page and keeps the PR reviewable.)
- Image upload, drag-and-drop reordering, bulk import, audit log — all listed in `proposal.md` Non-Goals.
- Admin authentication flow — this change assumes the access token is already in memory under whatever convention `staff-auth` ends up using; the API client reads it from a single module-level getter that can be re-wired when `staff-auth` lands.
- Optimistic UI. Every mutation waits for the server response before updating local state. Simpler to reason about and matches the low traffic of a single-shop admin.

## Decisions

### D1. File layout: page module under `pages/Menu/`, API under `api/menu.ts`

```
web/admin/src/
  api/
    client.ts              # authenticatedFetch + base URL + error class
    menu.ts                # typed wrappers per endpoint
  pages/
    Menu/
      index.tsx            # the <MenuPage> export; composes the panes
      CategoryList.tsx     # sidebar: list + create + rename + delete
      MenuItemsTable.tsx   # main pane: table, availability switch, row actions
      MenuItemFormDialog.tsx   # create/edit item modal (also manages sizes + modifier picks)
      SizeOptionsEditor.tsx    # inline editor inside the dialog
      ModifiersPanel.tsx       # global modifier list (small panel or drawer)
      types.ts                 # DTO types mirroring backend Pydantic schemas
```

**Rationale:** keeps every menu-admin file under two roots the user explicitly scoped (`pages/Menu/*` and `api/menu.ts`), makes the page composable, and matches the shadcn/ui convention of small co-located components. Alternative considered: one 800-line `MenuPage.tsx`. Rejected — unreviewable and blocks future reuse of the dialog.

### D2. Data fetching: plain typed `fetch`, no query library

Each screen MUST fetch on mount via `useEffect`, store results in `useState`, and re-fetch (not patch) after mutations. Loading state is per-request. Errors surface via a small toast hook or inline message — no global error boundary introduced in this change.

**Rationale:** this is one page against a low-RPS internal API. A query cache would be net-negative complexity for a change this size, and the user's scope does not include cross-page cache invalidation. Alternative considered: TanStack Query. Rejected — it is the right tool for the whole admin, not for one page; introducing it should be its own change so the decision is reviewable in isolation.

**Trade-off:** modifiers edited from the item dialog will trigger a re-fetch of the item list on close. Acceptable.

### D3. API client shape

`src/api/client.ts` exposes:

```ts
export class ApiError extends Error {
  constructor(public status: number, public body: unknown, message: string) { super(message); }
}

export async function authenticatedFetch(path: string, init?: RequestInit): Promise<Response>;
```

- Base URL comes from `import.meta.env.VITE_API_BASE_URL` (already the Vite convention in this repo).
- The access token comes from a single `getAccessToken()` stub in `src/api/client.ts` that returns `null` today. When `staff-auth` lands, that stub is the one line to change. This is the seam.
- On 401, this change does NOT implement refresh-and-retry — that is `staff-auth`'s responsibility. A 401 becomes an `ApiError(401, …)` that the page surfaces as "Session expired, reload".

`src/api/menu.ts` MUST export one async function per endpoint in `menu-admin-crud`, each returning a typed DTO. Example signatures:

```ts
listCategories(): Promise<CategoryResponse[]>
createCategory(body: CategoryCreate): Promise<CategoryResponse>
updateCategory(id: number, body: CategoryUpdate): Promise<CategoryResponse>
deleteCategory(id: number): Promise<void>            // 409 → ApiError

listItems(params?: { categoryId?: number }): Promise<MenuItemResponse[]>
getItem(id: number): Promise<MenuItemResponse>
createItem(body: MenuItemCreate): Promise<MenuItemResponse>
updateItem(id: number, body: MenuItemUpdate): Promise<MenuItemResponse>
deleteItem(id: number): Promise<void>
setItemAvailability(id: number, available: boolean): Promise<MenuItemResponse>

listModifiers(): Promise<ModifierResponse[]>
createModifier(body: ModifierCreate): Promise<ModifierResponse>
updateModifier(id: number, body: ModifierUpdate): Promise<ModifierResponse>
deleteModifier(id: number): Promise<void>
setModifierAvailability(id: number, available: boolean): Promise<ModifierResponse>

createSize(body: SizeOptionCreate): Promise<SizeOptionResponse>
updateSize(id: number, body: SizeOptionUpdate): Promise<SizeOptionResponse>
deleteSize(id: number): Promise<void>
```

DTO types live in `src/api/menu.ts` (or `pages/Menu/types.ts` — pick one and stick to it; design picks `src/api/menu.ts` so they travel with the client). They are hand-written mirrors of the Pydantic schemas in `core_api.schemas.menu`. They are NOT auto-generated in this change; when OpenAPI codegen lands repo-wide it will replace this file wholesale.

**Alternative considered:** `openapi-typescript` codegen now. Rejected for the same reason as TanStack Query — separate change, separate review.

### D4. Role awareness: pass `currentRole` in as a prop, hide admin-only controls

The page accepts a `currentRole: 'admin' | 'barista'` (sourced from whatever auth state the admin app ends up using; stubbed as `'admin'` until `staff-auth` lands). When the role is `barista`:

- Category sidebar shows names but hides the "New", "Rename", "Delete" buttons.
- Item table hides "New", "Edit", "Delete" row actions but keeps the availability switch active.
- Modifiers panel is read-only except for each modifier's availability switch.

This is UX, not security — the backend is the source of truth (INV-010). The UI just avoids surfacing buttons that will 403.

### D5. Stop-list toggle semantics

The availability switch in the item row sends `PATCH .../items/{id}/availability` with `{ available: bool }` and updates the row from the returned `MenuItemResponse`. The switch renders the server's `availability` field (`AVAILABLE` / `STOP_LIST` / `ARCHIVED`) as:

- `AVAILABLE` → switch on, badge hidden.
- `STOP_LIST` → switch off, yellow badge "Stop".
- `ARCHIVED` → switch disabled (cannot be toggled), gray badge "Archived".

This matches the precedence from `menu-admin-crud` scenario "Archived item stays archived when toggling availability" — archived is terminal for this control; to un-archive, the admin uses the item edit form.

### D6. Modifiers and sizes editing location

- **Size options** are edited **inside the item form dialog** (they are per-item in the backend schema). Adding/removing rows calls `createSize`/`deleteSize` while the dialog is open and the parent item already exists. For a brand-new item, sizes are added only after the initial `createItem` succeeds (the dialog switches from "create" to "edit" mode on success so the user can add sizes without closing it).
- **Modifiers** are global in the backend (`ModifierResponse` has no `menu_item_id`). They are edited in a separate small panel on the page (or a drawer), not inside the item dialog. This reflects the backend shape — the UI does not invent a per-item modifier link table.

### D7. Form validation strategy

Native HTML constraints (`required`, `min`, `maxLength`) + a tiny hand-written validator per form. No Zod / React Hook Form in this change. Rationale: same as D2 — one page, reversible later. Backend 422 responses surface as a single "Check the highlighted fields" message with the field list.

### D8. i18n keys

All UI strings live under `pages.menu.*` and `menu.common.*`. RU and EN files are updated in the same commit. No English fallback in JSX — `t('pages.menu.categories.deleteConfirm')` only.

## Risks / Trade-offs

- **[Risk]** No auth wired yet — every request will 401 until `staff-auth` lands. → **Mitigation:** the page renders a clear "Session expired, reload" on 401 and the `getAccessToken()` seam is a one-line change. Acceptance testing in this change uses a manually injected token in the browser devtools, documented in the task list.
- **[Risk]** Hand-written DTOs drift from `core_api.schemas.menu` as the backend evolves. → **Mitigation:** keep the DTO file small (≈50 lines), link to the Pydantic source with a comment, and plan to replace it wholesale with OpenAPI codegen in a later change (tracked in Open Questions).
- **[Risk]** No query cache means every dialog close re-fetches the item list. → **Mitigation:** acceptable at this scale (single shop, <200 items); re-fetches are bounded to O(one list per user action).
- **[Risk]** Creating an item, then failing partway through adding sizes, leaves a half-configured item. → **Mitigation:** the dialog clearly shows "Item created — add sizes below" after the first save; cancelling afterwards keeps the item (not a rollback). The admin can finish it later from the list. This is explicit, not a bug.
- **[Risk]** 409 on category delete (referenced by items) is a real scenario from `menu-admin-crud`. → **Mitigation:** the API client MUST surface 409 as a typed error and the UI MUST show a specific "This category still has items" message, not a generic one.
- **[Trade-off]** Hiding admin controls from barista duplicates server RBAC in the UI. This is intentional — the UI mirrors the matrix to keep the experience clean, but if they diverge the backend wins.

## Migration Plan

This change only adds / replaces files inside `web/admin/`. No DB migration, no backend deploy, no rollback script. Deploy is the standard admin SPA build. Rollback is `git revert` + rebuild — the placeholder `MenuPage.tsx` comes back and no data is affected.

## Open Questions

1. **OpenAPI codegen for the admin app** — when does it land? The hand-written DTOs in this change are explicitly temporary. Not blocking, but should be tracked as a follow-up.
2. **Global toast / notification primitive** — this change will need one for "Category deleted" / "Save failed" messages. Does one already exist anywhere we can reuse, or do we vendor a minimal shadcn `sonner` here? Defer to the task breakdown; if vendoring, keep it to a single file.
3. **Staff auth source of truth** — once `staff-auth` lands, where does `getAccessToken()` read from (memory store? context? zustand?)? This change commits to a single getter so the answer is a one-line change, but the team should decide before this change is archived to avoid two adjustments.
