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

### Packet 9 - Stronger Non-White Surface Correction

Status: complete

Files:

- `web/customer/src/index.css`
- `web/customer/src/pages/Menu/ItemDetail.tsx`
- `docs/design/aura-customer-redesign-plan.md`

Context:

Follow-up screenshots still read the main cards and item-detail controls as
white because Packet 8 left primary surfaces at `96%` lightness. This packet
makes the color shift visible rather than barely perceptible.

Steps:

1. Lower page canvas from `38 32% 90%` to `38 24% 84%`.
2. Lower card/popover surfaces from `42 56% 96%` to `39 40% 90%`.
3. Lower nested surfaces and placeholder fills into a biscuit range.
4. Lower border/input color so form fields and order cards remain legible on the
   warmer surfaces.
5. Make the item-detail modal panel use `bg-card` and `from-card` so the modal
   is a milk surface rather than the page canvas.

Acceptance:

- no large customer surface should read as white-white in browser screenshots
- body/canvas, cards, and nested panels have visibly separate warm-neutral
  values
- menu, item detail, checkout, and order detail remain readable
- no API, cart, order, checkout, auth, pricing, or persistence behavior changes

Verification:

- `cd web/customer && npm run typecheck`
- `cd web/customer && npm run lint`
- `cd web/customer && npm test -- src/pages/Menu/MenuPage.test.tsx src/pages/Menu/ItemDetail.test.tsx src/pages/OrderDetailPage.test.tsx src/pages/CheckoutPage.test.tsx src/components/Layout.test.tsx`
- `cd web/customer && npm run build`
- `./scripts/up.sh`
- Playwright browser pass against `http://localhost:240/` with authenticated QA
  customer state; captured `/menu`, item-detail viewport, `/checkout`, and
  `/orders/:orderId` screenshots under
  `/tmp/aura-customer-neutral-stronger-screenshots`.
- Browser computed color check confirmed body `rgb(224, 217, 204)`, cards/modal
  panel `rgb(240, 233, 219)`, and nested panels `rgb(218, 207, 190)`.

### Packet 10 - Bold Taupe/Cream Palette

Status: complete

Files:

- `web/customer/src/index.css`
- `docs/design/aura-customer-redesign-plan.md`

Context:

Packet 9 still stayed too restrained in live review. Packet 10 intentionally
moves the customer UI from subtle warmth to a visibly branded warm-neutral
scheme:

- taupe/oat page canvas
- cream menu/order/checkout cards
- biscuit nested controls and placeholder media
- coffee-toned borders

Steps:

1. Lower page canvas from `38 24% 84%` to `35 27% 72%`.
2. Lower card/popover surfaces from `39 40% 90%` to `39 38% 84%`.
3. Lower nested surface fills from the low-80s/high-70s to `34 34% 68%` and
   `36 30% 74%`.
4. Lower border/input color to `32 24% 54%` so cards and form fields separate
   clearly on the stronger background.
5. Preserve sage actions and espresso text for brand continuity and contrast.

Acceptance:

- the app no longer reads as white or near-white in menu, modal, checkout, or
  order-detail screenshots
- checked surface colors have RGB max channel below 233
- empty page space recedes as an intentional taupe canvas
- cards remain cream and readable rather than becoming brown-heavy
- no API, cart, order, checkout, auth, pricing, or persistence behavior changes

Verification:

- `cd web/customer && npm run typecheck`
- `cd web/customer && npm run lint`
- `cd web/customer && npm test -- src/pages/Menu/MenuPage.test.tsx src/pages/Menu/ItemDetail.test.tsx src/pages/OrderDetailPage.test.tsx src/pages/CheckoutPage.test.tsx src/components/Layout.test.tsx`
- `cd web/customer && npm run build`
- `./scripts/up.sh`
- Playwright browser pass against `http://localhost:240/` with authenticated QA
  customer state; captured `/menu`, item-detail viewport, `/checkout`, and
  `/orders/:orderId` screenshots under
  `/tmp/aura-customer-bold-palette-screenshots`.
- Browser computed color gate confirmed body `rgb(203, 187, 164)`,
  cards/modal panel `rgb(230, 219, 199)`, and nested panels
  `rgb(209, 193, 169)`; the smoke fails if checked surfaces are still
  near-white.

### Packet 11 - Media-First Menu Browsing And Cart CTA

Status: complete

Files:

- `web/customer/src/index.css`
- `web/customer/src/pages/Menu/MenuItemCard.tsx`
- `web/customer/src/pages/Menu/MenuItemCard.test.tsx`
- `web/customer/src/pages/Menu/ItemDetail.tsx`
- `web/customer/src/components/Layout.tsx`
- `web/customer/src/components/Layout.test.tsx`
- `docs/design/aura-customer-redesign-plan.md`

Context:

Live review still showed two problems in the browsing menu state:

- menu cards reserve a large light content block below the media, which blocks
  the video/photo from becoming the product surface
- the palette still has too much light-card energy in screenshots
- cart reachability should feel like the Drinkit reference:
  `docs/design/screenshots/main_menu_cart_at_the_bottom.png`

Source checks:

- Material imagery guidance supports large imagery and local text-protection
  scrims rather than blanket overlays:
  https://m1.material.io/style/imagery.html
- Material image-list guidance treats text protection as a scrim over the image
  when supporting text overlays media:
  https://www.npmjs.com/package/@material/image-list
- Material FAB guidance says one promoted floating action can be used for the
  primary screen action, and lists need bottom padding so content is not blocked:
  https://m1.material.io/components/buttons-floating-action-button.html
- WCAG 2.1 non-text contrast requires UI component boundaries and meaningful
  graphical objects to keep at least 3:1 contrast against adjacent colors:
  https://w3c.github.io/wcag21/understanding/non-text-contrast

Decision:

Use a media-first card instead of a white/cream information tray. The card media
fills the tile, product name and price float over a targeted espresso scrim, and
the price becomes a warm oval badge. For the broader palette, move away from
taupe-on-cream into a stronger smoked-sage canvas with clay/linen cards and
coffee borders. This removes white-white surfaces without turning every surface
into the same brown hue.

Steps:

1. Rework `MenuItemCard` so `MenuMedia` fills the card and the bottom content is
   an overlay scrim, not a separate light panel.
2. Move the price into a rounded warm oval over the media, near the product
   name, and keep the whole available card as the click target.
3. Preserve finite-stock and unavailable/sold-out badges as overlays.
4. Refresh the global customer tokens to smoked sage canvas, clay/linen cards,
   biscuit nested panels, dark olive primary actions, and coffee borders.
5. Make the floating menu cart link an extended bottom CTA with count and total,
   and refresh cart state on shell mount so existing carts show after reload.
6. Keep the item-detail dialog above the browsing cart CTA so the CTA does not
   cover modal configuration controls.
7. Preserve protected routes, cart API contracts, add-to-cart behavior, checkout
   payloads, order states, and backend-owned pricing.

Acceptance:

- menu browsing cards no longer have a light block underneath media
- product name and price remain readable over image/video via a targeted scrim
- price appears as a floating oval on the media
- large surfaces no longer read as white in menu/order/checkout screenshots
- cart CTA appears on `/menu` when the cart has items, including after reload
- no backend, API, auth enforcement, pricing, payment, or order-state behavior
  changes

Verification:

- `cd web/customer && npm run typecheck`
- `cd web/customer && npm run lint`
- `cd web/customer && npm test -- src/pages/Menu/MenuItemCard.test.tsx src/pages/Menu/MenuPage.test.tsx src/pages/Menu/ItemDetail.test.tsx src/components/Layout.test.tsx src/pages/CheckoutPage.test.tsx src/pages/OrderDetailPage.test.tsx`
- `cd web/customer && npm run build`
- `./scripts/up.sh`
- Playwright browser smoke on the canonical nginx URL with authenticated QA
  customer, seeded cart, `/menu`, item-detail, `/checkout`, and
  `/orders/:orderId` captures.
- Browser smoke captured screenshots under
  `/tmp/aura-customer-menu-media-card-screenshots`.
- Computed browser tokens confirmed smoked-sage canvas `rgb(135, 143, 112)`,
  clay card/placeholder surface `rgb(182, 159, 129)`, espresso floating cart
  CTA `rgb(27, 23, 19)`, and card scrim
  `linear-gradient(to top, rgba(27, 23, 19, 0.85), rgba(27, 23, 19, 0.35), transparent)`.
- Reload smoke confirmed the floating menu cart CTA appears after cart refresh
  without visiting `/cart` first.
- Layer smoke confirmed item-detail dialog z-index `70` sits above the floating
  cart CTA z-index `50`.

### Packet 12 - Auth, Profile, And Address Polish

Status: complete

Files:

- `web/customer/src/pages/LoginPage.tsx`
- `web/customer/src/pages/VerifyPage.tsx`
- `web/customer/src/pages/ProfilePage.tsx`
- `web/customer/src/pages/Profile/LoyaltyCard.tsx`
- `web/customer/src/pages/Profile/Addresses/AddressesPage.tsx`
- `web/customer/src/pages/Profile/Addresses/AddressForm.tsx`
- `web/customer/src/components/AddressAutocomplete/AddressAutocomplete.tsx`
- `docs/design/aura-customer-redesign-plan.md`

Context:

After Packet 11, menu browsing has the intended smoked-sage/clay tone. The
remaining customer polish backlog calls out auth, profile, and saved-address
surfaces, which still read as older light cards compared with the menu and
checkout work.

Decision:

Bring auth, profile, loyalty, and saved-address surfaces into the same visual
system without changing the OTP flow, protected-route behavior, profile API,
address create/edit/delete contracts, or PII handling. Keep forms compact and
usable for repeated customer tasks rather than making them marketing screens.

Steps:

1. Restyle `/login` and `/login/verify` as compact branded auth panels on the
   smoked-sage canvas while preserving input roles, masked-phone display, resend
   behavior, and localized errors.
2. Tighten `/profile` into structured surface groups with icon badges, mobile
   wrapping for editable controls, and stronger language/name/addresses affordances.
3. Refresh `LoyaltyCard` so the balance and history link match the customer
   visual system without changing the balance fetch or link target.
4. Polish saved-address list/create/edit screens with responsive action rows,
   clearer default badges, softer address input surfaces, and mobile-safe form
   grids.
5. Preserve all profile/address mutation payloads, typed-address geocoding
   behavior, delete confirmation, and API error rendering.

Acceptance:

- auth screens match the smoked-sage/clay customer palette and keep a single
  clear submit path
- profile fields and language controls do not overflow on mobile
- saved-address cards keep full address details readable without cramped action
  columns
- address create/edit form fields stack safely on small screens
- no API endpoint, auth-token storage, OTP resend/verify, profile mutation,
  address mutation, geocoding, logging, or backend behavior changes

Verification:

- `cd web/customer && npm run typecheck`
- `cd web/customer && npm run lint`
- `cd web/customer && npm test -- src/pages/LoginPage.test.tsx src/pages/VerifyPage.test.tsx src/pages/VerifyPage.otp409.test.tsx src/components/auth/PhoneInput.test.tsx src/components/auth/OTPInput.test.tsx src/pages/ProfilePage.test.tsx src/pages/Profile/LoyaltyCard.test.tsx src/pages/Profile/Addresses/AddressesPage.test.tsx src/pages/Profile/Addresses/AddressForm.test.tsx src/components/AddressAutocomplete/AddressAutocomplete.test.tsx`
- `cd web/customer && npm run build`
- Playwright browser smoke on the canonical nginx URL for `/login`,
  authenticated `/profile`, and authenticated `/profile/addresses`.
- Browser smoke captured 320px, 390px, and 1280px screenshots under
  `/tmp/aura-customer-auth-profile-polish-screenshots`.
- Browser smoke asserted no horizontal overflow on `/login`, `/profile`, and
  `/profile/addresses`, protected routes stayed on their expected paths, and no
  protected-route API 4xx/5xx responses or page errors occurred.

### Packet 13 - Menu Deep Link And Media Fallback Cleanup

Status: complete

Files:

- `web/customer/src/pages/Menu/MenuPage.tsx`
- `web/customer/src/pages/Menu/MenuMedia.tsx`
- `web/customer/src/pages/Menu/MenuPage.test.tsx`
- `web/customer/src/pages/Menu/MenuMedia.test.tsx`
- `docs/design/aura-customer-redesign-plan.md`

Context:

Follow-up menu review found two residual browsing issues after Packet 11:

- `/menu/:categoryId` was registered in the router but `MenuPage` ignored the
  category id, so deep links did not activate or scroll to that category.
- products without media still rendered a plain empty block, which weakened the
  media-first card treatment for food/merch QA items.

Steps:

1. Read `categoryId` from the route and, after menu load, activate and scroll to
   the matching non-empty category section.
2. Keep scroll-driven category synchronization as the active category authority
   while the customer browses normally.
3. Replace the no-source or failed-image media block with a branded fallback
   surface and icon that stays behind the existing product-name/price overlay.
4. Preserve menu API shape, category ownership, cart behavior, checkout payloads,
   pricing, auth, order state, and logging behavior.

Acceptance:

- `/menu/2` activates the matching category chip and scrolls to the matching
  category when the category exists and has public items.
- invalid or empty category ids fall back to the first visible category.
- no-media items show a branded fallback instead of a flat blank rectangle.
- no backend, API, auth, cart, pricing, payment, order-state, or persistence
  behavior changes.

Verification:

- `cd web/customer && npm test -- src/pages/Menu/MenuPage.test.tsx src/pages/Menu/MenuMedia.test.tsx`
- `cd web/customer && npm run typecheck`
- `cd web/customer && npm run lint`
- `cd web/customer && npm run build`
- `cd web/customer && npm test`
- `git diff --check`
- Playwright browser smoke against `http://127.0.0.1:240/menu/2` with
  authenticated QA customer cookies at 1280x720 and 390x844.
- Browser smoke captured screenshots under
  `/tmp/aura-customer-menu-deeplink-fallback`.
- Browser smoke asserted route retention on `/menu/2`, active category
  `Phase4 QA Food`, food section in viewport, branded fallback media present,
  and 0px horizontal overflow.

### Packet 14 - Saved Address Delete Dialog And Labels

Status: complete

Files:

- `web/customer/src/pages/Profile/Addresses/AddressesPage.tsx`
- `web/customer/src/pages/Profile/Addresses/AddressesPage.test.tsx`
- `docs/design/aura-customer-redesign-plan.md`

Context:

The remaining customer P2 polish backlog still had two saved-address issues in
the same screen:

- delete used the browser-native `window.confirm`, which breaks the app's visual
  system and is awkward on mobile.
- apartment, entrance, and floor details used hardcoded Russian prefixes in the
  saved-address list.

Steps:

1. Replace `window.confirm` with an in-app modal confirmation on the
   saved-address screen.
2. Keep `deleteAddress(id)` as the only destructive call and run it only after
   explicit confirmation.
3. Preserve the cancel path without API side effects.
4. Render apartment, entrance, and floor labels through existing i18n keys.
5. Preserve address list/create/edit/default APIs, payloads, geocoding behavior,
   auth enforcement, and PII logging boundaries.

Acceptance:

- tapping "Delete" opens a modal dialog instead of the browser confirm.
- cancel closes the dialog and does not call `deleteAddress`.
- confirm calls `deleteAddress(id)`, refreshes the list, and keeps the existing
  error rendering path.
- address detail labels are localized in RU and EN.
- no backend, API contract, auth, profile/address persistence, geocoding, or
  logging behavior changes.

Verification:

- `cd web/customer && npm test -- src/pages/Profile/Addresses/AddressesPage.test.tsx`
- `cd web/customer && npm run typecheck`
- `cd web/customer && npm run lint`
- `cd web/customer && npm run build`
- `cd web/customer && npm test`
- `git diff --check`
- Playwright browser smoke against `http://127.0.0.1:240/profile/addresses`
  with authenticated QA customer cookies at 1280x720 and 390x844.
- Browser smoke captured screenshots under
  `/tmp/aura-customer-address-delete-dialog`.
- Browser smoke asserted the delete dialog opens, cancel closes it without a
  DELETE request, address context is visible, and horizontal overflow is 0px.

### Packet 15 - Auth And Item Detail Accessibility Labels

Status: complete

Files:

- `web/customer/src/components/auth/OTPInput.tsx`
- `web/customer/src/components/auth/OTPInput.test.tsx`
- `web/customer/src/components/auth/PhoneInput.tsx`
- `web/customer/src/components/auth/PhoneInput.test.tsx`
- `web/customer/src/pages/Menu/ItemDetail.tsx`
- `web/customer/src/pages/Menu/ItemDetail.test.tsx`
- `web/customer/src/i18n/locales/en/common.json`
- `web/customer/src/i18n/locales/ru/common.json`
- `docs/design/aura-customer-redesign-plan.md`

Context:

The remaining customer accessibility/i18n backlog still had small hardcoded or
unlabeled controls:

- OTP digit inputs had no accessible per-field labels.
- the phone input placeholder was hardcoded instead of using existing i18n.
- the item-detail close button used a hardcoded English ARIA label.

Steps:

1. Add localized per-digit OTP labels with position and total.
2. Read the phone placeholder from `auth.phone.placeholder`.
3. Add a localized `menu.close` key and use it for the item-detail close button.
4. Preserve OTP value handling, auto-advance, paste behavior, verification
   payloads, phone normalization, item-detail cart payloads, and pricing display.

Acceptance:

- screen readers can distinguish OTP digit inputs.
- phone placeholder text is sourced from i18n.
- item-detail close action is localized.
- no OTP send/verify behavior, auth-token storage, cart API payload, checkout,
  backend, logging, or PII persistence behavior changes.

Verification:

- `cd web/customer && npm test -- src/components/auth/OTPInput.test.tsx src/components/auth/PhoneInput.test.tsx src/pages/Menu/ItemDetail.test.tsx`
- `cd web/customer && npm run typecheck`
- `cd web/customer && npm run lint`
- `cd web/customer && npm run build`
- `cd web/customer && npm test`
- `git diff --check`

### Packet 16 - Address Autocomplete Combobox Keyboard Support

Status: complete

Files:

- `web/customer/src/components/AddressAutocomplete/AddressAutocomplete.tsx`
- `web/customer/src/components/AddressAutocomplete/AddressAutocomplete.test.tsx`
- `web/customer/src/pages/CheckoutPage.test.tsx`
- `web/customer/src/pages/Profile/Addresses/AddressForm.test.tsx`
- `docs/design/aura-customer-redesign-plan.md`

Context:

The customer UX audit found that address suggestions were mouse-selectable but
the input did not expose combobox semantics or keyboard navigation. This made
saved-address and checkout address entry weaker for keyboard and assistive-tech
users.

Steps:

1. Add stable listbox/option IDs and connect the input with `role="combobox"`,
   `aria-autocomplete`, `aria-expanded`, `aria-controls`, and
   `aria-activedescendant`.
2. Track an active suggestion and support ArrowDown, ArrowUp, Enter, and Escape.
3. Reset active suggestion state when the query changes, the list closes, the
   component enters maps-degraded fallback, or the query becomes too short.
4. Preserve the existing suggest debounce, stale-response guard, mouse selection,
   degraded fallback, and typed-address geocoding contract.

Acceptance:

- screen readers can detect the input as a list-backed combobox.
- keyboard users can move through suggestions and choose one without a pointer.
- Escape closes the suggestions without changing the typed address.
- manual text entry still clears coordinates so the server can geocode at order
  time.
- no checkout payload, saved-address mutation, maps API contract, backend,
  logging, auth, payment, or order-state behavior changes.

Verification:

- `cd web/customer && npm test -- src/components/AddressAutocomplete/AddressAutocomplete.test.tsx`
- `cd web/customer && npm test -- src/components/AddressAutocomplete/AddressAutocomplete.test.tsx src/pages/Profile/Addresses/AddressForm.test.tsx`
- `cd web/customer && npm test -- src/components/AddressAutocomplete/AddressAutocomplete.test.tsx src/pages/Profile/Addresses/AddressForm.test.tsx src/pages/CheckoutPage.test.tsx`

### Packet 17 - Menu Item Native Button Semantics

Status: complete

Files:

- `web/customer/src/pages/Menu/MenuItemCard.tsx`
- `web/customer/src/pages/Menu/MenuItemCard.test.tsx`
- `docs/design/aura-customer-redesign-plan.md`

Context:

The customer UX audit still had one small menu accessibility note: menu item
cards used `div role="button"` with custom keyboard handling. Native button
semantics are more robust and make disabled unavailable/sold-out cards explicit.

Steps:

1. Replace the custom clickable `div` with a native `button type="button"`.
2. Use the native `disabled` attribute for unavailable and sold-out items.
3. Remove custom `tabIndex`, `role`, `aria-disabled`, and keydown activation.
4. Preserve the media-first visual treatment, price/name overlays, plus icon,
   badges, click-to-open behavior, and no cart/order mutation from the card.

Acceptance:

- available item cards are native enabled buttons.
- unavailable and sold-out cards are native disabled buttons and do not call
  `onOpen`.
- video/image media clicks still bubble to the available card button.
- no cart API, menu API, pricing, availability, checkout, backend, logging,
  auth, payment, or order-state behavior changes.

Verification:

- `cd web/customer && npm test -- src/pages/Menu/MenuItemCard.test.tsx`

### Packet 18 - Checkout And Item Detail Focus Flow

Status: complete

Files:

- `web/customer/src/pages/CheckoutPage.tsx`
- `web/customer/src/pages/CheckoutPage.test.tsx`
- `web/customer/src/pages/Menu/ItemDetail.tsx`
- `web/customer/src/pages/Menu/ItemDetail.test.tsx`
- `web/customer/src/pages/Menu/MenuItemCard.tsx`
- `web/customer/src/pages/Menu/MenuPage.tsx`
- `web/customer/src/pages/Menu/MenuPage.test.tsx`
- `docs/design/aura-customer-redesign-plan.md`

Context:

The remaining current customer accessibility note was focus flow: checkout
server errors should move focus to the alert, and opening item detail should
move focus into the modal then restore focus to the originating menu card on
close.

Steps:

1. Focus the checkout error alert when submit/address validation errors render.
2. Focus the item-detail close control when the bottom sheet opens.
3. Pass the originating native menu-card button to `MenuPage` and restore focus
   after `ItemDetail` closes.
4. Preserve checkout payloads, cart add payloads, menu API behavior, item
   pricing display, media rendering, and all backend/order/auth/logging paths.

Acceptance:

- checkout validation or server errors render an alert and move keyboard focus
  to it.
- item detail opens with focus inside the dialog.
- closing item detail returns focus to the card that opened it.
- no checkout payload, cart API, menu API, backend, logging, auth, payment, or
  order-state behavior changes.

Verification:

- `cd web/customer && npm test -- src/pages/Menu/MenuPage.test.tsx src/pages/Menu/ItemDetail.test.tsx src/pages/Menu/MenuItemCard.test.tsx src/pages/CheckoutPage.test.tsx`

### Packet 19 - Login Submit Loading Label

Status: complete

Files:

- `web/customer/src/pages/LoginPage.tsx`
- `web/customer/src/pages/LoginPage.test.tsx`
- `web/customer/src/i18n/locales/en/common.json`
- `web/customer/src/i18n/locales/ru/common.json`
- `docs/design/aura-customer-redesign-plan.md`

Context:

The remaining current customer i18n note was a hardcoded `...` loading label on
the login submit button while the OTP send-code request is pending.

Steps:

1. Add localized `auth.phone.submitting` text in RU and EN.
2. Use the localized key for the pending submit button label.
3. Add a pending-promise test so the transient loading state is asserted.
4. Preserve phone normalization, validation, `login(phone)`, return-url
   propagation, error rendering, and OTP verify routing.

Acceptance:

- login submit no longer renders a literal `...`.
- pending send-code state is localized and the button remains disabled.
- no auth API contract, OTP code flow, token storage, backend, SMS, logging, or
  PII persistence behavior changes.

Verification:

- `cd web/customer && npm test -- src/pages/LoginPage.test.tsx`

### Packet 20 - Mobile Text Overflow Screenshot Verification

Status: complete

Files:

- `docs/design/aura-customer-redesign-plan.md`

Context:

The remaining customer audit note was verification-oriented: mobile text
overflow needed screenshot coverage for long Russian checkout/address/profile
strings.

Steps:

1. Use the existing `tests/e2e` Playwright dependency and canonical nginx URL
   `http://127.0.0.1:240`.
2. Authenticate the seeded QA customer with a server-issued refresh cookie and
   seed one cart item through the API so checkout renders totals.
3. Force RU locale through `localStorage.i18nextLng`.
4. Capture `/checkout`, `/profile`, and `/profile/addresses` at 375x812,
   390x844, 430x932, 768x1024, and 1280x800.
5. Measure `documentElement/body.scrollWidth` against `window.innerWidth` and
   scan visible element boxes for viewport overflow.

Acceptance:

- all measured routes have 0px horizontal overflow at all target viewports.
- no visible element box extends beyond the viewport.
- checkout/profile/address screenshots are captured for manual inspection.
- no source code, API, auth flow, cart behavior, backend, logging, payment, or
  order-state behavior changes.

Verification:

- Headless Chrome smoke against `http://127.0.0.1:240` using the repo's
  `tests/e2e/node_modules/playwright` install.
- Screenshots and `results.json` captured under
  `/tmp/aura-customer-mobile-overflow`.
- Browser smoke covered 15 combinations: `/checkout`, `/profile`,
  `/profile/addresses` at 375x812, 390x844, 430x932, 768x1024, and 1280x800.
- Every combination reported `overflowPx: 0`, `offenderCount: 0`, and no
  non-favicon HTTP 4xx/5xx responses.

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

Packet status: Packets 0-20 complete.

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
- Playwright stronger non-white screenshot checks listed under Packet 9.
- Playwright bold taupe/cream screenshot and computed-color gate listed under
  Packet 10.
- Packet 12 focused verification listed under Packet 12.
- Packet 13 focused verification listed under Packet 13.
- Packet 14 focused verification listed under Packet 14.
- Packet 15 focused verification listed under Packet 15.
- Packet 16 focused verification listed under Packet 16.
- Packet 17 focused verification listed under Packet 17.
- Packet 18 focused verification listed under Packet 18.
- Packet 19 focused verification listed under Packet 19.
- Packet 20 browser overflow/screenshot verification listed under Packet 20.

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
