# Drinkit Design Replication Guide For Aura

This is a design adaptation guide, not a cloning brief. The goal is to make Aura
Coffee feel similarly premium, fast, media-led, and mobile-native while keeping
Aura's own brand, product scope, assets, copy, and backend rules.

## Design Thesis

Drinkit's app is not a normal restaurant catalog. It is a dark, cinematic coffee
ordering surface built around product media, fast repeat ordering, and a playful
checkout loop.

The durable ideas worth adapting:

- product media is the main navigation and sales tool
- ordering must feel faster than talking to a cashier
- customization is visually central, not hidden in a form
- cart/payment stays reachable as a persistent bottom control
- order state is visible before, during, and after pickup
- post-order feedback and small rituals create habit

The ideas not safe to copy directly:

- whale mark, blue mascot language, exact iconography, illustrations, and copy
- Drinkit product photography/video
- exact blue palette and branded promotional cards
- referral, gifts, loyalty, tips, maps, and rating behavior unless Aura's PDD
  explicitly adopts those product features

## Screen Model

### App Shell

Drinkit behaves like a native mobile app, not a responsive website.

- full-height dark surface
- status-aware top header with shop/location and close/profile affordances
- horizontal category tabs near the top
- scrollable content under a transparent/dim overlay
- bottom safe-area-aware purchase/cart control

Aura adaptation:

- keep Aura's route structure and web constraints
- use the current single-shop assumption from the PDD
- show the selected fulfillment mode and shop status without adding a multi-shop
  map unless product scope changes

### Home And Menu

Observed files:

- `main_menu*.png`
- `drinkit-screenbook-home-for-you-promo-usual-order-again.png`
- `drinkit-screenbook-home-scrolled-worth-shot-new-for-you.png`
- `drinkit-screenbook-home-sticky-cart-bar.png`

Pattern:

- first screen is a personalized "for you" feed
- hero media fills the background or card surface
- sections mix promos, usual orders, repeat orders, new products, and categories
- product cards are media-first, with compact title, price, and plus action
- the page uses horizontal rails more than long vertical lists

Aura adaptation:

- build a menu-first home, not a marketing landing page
- use API categories as tabs and rails
- treat "usual order", referrals, and gifts as out of scope until real product
  behavior exists
- a "popular" or "new" rail can be visual-only only if backed by existing menu
  metadata or deterministic category ordering

### Category/Catalog

Observed files:

- `submenu*.png`
- `drinkit-screenbook-catalog-black-coffee-boxes-coming-soon.png`

Pattern:

- sticky top category rail
- dark page with large card blocks
- unavailable/coming-soon products remain visible but muted
- big feature cards coexist with compact product tiles

Aura adaptation:

- preserve server-owned availability
- do not add client-side availability or preorder states
- show unavailable items only if the API exposes that state; otherwise omit

### Product Detail

Observed files:

- `drink_page.png`
- `drink_description.png`
- `drinkit-screenbook-product-detail-matcha-customizer.png`
- `drinkit-screenbook-product-detail-temperature-choice.png`
- `drinkit-appstore-2026-product-customizer-hero.png`

Pattern:

- full-bleed drink media is the emotional anchor
- name and nutrition sit over the media or just below it
- size selector and add-to-cart price are fixed near the bottom
- ingredient/customization cards overlay the lower media area
- "what's inside" and allergens use a bottom sheet

Aura adaptation:

- initial visual pass can use existing `image_url`
- final target should use Aura-owned/generated video via the media contract
- nutrition/allergen rows are product changes unless Aura already has those data
- item detail must keep existing item, size, modifier, and quantity payloads

### Modifier System

Observed files:

- `drink_addons_*.png`
- `drinkit-appstore-2026-modifier-grid-customization.png`
- `drinkit-googleplay-2026-modifier-grid-customization.png`
- `drinkit-screenbook-food-addon-grid-empty.png`
- `drinkit-screenbook-food-addon-grid-selected.png`

Pattern:

- add-ons are grouped by meaning: milk, syrup, topping, ice, cup, temperature,
  espresso, sauces
- each option is a visual tile with image/icon, name, price, plus, check, or
  quantity stepper
- active option often becomes a light card inside a dark/glass grid
- repeated modifiers can have `- 1 +` steppers

Aura adaptation:

- current Aura API has a flat modifier model; grouping and quantities are real
  product/API changes
- first pass should render flat modifiers in a Drinkit-like visual grid
- grouped modifier categories and per-modifier quantities should be a separate
  PDD/GRACE packet

### Cart And Payment

Observed files:

- `cart_and_checkout.png`
- `drinkit-appstore-2026-cart-swipe-to-pay.png`
- `drinkit-googleplay-2026-cart-card-payment.png`
- `drinkit-habr-menu-pay-slider-hero.jpeg`
- `drinkit-habr-payment-slider-states.png`
- `drinkit-habr-payment-error-feedback.png`

Pattern:

- cart is not just a list; it is a checkout surface
- item card, totals, add-ons, upsells, and payment control share one screen
- payment action is a large persistent bottom pill or slider
- slider has states: idle, payment in progress, failed
- failures are visible in-place and can route the user to cart for correction

Aura adaptation:

- totals, discounts, delivery fees, and payment creation remain server-owned
- a payment slider is a UX change over the existing checkout action, not a new
  payment state machine
- failed payment UI must reflect server/API results, not invented client states
- adding a true swipe-to-pay should be tested carefully for accidental orders,
  accessibility, and keyboard/touch support

### Order Status, Rating, And Profile

Observed files:

- `drinkit-appstore-2026-order-ready-status.png`
- `drinkit-googleplay-2026-order-ready-tracking-tip.png`
- `drinkit-screenbook-order-rating-feedback-form.png`
- `drinkit-screenbook-order-rating-fortune-cookie.png`
- `profile_deeper.png`
- `drinkit-appstore-legacy-invite-friends-profile-history.png`

Pattern:

- order status uses friendly visuals, barista cards, and clear readiness labels
- ready state is visible in notifications/widgets in native apps
- rating is a short chip-based form with a final playful screen
- profile uses dark rounded fields and simple menu rows

Aura adaptation:

- web cannot copy native Live Activities/widgets
- order status must use Aura's PDD order lifecycle exactly
- rating, tips, referral gifts, and fortune-cookie rituals are product changes
- profile can be visually adapted, but PII handling and logging rules stay
  unchanged

## Visual System To Extract

Use these as direction, not exact tokens:

- base: near-black app background
- surfaces: dark elevated cards with subtle contrast
- media: full-bleed, bright, high-quality drink imagery or video
- primary action: saturated cool blue pill
- secondary action: glassy dark chips
- selected state: light tile or strong colored border/check
- type: large, bold product names; compact secondary labels
- spacing: dense rails on catalog screens, roomier hero product screens
- motion: smooth media transitions, bottom-sheet transitions, subtle button
  state changes

Aura-specific translation:

- keep Aura colors and brand personality
- avoid a one-note blue app by using Aura accent, coffee neutrals, and product
  media color
- do not copy Drinkit's mascot/whale shapes or exact promotional card treatment
- use generated or owned media only

## Product Boundaries

Safe frontend-only adaptation:

- dark app shell
- menu/category layout
- product-card hierarchy
- item-detail layout using current data
- fixed add-to-cart and cart controls
- cart/profile visual styling

Requires product/API/PDD work:

- video media fields beyond `image_url`
- grouped modifier categories
- modifier quantities
- favorites/usuals
- referral gifts or one-ruble promos
- loyalty/gifts/Coffeepass/subscription
- tips
- order rating
- shop map/multi-location selection
- nutrition/allergens/caffeine values
- receipt photo upload

GRACE/LDD decision:

- This documentation packet does not touch runtime code, backend state
  transitions, auth, payments, PII logging, or transaction boundaries. LDD
  assertions are not applicable.
- Future packets that touch checkout, payment, auth, order status, OTP/SMS,
  PII, or required log markers must apply the normal GRACE verification gate.

## Recommended Aura Implementation Path

1. Build a frontend-only dark shell and menu visual pass using current
   `image_url`, categories, sizes, and flat modifiers.
2. Restyle item detail with a media hero, fixed add-to-cart control, and visual
   modifier grid without changing API payloads.
3. Restyle cart and checkout, preserving current server totals and order
   creation flow.
4. Restyle profile/orders without changing PII or order state semantics.
5. Execute the existing video-media plan if the final design needs moving drink
   media.
6. Split every product behavior inspired by Drinkit into separate PDD/GRACE
   packets before implementation.

## Practical Design Checklist

- Can the user add a common drink in two or three taps after landing on menu?
- Is the cart/payment control always visible when there is a cart?
- Are price and quantity visible without scrolling?
- Does product customization look visual and tactile, not like a settings form?
- Does every unavailable or failed state explain what happened?
- Does the UI still work with no media, long Russian text, and no modifiers?
- Are all Aura prices, discounts, delivery fees, and payment states server-owned?
- Are raw phone numbers, addresses, comments, and auth data never logged?
