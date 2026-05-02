# Aura Customer Redesign Plan

Created: 2026-05-02

## Direction

Aura customer web should move from the current dark Drinkit-derived shell to a
soft botanical ordering utility:

- cream working canvas
- espresso text and icons
- sage/olive as brand field and primary action family
- caramel/pastry accents for appetite and emphasis
- product media as the main merchandising layer

The design anchor is `docs/design/aura_coffee_color_reference.pdf`; the
implementation guidance is `docs/design/deep-research-report.md`.

## Scope

Target module: `web/customer`.

Primary files:

- `web/customer/src/index.css`
- `web/customer/tailwind.config.ts`
- `web/customer/src/components/ui/button.tsx`
- `web/customer/src/components/Layout.tsx`
- `web/customer/src/pages/Menu/*`
- `web/customer/src/pages/Cart/*`
- `web/customer/src/pages/CheckoutPage.tsx`
- `web/customer/src/pages/OrdersPage.tsx`
- `web/customer/src/pages/OrderDetailPage.tsx`
- `web/customer/src/pages/Profile*`
- `web/customer/src/components/auth/*`
- `web/customer/src/components/AddressAutocomplete/*`

Out of scope for this visual redesign unless a later PDD/GRACE packet explicitly
changes product behavior:

- grouped modifier categories
- per-modifier quantities
- new loyalty/referral/rating/gift behavior
- new order/payment states
- client-owned pricing or delivery calculations
- direct third-party media, SMS, YuKassa, or Yandex Maps calls from the frontend

## Current Repo Corrections

The deep research report contains two assumptions that need repo-specific
correction before implementation:

1. Tailwind is v3.4, not v4. Use the existing HSL CSS-variable token layer and
   `tailwind.config.ts` semantic mappings; do not introduce Tailwind v4
   `@theme`.
2. The menu media contract already exists. PDD and code include
   `media_type`, `media_url`, `media_poster_url`, legacy `image_url`, and the
   customer `MenuMedia` component. This plan refines visual usage; it does not
   re-add backend media support.

## Required Invariants

- PDD §4.4: customer frontend is mobile-first responsive web, bilingual RU/EN,
  and displays server-owned prices and status.
- PDD §5.2 notes: menu media is presentation only and does not affect pricing,
  availability, cart validation, payment, or order snapshots.
- PDD §7.2-§7.4: checkout totals, delivery fee, delivery radius, minimum order,
  promo, and loyalty math remain server-owned.
- INV-002: frontend auth checks are UX only; backend enforces authorization.
- INV-013: do not log phone numbers, addresses, comments, tokens, or other PII.
- INV-014: order/cart item prices are server snapshots; frontend does not
  recompute business totals.
- INV-016: do not invent states or transitions.

## Design Decisions

- Typography: use self-hosted `Onest` for headings, category rail, chips, and
  CTAs; self-hosted `Inter` for body, forms, checkout, prices, and numeric
  surfaces.
- Palette: use warm semantic CSS variables rather than hard-coded component
  colors.
- Sage rule: use dark espresso text on PDF-like poster sage; use white text only
  on deeper olive action colors.
- Radius: keep the existing 8px default radius for app surfaces and use pills
  only for chips, category rails, cart affordances, and icon actions.
- Motion/media: keep existing `MenuMedia` reduced-motion and poster fallback
  behavior. Do not autoplay video across the whole catalog.

## Packet Plan

### Packet 0 - Plan Artifact

Status: complete

Write this execution plan and identify repo-specific corrections before code.

Acceptance:

- plan lives in `docs/design/aura-customer-redesign-plan.md`
- plan lists scope, invariants, packets, verification, risks, and rollback

### Packet 1 - Token And Font Foundation

Status: complete

Files:

- `web/customer/package.json`
- `web/customer/package-lock.json`
- `web/customer/src/main.tsx`
- `web/customer/src/index.css`
- `web/customer/tailwind.config.ts`
- `web/customer/src/components/ui/button.tsx`

Steps:

1. Add self-hosted `@fontsource/onest` and `@fontsource/inter`.
2. Import required font weights in `main.tsx`.
3. Replace dark HSL tokens with cream, espresso, sage, caramel, and warm borders.
4. Remove `color-scheme: dark`; set `color-scheme: light`.
5. Add font-family and numeric utility tokens through Tailwind v3 extension.
6. Rework `.aura-surface` and `.aura-surface-soft` to light warm surfaces.
7. Adjust button primitive hover/focus treatment to fit the new tokens.

Acceptance:

- global customer UI no longer encodes the dark/yellow palette
- Onest and Inter are available without external runtime font requests
- primary button contrast uses deep olive with white text
- body text and form surfaces use high-contrast espresso on cream/warm surfaces
- no route, API payload, auth, cart, pricing, checkout, or state behavior changes

Verification:

- `cd web/customer && npm run typecheck`
- `cd web/customer && npm test`
- `cd web/customer && npm run build`
- `cd web/customer && npm run lint`
- Follow-up optimization: broad Fontsource CSS imports were replaced with
  explicit Latin/Cyrillic `@font-face` declarations backed by Fontsource assets,
  reducing the production CSS/font asset set while preserving RU/EN coverage.

### Packet 2 - App Shell And Navigation

Status: complete

Files:

- `web/customer/src/components/Layout.tsx`
- `web/customer/src/components/LanguageSwitcher.tsx`

Steps:

1. Update module contract language from dark shell to soft botanical shell.
2. Restyle header as a compact brand/ordering context surface.
3. Restyle desktop nav, mobile bottom nav, and floating cart with new tokens.
4. Preserve protected-route layout, logout side effect, route paths, and cart
   count behavior.

Acceptance:

- shell supports 320px mobile without text overlap
- cart affordance remains safe-area aware
- active nav and badge colors meet contrast

Verification:

- `cd web/customer && npm test -- src/components/Layout.test.tsx`
- `cd web/customer && npm run typecheck`
- `cd web/customer && npm test`
- `cd web/customer && npm run build`
- `cd web/customer && npm run lint`

### Packet 3 - Menu Browsing

Status: complete

Files:

- `web/customer/src/pages/Menu/MenuPage.tsx`
- `web/customer/src/pages/Menu/MenuItemCard.tsx`
- `web/customer/src/pages/Menu/MenuMedia.tsx`

Steps:

1. Replace dark hero block with a compact ordering-first intro.
2. Restyle sticky category rail with deep-sage active chips and warm inactive
   chips.
3. Rework cards to media-first warm surfaces with stable price and add controls.
4. Keep categories API-owned and menu media fallback behavior intact.

Acceptance:

- no invented categories or product metadata
- sold-out / unavailable / finite inventory states remain visible
- product names fit in RU and EN at mobile widths

Verification:

- `cd web/customer && npm test -- src/pages/Menu/MenuPage.test.tsx src/pages/Menu/MenuItemCard.test.tsx src/pages/Menu/MenuMedia.test.tsx`
- `cd web/customer && npm run typecheck`
- `cd web/customer && npm test`
- `cd web/customer && npm run build`
- `cd web/customer && npm run lint`

### Packet 4 - Item Detail And Modifiers

Status: complete

Files:

- `web/customer/src/pages/Menu/ItemDetail.tsx`

Steps:

1. Restyle modal/sheet with light surfaces and controlled media hero.
2. Restyle size, modifier, quantity, toast, and bottom add-to-cart controls.
3. Keep current flat modifier model and display-only price behavior.

Acceptance:

- add-to-cart payload remains unchanged
- quantity remains UX-capped only; server remains source of truth
- no grouped modifiers or modifier quantities added

Verification:

- `cd web/customer && npm test -- src/pages/Menu/ItemDetail.test.tsx`
- `cd web/customer && npm run typecheck`
- `cd web/customer && npm test`
- `cd web/customer && npm run build`
- `cd web/customer && npm run lint`

### Packet 5 - Cart And Checkout

Status: complete

Files:

- `web/customer/src/pages/Cart/*`
- `web/customer/src/pages/CheckoutPage.tsx`
- `web/customer/src/components/AddressAutocomplete/*`

Steps:

1. Restyle cart header, lines, empty state, repeat-order notices, and sticky
   subtotal.
2. Restyle checkout as a sectioned warm surface.
3. Preserve server-owned estimates, create-order payloads, typed-address geocode
   flow, saved-address flow, and localized backend errors.

Acceptance:

- no client-owned business totals
- pickup/delivery mode remains explicit
- address/comment PII is not logged
- long delivery errors and RU labels do not overlap

Verification:

- `cd web/customer && npm test -- src/pages/Cart/CartPage.test.tsx src/pages/Cart/CartLine.test.tsx src/pages/CheckoutPage.test.tsx src/components/AddressAutocomplete/AddressAutocomplete.test.tsx`
- `cd web/customer && npm run typecheck`
- `cd web/customer && npm test`
- `cd web/customer && npm run build`
- `cd web/customer && npm run lint`

### Packet 6 - Orders, Profile, Auth, And Residual Raw Colors

Status: complete

Files:

- `web/customer/src/pages/OrdersPage.tsx`
- `web/customer/src/pages/OrderDetailPage.tsx`
- `web/customer/src/pages/Profile*`
- `web/customer/src/pages/LoginPage.tsx`
- `web/customer/src/pages/VerifyPage.tsx`
- `web/customer/src/components/auth/*`
- `web/customer/src/auth/ProtectedRoute.tsx`

Steps:

1. Replace raw `gray-*`, `red-*`, and dark-only border classes with semantic
   tokens where appropriate.
2. Restyle order timeline, status badges, loyalty card, profile forms, OTP, and
   login surfaces.
3. Preserve polling/status behavior, OTP flow, profile/address APIs, and PII
   boundaries.

Acceptance:

- customer flow is visually coherent end to end
- order states match PDD only
- auth and profile forms remain bilingual and accessible

Verification:

- `cd web/customer && npm test -- src/pages/LoginPage.test.tsx src/pages/VerifyPage.test.tsx src/pages/VerifyPage.otp409.test.tsx src/components/auth/PhoneInput.test.tsx src/components/auth/OTPInput.test.tsx src/auth/ProtectedRoute.test.tsx src/pages/OrdersPage.test.tsx src/pages/OrderDetailPage.test.tsx src/pages/ProfilePage.test.tsx src/pages/Profile/LoyaltyCard.test.tsx src/pages/Profile/Loyalty/LoyaltyPage.test.tsx src/pages/Profile/Loyalty/TransactionRow.test.tsx src/pages/Profile/Addresses/AddressesPage.test.tsx src/pages/Profile/Addresses/AddressForm.test.tsx`
- `cd web/customer && npm run typecheck`
- `cd web/customer && npm run lint`
- `cd web/customer && npm test`
- `cd web/customer && npm run build`

### Packet 7 - Screenshot Verification And Polish

Status: complete

Steps:

1. Run the customer app through the canonical local stack or Vite as appropriate.
2. Capture desktop and mobile screenshots for:
   - menu loading/loaded/error/empty
   - product detail with image/video/fallback
   - finite-stock and sold-out items
   - cart empty/filled
   - checkout pickup/delivery/saved-address/new-address/error
   - orders and order detail
   - profile, addresses, loyalty
   - login and OTP
3. Validate 375px, 390px, 430px, and desktop widths in RU and EN.
4. Check reduced-motion media fallback.

Acceptance:

- no incoherent overlap
- sticky controls do not collide with mobile browser/safe area
- contrast and tap target issues are corrected before final signoff

Verification:

- `./scripts/up.sh`
- Playwright browser pass against `http://localhost:240/` with authenticated QA
  customer state, cart seeding, and pickup order creation.
- Captured 13 route screenshots under
  `/tmp/aura-customer-redesign-screenshots`.
- Checked `/menu`, `/cart`, `/checkout`, `/orders`, `/profile`,
  `/profile/addresses`, and `/profile/loyalty` at 375px, 390px, 430px, and
  1440px for nonblank render and horizontal overflow; all reported 0px
  horizontal overflow.
- Captured viewport-only mobile screenshots for menu, cart, checkout, profile,
  and item detail to validate fixed bottom-nav behavior without full-page
  screenshot artifacts.
- Focused bilingual overflow pass for RU and EN on `/menu`, `/checkout`,
  `/profile`, and `/profile/addresses` at 375px and 430px; all reported 0px
  horizontal overflow.

### Packet 8 - Warm Neutral Review Adjustment

Status: complete

Files:

- `web/customer/src/index.css`
- `docs/design/aura-customer-redesign-plan.md`

Context:

Review screenshots showed that `--card` was reading as white-white and large
blank page areas still pulled attention. The adjustment keeps the botanical
direction but deepens the neutral hierarchy:

- page canvas: oat
- primary surfaces: milk white
- nested surfaces and placeholders: biscuit

Steps:

1. Lower `--background` lightness so blank canvas recedes.
2. Lower `--card` / `--popover` from near-white to milk white.
3. Nudge `--muted`, `--secondary`, `--border`, and `--input` into the same warm
   neutral family.
4. Preserve sage actions, espresso text, and existing semantic component usage.

Acceptance:

- screenshots no longer read as white-white cards on a white page
- UI remains warm botanical rather than brown-heavy
- text contrast remains high on cards, modal panels, checkout totals, and order
  details
- no route, API payload, auth, cart, pricing, checkout, or state behavior changes

Verification:

- `cd web/customer && npm run typecheck`
- `cd web/customer && npm run lint`
- `cd web/customer && npm test -- src/pages/Menu/MenuPage.test.tsx src/pages/Menu/ItemDetail.test.tsx src/pages/OrderDetailPage.test.tsx src/pages/CheckoutPage.test.tsx src/components/Layout.test.tsx`
- `cd web/customer && npm run build`
- `./scripts/up.sh`
- Playwright browser pass against `http://localhost:240/` with authenticated QA
  customer state; captured `/menu`, item detail, `/checkout`, and
  `/orders/:orderId` screenshots under
  `/tmp/aura-customer-neutral-tweak-screenshots`.
- Browser computed color check confirmed the page canvas as
  `rgb(238, 232, 221)` and card overlays as warm milk-white instead of pure
  white.

## Verification Commands

For frontend visual packets:

```bash
cd web/customer
npm test
npm run build
```

Optional narrow checks while iterating:

```bash
cd web/customer
npm run typecheck
npm run lint
```

Browser verification after visible screen packets:

```bash
./scripts/up.sh
```

Use the nginx URL printed by `up.sh`, not Vite container URLs.

## LDD Decision

LDD assertions are not required for pure visual customer frontend packets because
they do not touch backend state transitions, transaction boundaries, auth role
checks, OTP/SMS handling, payments, PII logging, or required GRACE log markers.

LDD becomes required if a later packet changes checkout server behavior, auth,
OTP, payment, order transitions, PII logging, or backend marker emission.

## GRACE Final Report

Module: `M-WEB-CUSTOMER`

Packet status: Packets 0-8 complete.

Safety double-check:

- Diff is presentation-only in customer frontend files plus font dependencies.
- No backend files, migrations, state machines, payment/SMS workers, or GRACE
  marker emitters changed.
- No API endpoint, auth-token storage, checkout payload, order-status polling,
  profile/address mutation, cart mutation, or pricing calculation behavior was
  intentionally changed.
- `AddressUpdatePayload` remains free of `lat`/`lon`; typed-address geocoding
  remains create-only.
- No new `console.*`, logger, or PII/secrets logging paths were added.

Markers asserted: none. LDD markers are not applicable for this visual-only
frontend packet.

Redaction checks asserted: no captured log redaction assertions were required
because no logging path was added or changed. Static diff scan found no new
frontend logging of phone, address, comment, OTP, JWT, password, or token data.

Required markers left untested: none. The packet did not touch modules or flows
with required markers in `docs/verification-plan.xml`.

Verification commands run:

- `cd web/customer && npm run typecheck`
- `cd web/customer && npm run lint`
- `cd web/customer && npm test`
- `cd web/customer && npm test -- src/pages/Menu/MenuPage.test.tsx src/pages/Menu/ItemDetail.test.tsx src/pages/OrderDetailPage.test.tsx src/pages/CheckoutPage.test.tsx src/components/Layout.test.tsx`
- `cd web/customer && npm run build`
- `git diff --check`
- `./scripts/up.sh`
- Dev-server browser font check on `http://localhost:240/login`: Inter and
  Onest loaded via `document.fonts.check(...)`; no unexpected HTTP 4xx/5xx
  responses.
- Playwright browser overflow/screenshot checks listed under Packet 7.
- Playwright warm-neutral screenshot checks listed under Packet 8.

Residual test cleanup:

- `src/App.menuCart.test.tsx` now waits for `MenuPage` to settle on the empty
  state before ending the authenticated menu-route test.
- `src/pages/Profile/LoyaltyCard.test.tsx` now waits for async balance loading
  before asserting the loyalty-history link.
- Full `npm test` passes without the previous React `act(...)` warnings.

## Risks

- White-on-sage can fail contrast when the sage is too close to the PDF color.
- Bilingual RU/EN labels can overflow category chips, buttons, and checkout rows.
- Sticky bottom controls can collide with mobile browser chrome or safe areas.
- Adding font dependencies can increase bundle size; keep weights narrow.
- Visual changes can accidentally hide server-owned errors or totals.
- Replacing raw colors broadly can break existing tests that assert class names.

## Rollback Path

Each packet should stay small enough to revert by file group:

- Packet 1: revert `package*.json`, `main.tsx`, `index.css`,
  `tailwind.config.ts`, and `button.tsx`.
- Packets 2-6: revert the touched screen/component group.
- Plan file can remain as documentation even if an implementation packet is
  reverted.

Do not use destructive git commands. Preserve unrelated user changes.
