## Why

After OTP login (Tests 1-3 pass), the user lands on `/` but has no way to navigate to `/profile`, `/orders`, `/cart` or log out on desktop — the bottom nav has `md:hidden` and no desktop equivalent exists. This blocks Tests 4-7 (protected routes, profile, logout, error handling). On mobile the bottom nav is visible but lacks a logout action and has no safe-area padding for iPhones with home indicator.

## What Changes

- **[web-customer]** Add desktop horizontal nav in `Layout` header — links to Menu, Cart, Orders, Profile + logout button. Visible at `md:` breakpoint and above (`hidden md:flex`).
- **[web-customer]** Add logout button to `ProfilePage` — mobile users reach profile via bottom nav but need a way to sign out from there.
- **[web-customer]** Add `viewport-fit=cover` to `index.html` and safe-area bottom padding to the mobile bottom nav — prevents home indicator overlap on iPhone.
- **[web-customer]** Increase tap targets in mobile bottom nav — minimum 44px touch area per Apple HIG.
- **[web-customer]** Add `nav.logout` translation key to both locales (`"Выйти"` / `"Sign Out"`).

## Non-Goals

- No redesign of the header/brand area or addition of icons — text links only, consistent with current style
- No hamburger/drawer menu — desktop gets inline links, mobile keeps bottom nav
- No changes to auth logic, token handling, or ProtectedRoute — those already work correctly
- No new pages or routes — all target pages (profile, orders, cart) already exist

## MVP Phase

Phase 1 (Auth) — completes the post-login navigation that makes the auth flow end-to-end testable.

## Capabilities

### New Capabilities
<!-- None — this adds UI navigation to existing routes and auth functions -->

### Modified Capabilities
- `web-customer`: Layout gains desktop nav with logout; ProfilePage gains logout button; mobile nav gains safe-area support and larger tap targets

## Impact

- **Code:** `web/customer/src/components/Layout.tsx`, `web/customer/src/pages/ProfilePage.tsx`, `web/customer/index.html`, `web/customer/src/i18n/locales/ru/common.json`, `web/customer/src/i18n/locales/en/common.json`
- **Risk:** Minimal — purely UI additions, no business logic changes
