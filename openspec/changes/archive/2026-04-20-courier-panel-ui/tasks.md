## 1. Dependencies & bootstrap

- [x] 1.1 [web-admin] PREREQ: Add `@tanstack/react-query ^5` to `dependencies` in `web/admin/package.json` (run `npm install` inside the admin container or host venv; commit the updated `package.json` and `package-lock.json`).
- [x] 1.2 [web-admin] IMPL: Wrap `<App />` in `<QueryClientProvider>` in `web/admin/src/main.tsx` — instantiate a single `QueryClient` with no global `refetchInterval`.

## 2. Auth: role storage helpers

- [x] 2.1 [web-admin] RED: Add `web/admin/src/lib/auth.test.ts` with tests for `getRole`, `setRole`, `clearRole` covering: (a) `setRole('courier')` persists to `localStorage.staffRole`; (b) `clearRole()` removes the key; (c) `getRole()` returns `null` when unset; (d) TypeScript narrowing check (`getRole()` return type is `StaffRole | null`). Tests MUST fail with `Cannot find module '@/lib/auth'`.
- [x] 2.2 [web-admin] GREEN: Create `web/admin/src/lib/auth.ts` exporting `StaffRole`, `getRole`, `setRole`, `clearRole` → passes 2.1.
- [x] 2.3 [web-admin] RED: Extend `web/admin/src/api/client.test.ts` with a new test `logout clears both accessToken and staffRole` that asserts `localStorage.getItem('staffRole') === null` after `logout()`. Test MUST fail against current `logout()` (which only clears accessToken).
- [x] 2.4 [web-admin] GREEN: Update `web/admin/src/api/client.ts` `logout()` to also call `clearRole()` (import from `@/lib/auth`) → passes 2.3.

## 3. Auth: login page role-based redirect

- [x] 3.1 [web-admin] RED: Extend `web/admin/src/pages/Login/LoginPage.test.tsx` with a test `successful courier login navigates to /courier` that mocks `staffLogin` returning `role: 'courier'` and asserts the router navigated to `/courier`. MUST fail against current login page (always navigates to `returnUrl ?? '/'`).
- [x] 3.2 [web-admin] RED: Add to `LoginPage.test.tsx` a test `courier login ignores returnUrl` — when URL is `?returnUrl=%2Fmenu` and `role: 'courier'`, assert navigate was called with `/courier` (NOT `/menu`). MUST fail.
- [x] 3.3 [web-admin] RED: Add to `LoginPage.test.tsx` a test `successful login calls setRole with returned role` that asserts `setRole` (spied from `@/lib/auth`) was called with the exact role string from the mocked response. MUST fail.
- [x] 3.4 [web-admin] GREEN: Update `web/admin/src/pages/Login/LoginPage.tsx` to import `setRole` from `@/lib/auth`, call it after `setAccessToken`, and navigate to `/courier` when `result.role === 'courier'` (ignoring `returnUrl`) → passes 3.1, 3.2, 3.3.
- [x] 3.5 [web-admin] REFACTOR: Review `LoginPage.tsx` for navigation branch clarity; extract the role-based redirect target into a local const if the conditional grows beyond a ternary.

## 4. Routing: ProtectedRoute role gating

- [x] 4.1 [web-admin] RED: Extend `web/admin/src/components/ProtectedRoute.test.tsx` with a test `courier role on admin-only route redirects to /courier` — render `<ProtectedRoute allowedRoles={['admin','barista']}>...</ProtectedRoute>` with `localStorage.staffRole='courier'`, assert `<Navigate to="/courier" replace>`. MUST fail (prop not supported).
- [x] 4.2 [web-admin] RED: Add test `barista role on courier-only route redirects to /` — `allowedRoles={['admin','courier']}` with `staffRole='barista'`, asserts `<Navigate to="/" replace>`. MUST fail.
- [x] 4.3 [web-admin] RED: Add test `admin role allowed on both route groups` — verifies admin passes `['admin','barista']` AND passes `['admin','courier']` (two assertions in two renders). MUST fail.
- [x] 4.4 [web-admin] RED: Add test `allowedRoles omitted preserves legacy behavior` — any token renders children regardless of role. MUST pass already for non-null token with no allowedRoles (legacy behavior preserved) — this test is kept as a regression guard.
- [x] 4.5 [web-admin] RED: Add test `null role with allowedRoles set falls through to /` — asserts that a token without `staffRole` in localStorage redirects to `/`. MUST fail.
- [x] 4.6 [web-admin] RED: Add test `no token redirects to login even when allowedRoles set` — asserts the no-token branch short-circuits role checking. MUST fail (or pass as regression guard).
- [x] 4.7 [web-admin] GREEN: Update `web/admin/src/components/ProtectedRoute.tsx` to accept optional `allowedRoles?: StaffRole[]` prop and implement the role-redirect rules per spec → passes 4.1–4.6.
- [x] 4.8 [web-admin] REFACTOR: Inline small doc comment on the role-redirect helper noting that this is a UX hint, authoritative check is in core-api (INV-010).

## 5. Routing: /courier route wiring

- [x] 5.1 [web-admin] IMPL: Create `web/admin/src/pages/Courier/CourierShell.tsx` — a layout component that renders only `<LanguageSwitcher />`, `<NotificationList />`, and `<Outlet />` (no sidebar, no nav).
- [x] 5.2 [web-admin] IMPL: Update `web/admin/src/App.tsx` to add `allowedRoles={['admin','barista']}` on the existing `ProtectedRoute` wrapper around `Layout`, and add a second protected group `ProtectedRoute allowedRoles={['admin','courier']}` wrapping `CourierShell` with a nested `<Route path="courier" element={<CourierPage />} />`.
- [x] 5.3 [web-admin] TEST: Add `web/admin/src/App.test.tsx` scenario (or new file) verifying that `/admin/courier` with `staffRole='courier'` renders the courier page chrome (no sidebar), and that `/admin/menu` with `staffRole='courier'` redirects to `/admin/courier`.

## 6. API client: courier endpoints

- [x] 6.1 [web-admin] RED: Create `web/admin/src/api/courier.test.ts` with tests for the five functions: `listAvailable`, `takeAssignment`, `listMine`, `pickupAssignment`, `deliverAssignment`. Assertions: (a) request path and method; (b) Authorization header present; (c) 409 on `takeAssignment` throws `ApiError` with `status === 409`; (d) non-2xx generally throws `ApiError`. MUST fail with `Cannot find module '@/api/courier'`.
- [x] 6.2 [web-admin] GREEN: Create `web/admin/src/api/courier.ts` exporting the five functions and the `CourierAssignmentResponse` type. Use `authenticatedFetch`, mirror `menu.ts` shape → passes 6.1.
- [x] 6.3 [web-admin] REFACTOR: Extract shared helpers (`json`, `post`) only if they are not already exposed from `client.ts` or `menu.ts`; otherwise reuse in-place. No behavior change.

## 7. Courier page: shell, tabs, Available feed

- [x] 7.1 [web-admin] IMPL: Create `web/admin/src/pages/Courier/CourierPage.tsx` scaffold — two pill tabs controlled by local state (`'available' | 'mine'`), default `'available'`; renders the active tab's body component.
- [x] 7.2 [web-admin] IMPL: Create `web/admin/src/pages/Courier/AvailableTab.tsx` that calls `useQuery({ queryKey: ['courier','available'], queryFn: listAvailable, refetchInterval: 5000, refetchIntervalInBackground: false })` and renders one `AssignmentCard` per item; shows empty-state `courier.empty.available` when list is empty.
- [x] 7.3 [web-admin] IMPL: Create `web/admin/src/pages/Courier/AssignmentCard.tsx` — a pure presentation component rendering address, total (kopecks→roubles), requested time (HH:mm or localized "ASAP"), and a slot for a primary action button. Mobile-first classes: `w-full md:w-1/2`, `min-h-12` on buttons.
- [x] 7.4 [web-admin] IMPL: Wire the "Взять" button on cards in `AvailableTab` via `useMutation({ mutationFn: takeAssignment })`. On `onSuccess` invalidate `['courier','available']` AND `['courier','mine']`. On `onError` if `err instanceof ApiError && err.status === 409` call `notify(t('courier.errors.alreadyTaken'), 'error')` and invalidate `['courier','available']`.
- [x] 7.5 [web-admin] TEST: Add `web/admin/src/pages/Courier/AvailableTab.test.tsx` — mocks `listAvailable` and `takeAssignment`; asserts: (a) cards render for fetched items; (b) clicking "Взять" calls `takeAssignment` with the correct id; (c) 409 response emits a toast with the localized string; (d) 5-second `refetchInterval` is wired (inspect `useQuery` args).
- [x] 7.6 [web-admin] REFACTOR: Review `AvailableTab` / `AssignmentCard` seam — if any presentation leaks into `AvailableTab`, move it to `AssignmentCard`.

## 8. Courier page: Mine tab

- [x] 8.1 [web-admin] IMPL: Create `web/admin/src/pages/Courier/MineTab.tsx` that calls `useQuery({ queryKey: ['courier','mine'], queryFn: listMine, refetchInterval: 5000, refetchIntervalInBackground: false })` and renders one `AssignmentCard` per item with status-driven action button: `COURIER_ASSIGNED` → "Забрал" (calls `pickupAssignment`); `PICKED_UP` → "Доставлен" (calls `deliverAssignment`); other statuses → no button.
- [x] 8.2 [web-admin] IMPL: Wire both `useMutation`s to invalidate `['courier','mine']` on `onSuccess`.
- [x] 8.3 [web-admin] TEST: Add `web/admin/src/pages/Courier/MineTab.test.tsx` — asserts: (a) `COURIER_ASSIGNED` card shows "Забрал" and calls `pickupAssignment` on click; (b) `PICKED_UP` card shows "Доставлен" and calls `deliverAssignment` on click; (c) `DELIVERED` / `CANCELLED` cards render no action button.
- [x] 8.4 [web-admin] REFACTOR: Review `AvailableTab` vs `MineTab` for duplication of the `useQuery` wrapper and button-rendering logic; extract only if duplication is clear (≥ 2 identical blocks), otherwise leave.

## 9. Localization

- [x] 9.1 [web-admin] IMPL: Extend `web/admin/src/i18n/locales/ru/common.json` with the `courier` namespace (tabs, actions, empty states, errors, field labels).
- [x] 9.2 [web-admin] IMPL: Extend `web/admin/src/i18n/locales/en/common.json` with the same keys (English strings).
- [x] 9.3 [web-admin] TEST: Extend `web/admin/src/i18n/locales/__tests__/` (existing fixture) with a test that asserts every `courier.*` key resolves to a non-empty string under both `lng: 'ru'` and `lng: 'en'`.

## 10. Verification

- [x] 10.1 [web-admin] VERIFY: Run `npm test` inside `web/admin/` (or the equivalent Docker command) and confirm ALL tests pass — existing suite plus the new courier-* and auth tests.
- [x] 10.2 [web-admin] VERIFY: Run `npm run build` inside `web/admin/` to confirm TypeScript types compile cleanly (no `any` regressions in new code).
- [ ] 10.3 [web-admin] VERIFY: Start the dev server (`./scripts/up.sh`) and manually walk: (a) log in as admin → `/`, sidebar visible, `/admin/courier` renders no-sidebar shell; (b) log in as courier (test credentials from `database/seeds/`) → auto-redirect to `/admin/courier`; (c) navigate manually to `/admin/menu` as courier → redirected to `/admin/courier`. Record findings in the PR description.
