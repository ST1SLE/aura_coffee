## Why

Phase 4 ships own-courier delivery (PDD §7.1). The backend Delivery Assignment lifecycle (§6.3) and the courier-side endpoints (`/api/v1/courier/assignments/available`, `/take`, `/mine`, `/pickup`, `/deliver`) are delivered under the parallel `delivery-assignment` feature, but couriers have no UI to use them. Barista/admin views run the whole ordering flow today; the courier role exists in `staff_accounts.role` but, on login, a courier lands in an admin UI they are forbidden to see (INV-010).

This change adds the first operator-facing realtime feed in `web/admin` — a mobile-first `/courier` view with ≤ 5 s latency (PDD §4.5). It also establishes the React-Query-with-`refetchInterval` pattern that the upcoming barista feed will reuse, so we only negotiate the polling contract once.

## What Changes

- Introduce a new `/courier` route in the admin SPA with two tabs — "Доступные" (available, unassigned deliveries) and "Мои" (assignments taken by the current courier).
- On successful staff login, persist `role` alongside `access_token`; redirect couriers to `/courier` and keep admin/barista on `/`.
- Restrict `/courier` to `role ∈ {courier, admin}` at the router level (UX hint only — authoritative check stays in core-api per INV-010).
- Hide the admin sidebar/header chrome for couriers so they see only the courier view (INV-010 — "Курьер НЕ ДОЛЖЕН видеть меню/заказы/настройки").
- Add `@tanstack/react-query` to `web/admin` and wrap the app in `QueryClientProvider`; use `useQuery({ refetchInterval: 5000 })` for both lists.
- Add `web/admin/src/api/courier.ts` — typed client mirroring `services/core-api/src/core_api/schemas/courier.py` (hand-written, same convention as `menu.ts`).
- Use the existing `useNotifier` / `NotificationList` for the "Заказ уже взят другим курьером" (HTTP 409) toast on `POST /take`; refetch the available list afterwards.
- Add bilingual strings under `courier.*` in `web/admin/src/i18n/locales/{ru,en}/common.json`.
- Mobile-first layout: single-column, large tap targets, minimal per-card info (address, total, requested time, one primary action button).

## Capabilities

### New Capabilities

- `courier-panel-ui`: the `/courier` page, its two tabs, the `courier.ts` API client, the React-Query provider, the 5-second polling contract, and the courier-scoped localization. Covers only the admin-SPA surface.

### Modified Capabilities

- `admin-auth-ui`: `staffLogin` result's `role` field MUST be persisted to `localStorage`; new `getRole()`/`setRole()`/`clearRole()` helpers; `logout()` clears both token and role; the login page MUST redirect to `/courier` when `role === 'courier'`.
- `frontend-routing`: add a protected `/courier` route rendered outside the main `Layout`; gate existing protected routes so a logged-in courier who navigates to `/`, `/orders`, `/menu`, `/users`, `/promos`, `/settings` is redirected to `/courier`.

## Impact

- **Code:** `web/admin/src/App.tsx`, `web/admin/src/pages/Courier/`, `web/admin/src/pages/Login/LoginPage.tsx`, `web/admin/src/components/ProtectedRoute.tsx`, `web/admin/src/lib/auth.ts` (new), `web/admin/src/api/client.ts`, `web/admin/src/api/courier.ts` (new), `web/admin/src/main.tsx` (QueryClientProvider), `web/admin/src/i18n/locales/{ru,en}/common.json`.
- **Dependencies:** `@tanstack/react-query ^5` added to `web/admin/package.json`.
- **APIs:** Consumes, does not define, `GET /api/v1/courier/assignments/available`, `POST /api/v1/courier/assignments/{id}/take`, `GET /api/v1/courier/assignments/mine`, `POST /api/v1/courier/assignments/{id}/pickup`, `POST /api/v1/courier/assignments/{id}/deliver` (owned by `delivery-assignment`).
- **No backend, worker, DB, or shared-package changes.**
- **MVP phase:** Phase 4 — Delivery (PDD §7.1).
- **Non-Goals:**
  - WebSocket/SSE push — out of scope; 5-second polling is the contract for Phase 4.
  - Barista feed at `/barista` — this change only establishes the pattern; the barista view is a separate feature.
  - Courier geolocation, route planning, ETAs, customer-facing courier tracking — Phase 4+ roadmap, not this change.
  - Offline/PWA support — couriers work online from a phone on mobile data; no service worker added here.
  - Role-based authorization on the server — already enforced by `delivery-assignment`; this change does NOT modify core-api.
  - Replacing `useNotifier` with a third-party toast library (e.g. sonner) — the existing notifier is sufficient for this single toast.
