## Context

**Affected modules:** `[web-admin]` only. No backend, worker, DB, shared-package, or redis changes.

Phase 4 delivery flow requires couriers to pick up available deliveries and progress them through the state machine in PDD §6.3. The backend endpoints are delivered by the parallel feature `delivery-assignment` and are already authorized against `role = courier` in core-api (INV-010). What is missing is the courier-facing UI.

Today `web/admin` has exactly one top-level shell: `Layout` (sidebar + header) wrapping six admin/barista routes under a single `ProtectedRoute` that only checks token presence. `LoginPage` calls `staffLogin`, which returns `{access_token, role}`, but only `access_token` is written to `localStorage` — `role` is dropped on the floor. There is no React-Query anywhere in the admin SPA; data is fetched with bare `authenticatedFetch` inside `useEffect`.

Constraints from AGENTS.md / OpenSpec rules:
- Frontend uses lighter TDD (IMPL → TEST → REFACTOR for UI; RED → GREEN → REFACTOR for logic/clients). Single OpenSpec change — no red/green split.
- Bilingual RU + EN, `react-i18next`.
- Mobile-first: courier works from a phone.
- RFC 2119 language in this doc.

## Goals / Non-Goals

**Goals:**
- Give couriers a functioning UI for the §6.3 lifecycle transitions (`Взять` → `Забрал` → `Доставлен`).
- Meet PDD §4.5 latency requirement: new available deliveries appear in the feed within ≤ 5 s.
- Establish the React-Query `refetchInterval: 5000` pattern for realtime-ish feeds, so the upcoming barista feed drops in without re-negotiation.
- Enforce INV-010 at the router level: a logged-in courier MUST NOT be able to navigate to admin/barista routes through the SPA.
- Persist `role` from login so the client can route correctly without re-decoding the JWT.

**Non-Goals:**
- Server-side role enforcement. Already done by `delivery-assignment`. Client checks are UX hints only.
- WebSocket / SSE push, Service Worker / PWA, offline cache, geolocation, route planning.
- A barista feed at `/barista`. This change only establishes the pattern.
- Replacing `useNotifier` with sonner or any third-party toast lib.
- JWT claim decoding on the client (we persist `role` separately; we do NOT parse JWT payload).

## Decisions

### D1. React Query over setInterval + useEffect

`@tanstack/react-query ^5` SHALL be added to `web/admin/package.json` and configured in `main.tsx` with a single `QueryClient` wrapped by `QueryClientProvider`.

Both courier queries SHALL use `useQuery({ queryKey, queryFn, refetchInterval: 5000, refetchIntervalInBackground: false })`. Mutations (`take`, `pickup`, `deliver`) SHALL use `useMutation` and invalidate the relevant query on success (`queryClient.invalidateQueries({ queryKey: [...] })`).

**Why over a hand-rolled `setInterval`:** React Query de-duplicates in-flight requests, pauses polling when the tab is hidden (`refetchIntervalInBackground: false`), cancels stale requests on unmount, and gives us an ergonomic mutation → invalidate cycle for the 409-retake case. Rolling this by hand is 30+ lines of state per hook and duplicates the barista feed's future needs.

**Alternatives considered:**
- **SWR:** similar API, smaller bundle, but no built-in mutation invalidation helpers and weaker TS story. Rejected.
- **Hand-rolled `useInterval`:** smallest diff, but doesn't de-duplicate and would need its own tab-visibility handling. Rejected because we pay this cost again for the barista feed.

### D2. Persist role in localStorage next to access_token

`role` SHALL be persisted as a separate `localStorage` key `staffRole` with the set `{'admin', 'barista', 'courier'}`. A new module `web/admin/src/lib/auth.ts` SHALL expose `getRole()`, `setRole(role)`, `clearRole()`, and a pure helper `canAccess(route, role)`.

`staffLogin` MUST continue to return `{access_token, role}`. `LoginPage` MUST call `setRole(result.role)` immediately after `setAccessToken(result.access_token)`. `logout()` in `client.ts` MUST call `clearRole()` in addition to `clearAccessToken()`.

**Why a separate key (not a JSON blob):** keeps the blast radius of each helper minimal; existing `getAccessToken`/`setAccessToken` callers do not change; DevTools inspection stays human-readable.

**Why not decode the JWT:** the JWT payload is not a public API of `staff-auth` — it can change shape without breaking the auth contract. `staffLogin`'s `{role}` field IS a public API (spec `admin-auth-ui`). Coupling to it is safer than parsing claims.

**Not authoritative:** `role` from `localStorage` is an untrusted client hint per INV-010. Every backend call MUST still be authorized server-side, which it already is.

### D3. Post-login redirect by role

After a successful `staffLogin`, `LoginPage` SHALL:
- If `result.role === 'courier'` → navigate to `/courier` (ignore any `returnUrl`, since a courier has no business visiting admin routes).
- Otherwise → navigate to `returnUrl ?? '/'` as today.

**Rationale for ignoring returnUrl for couriers:** `returnUrl` is set by `ProtectedRoute` when an unauthenticated user hits a protected route. A courier should never have ended up on `/menu` in the first place; honoring a returnUrl of `/menu` would just bounce them through the role-gate below and waste a round-trip.

### D4. Router structure: two protected groups

`App.tsx` SHALL declare routes in this shape:

```
<BrowserRouter basename="/admin">
  <Routes>
    <Route path="/login" element={<LoginPage />} />

    <Route element={<ProtectedRoute allowedRoles={['admin', 'barista']}><Layout /></ProtectedRoute>}>
      <Route index element={<DashboardPage />} />
      <Route path="orders" element={<OrdersPage />} />
      ... other existing admin routes ...
    </Route>

    <Route element={<ProtectedRoute allowedRoles={['admin', 'courier']}><CourierShell /></ProtectedRoute>}>
      <Route path="courier" element={<CourierPage />} />
    </Route>

    <Route path="*" element={<NotFoundPage />} />
  </Routes>
</BrowserRouter>
```

`ProtectedRoute` SHALL accept an optional `allowedRoles?: StaffRole[]` prop. Behavior:
- No token → redirect to `/login?returnUrl=<path>` (today's behavior, unchanged).
- Token present, `allowedRoles` omitted → render children (today's behavior, unchanged — keeps backwards compatibility for any future route that does not care about role).
- Token present, `allowedRoles` set, `getRole()` not in `allowedRoles` → redirect:
  - If `getRole() === 'courier'` → `/courier`
  - Else → `/` (dashboard — admin's default)

`CourierShell` is a trivial layout wrapper (no sidebar, no nav) that only renders the `LanguageSwitcher` and `NotificationList`. Admins still get the full `Layout` with sidebar when they land on `/courier` — wait, **correction:** since `Layout` contains the sidebar that exposes menu/orders/etc, and admins MAY navigate freely, admins landing on `/courier` get `CourierShell` too. They can still return to `/` via URL; we do NOT add a courier link to the admin sidebar in this change.

### D5. API client shape — hand-written, mirrors menu.ts

`web/admin/src/api/courier.ts` SHALL be hand-written (OpenAPI codegen is not set up in this repo yet — see `menu.ts` header comment). Types MUST mirror `services/core-api/src/core_api/schemas/courier.py` from `delivery-assignment`. Endpoints:

```
GET  /api/v1/courier/assignments/available  → CourierAssignmentResponse[]
POST /api/v1/courier/assignments/{id}/take  → CourierAssignmentResponse  (409 on conflict)
GET  /api/v1/courier/assignments/mine       → CourierAssignmentResponse[]
POST /api/v1/courier/assignments/{id}/pickup → CourierAssignmentResponse
POST /api/v1/courier/assignments/{id}/deliver → CourierAssignmentResponse
```

All calls go through `authenticatedFetch` and throw `ApiError` on non-2xx, matching `menu.ts`. The response shape is speculative until `delivery-assignment` lands — at minimum it MUST include `id`, `order_id`, `status`, `delivery_address`, `total`, `requested_time`. If `delivery-assignment` ships different field names, this file is updated in the integration commit, not in this change.

### D6. 409 conflict handling via the existing notifier

`POST /take` receiving HTTP 409 (another courier grabbed it first — see §6.3 optimistic-lock note) SHALL:
1. Trigger `notify(t('courier.errors.alreadyTaken'), 'error')` via the `useNotifier` hook.
2. Invalidate the `['courier', 'available']` query so the stale card disappears.

No custom error types or per-button error state. The existing `NotificationList` auto-dismisses after 4 s.

### D7. Mobile-first layout

- Cards: full-width on `sm`, two columns on `md+`. (Default breakpoint: Tailwind `md` = 768px. Couriers on phones stay at `sm`.)
- Primary action button per card: `min-h-12`, full card-width on `sm`, aligned-right on `md+`.
- Per card, display only: street address (from `delivery_address.address_line`), total in roubles (kopecks / 100), requested time formatted `HH:mm` in browser locale, and the one status-appropriate action.
- No sidebar, no nav tabs at the top — just two pill tabs ("Доступные" / "Мои") on a single-line row at the top of the page.

### D8. State transitions covered (PDD §6.3)

This UI drives exactly three transitions; core-api is the actor that changes state, but the UI is the trigger surface:

| From              | To                | UI action            | Endpoint                                  |
|-------------------|-------------------|----------------------|-------------------------------------------|
| AWAITING_COURIER  | COURIER_ASSIGNED  | "Взять" button       | POST `/api/v1/courier/assignments/{id}/take`    |
| COURIER_ASSIGNED  | PICKED_UP         | "Забрал" button      | POST `/api/v1/courier/assignments/{id}/pickup`  |
| PICKED_UP         | DELIVERED         | "Доставлен" button   | POST `/api/v1/courier/assignments/{id}/deliver` |

Forbidden transitions from §6.3 (`COURIER_ASSIGNED → AWAITING_COURIER`, `PICKED_UP → CANCELLED`, etc.) are not exposed as UI actions — there are no buttons for them.

## Risks / Trade-offs

- **[Risk]** `delivery-assignment` may land with different field names than we assume in `courier.ts`. → **Mitigation:** the client is a thin hand-written layer; the integration PR that merges `delivery-assignment` into `delivery` branch owns the field-name reconciliation (one-line type changes). We do NOT block this change on that merge.
- **[Risk]** Persisted `role` diverges from server-side truth if an admin demotes a courier mid-session. → **Mitigation:** acceptable — the next API call returns 401/403 and `authenticatedFetch` redirects to `/login`. INV-010 is still enforced server-side.
- **[Risk]** 5-second polling on a locked-phone tab wastes battery. → **Mitigation:** `refetchIntervalInBackground: false` pauses polling when the tab is hidden; resumes on focus.
- **[Risk]** React-Query bundle adds ~10 KB gzipped to `web/admin`. → **Trade-off accepted:** barista feed (next Phase 4 feature) and any future realtime-ish view amortize this; rolling our own polling de-dup is more long-term code than the dep.
- **[Trade-off]** Couriers and admins both land in `/courier` via the same route. An admin cannot get back to the dashboard through in-UI navigation — they must retype the URL. Acceptable: this is rare (admin debugging), and we do not want a courier-visible nav link back to `/`.
- **[Risk]** `returnUrl` that points at a protected admin route will silently drop for couriers. → **Mitigation:** documented in D3; the `LoginPage` spec scenarios cover it.

## Migration Plan

- Forward-only. No DB, no config, no env-var changes.
- Deploy via the normal Vite build; nginx already serves `/admin/*`.
- Manual test checklist (added to `docs/phase3_manual_test_scenarios.md` as a Phase 4 addendum or to a new phase-4 doc — out of scope for this change, will be handled in the `delivery` merge commit):
  - Log in as admin → land on `/`, sidebar visible, `/courier` reachable via URL, deliveries render.
  - Log in as courier → land on `/courier` automatically, no sidebar, two tabs.
  - Tab "Доступные" shows cards, polls every 5 s, "Взять" moves card to "Мои".
  - Two sessions both hit "Взять" on the same assignment → winner keeps the card, loser sees the toast, the card disappears from "Доступные".
  - Courier navigates directly to `/menu` → redirected to `/courier`.
- Rollback: revert the single merge commit. No data migration to undo.

## Open Questions

None blocking. The field-name reconciliation with `delivery-assignment` (noted under Risks) is scheduled for the merge commit, not this change.
