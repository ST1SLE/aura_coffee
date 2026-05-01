# Customer Redesign Reference Map

Created from the screenshots in `docs/design/screenshots/`.

Expanded public-source research is documented in:

- `docs/design/drinkit-public-screenshot-sources.md`
- `docs/design/drinkit-design-replication-guide.md`

## Core Direction

The reference product is a mobile-native, media-led coffee ordering app. The
main differentiator is moving drink media: products are presented as short,
immersive drink videos rather than static catalog photos. The UI uses a dark
base, full-bleed media, large rounded product cards, horizontal rails, sticky
category navigation, and fixed bottom purchase controls.

This should be adapted to Aura Coffee without copying another company's brand,
logos, copywriting, proprietary media, or exact trade dress. The correct target
is the experience pattern: premium drink media, fast browsing, clear modifiers,
and low-friction checkout.

## Existing Aura Boundary

Primary frontend target:

- `web/customer/src/components/Layout.tsx`
- `web/customer/src/pages/Menu/MenuPage.tsx`
- `web/customer/src/pages/Menu/MenuItemCard.tsx`
- `web/customer/src/pages/Menu/ItemDetail.tsx`
- `web/customer/src/pages/Cart/*`
- `web/customer/src/pages/CheckoutPage.tsx`
- `web/customer/src/pages/Profile*`
- `web/customer/src/index.css`

Current menu media contract:

- PDD and backend expose `menu_items.image_url`.
- `PublicMenuItem` exposes `image_url: string | null`.
- `MenuItemCard` renders `image_url` with `<img>`.
- There is no current first-class video media field.

Implication: visual restyling can be frontend-only, but true product videos need
a product/API/data contract change.

## Screenshot Groups

| Screenshot(s) | Aura Target | What To Adapt | Behavior Boundary |
| --- | --- | --- | --- |
| `main_menu.png`, `main_menu_scrolled_down*.png`, `main_menu_cart_at_the_bottom.png` | `Layout`, `MenuPage`, `MenuItemCard` | full-screen mobile shell, location/shop header, dark translucent lower content, horizontal category tabs, popular/new rails, large media cards, sticky cart pill | Do not introduce multiple shop locations unless product scope changes; single-shop pickup/delivery remains authoritative. |
| `submenu.png`, `submenu_scrolled_down*.png` | `MenuPage`, possible category route/section component | dense category page, sticky top category rail, large featured card followed by product grid/list cards | Categories come from API. No hardcoded seasonal taxonomy unless represented by menu categories/tags. |
| `drink_page.png`, `drink_description.png` | `ItemDetail` | immersive product detail with full-bleed media, top nutrition row, favorite/close controls, "what's inside" bottom sheet, horizontal addon category cards, fixed add-to-cart bar | Add-to-cart payload must remain existing item/size/modifier IDs. Price shown can be display-only; server remains source of truth. |
| `drink_addons_1.png` through `drink_addons_17.png` | `ItemDetail`, modifier picker components | modifier category carousel, cards with icon/media, selected state, plus/check controls, quantity stepper for repeatable modifiers, size pill, fixed price/add bar | Existing API supports a flat modifier list, not grouped addon categories or modifier quantities. Grouping/quantities are product/API changes if required. |
| `cart_and_checkout.png` | `CartPage`, `CheckoutPage` | dark cart page, item summary card, nutrition summary, upsell rail, fixed payment/checkout bar | Payment remains YuKassa/server-owned. Current checkout supports pickup/delivery and creates orders via API; do not add a client-only payment success path. |
| `profile_deeper.png` | `ProfilePage`, address/loyalty/order pages | dark profile form styling, large rounded fields, notification toggle, menu rows, logout button | Phone/name/address are PII. Keep them in existing API/profile flows and do not log raw values. |

## Video Media Requirement

The reference app's strongest advantage is video product media. To make Aura feel
similar, static photos are not enough. Recommended target behavior:

- Menu cards show silent looping drink video previews when available.
- Product detail uses full-bleed silent looping video as the hero.
- The first frame/poster is visible immediately.
- Videos are muted, looped, `playsInline`, and never require controls for normal
  browsing.
- Videos lazy-load and pause when offscreen.
- `prefers-reduced-motion` and failed media loads fall back to poster images.
- The UI must still work when a menu item has no media.

Do not use another company's videos. Use owned drink videos, generated media
approved for commercial use, or temporary local placeholders clearly marked as
placeholders.

## Product/API Decision Point

Decision: use Path B, the video-first media contract, with Aura-owned/generated
drink videos. Path A remains useful only as a fallback if video asset production
blocks UI implementation.

Confirmed implementation constraints:

- Generated videos are local static assets because menu media is set once and
  changes rarely.
- Menu media URLs are stored as public static paths in the database.
- The existing admin menu item form must support `media_type`, `media_url`, and
  `media_poster_url` in the first media-contract wave.
- Grouped modifier categories and modifier quantities are explicitly separate
  product changes and must not be folded into the video-led redesign.

There are two implementation paths.

### Path A: Visual Pass First

Keep current backend contract and use `image_url` posters/static images.

Pros:

- fastest
- low risk
- no DB migration
- no PDD/API updates
- no backend tests beyond existing frontend verification

Cons:

- misses the main "moving drink" differentiator
- final UI may need another pass once videos are added

### Path B: Video-First Media Contract

Add explicit media support before finalizing the menu/product UI.

Likely data/API shape:

```text
menu_items.media_type        image | video | null
menu_items.media_url         URL to primary image/video
menu_items.media_poster_url  URL to static poster/fallback
```

Compatibility rule:

- keep `image_url` as legacy/poster during migration, or map it to
  `media_poster_url` until all menu items have the new fields.

Frontend shape:

- add a `MenuMedia` component that chooses `<video>` or `<img>`
- update `PublicMenuItem` types
- update `MenuItemCard` and `ItemDetail` to use `MenuMedia`
- add tests for image fallback, video rendering, and missing media

Backend/data shape:

- update PDD menu item table definition
- add database migration
- update ORM model, schemas, public menu service, seeds/admin flows
- add API tests for backwards-compatible menu payloads

GRACE/LDD:

- LDD assertions are not expected for media-only schema/API work unless the
  packet also touches state transitions, auth, payments, OTP/SMS, PII logging,
  or transaction boundaries.
- PDD/XML refresh is required for Path B because the product/API/data contract
  changes.

## Design Tokens To Extract

- base background: near-black app surface
- panels/cards: slightly lighter dark surfaces with high radius
- text: large white display text, muted gray secondary text
- accent: saturated blue action button/pill
- cards: large radii, image/video-first layout, little border use
- bottom controls: fixed, safe-area-aware, pill-shaped
- category nav: horizontally scrollable, oversized active label
- modal sheets: black/near-black sheets over dimmed/blurred media

Adapt colors to Aura Coffee branding instead of copying the exact reference
palette.

## Suggested Implementation Packets

1. **Reference-safe app shell:** dark mobile-first `Layout`, safe-area spacing,
   profile/cart/order access, bottom/sticky navigation behavior.
2. **Menu visual pass:** category rails and product cards using current
   `image_url`, no API changes.
3. **Item detail visual pass:** immersive detail view using current size and
   flat modifier list, fixed add-to-cart bar, existing cart payload.
4. **Cart/checkout visual pass:** dark cart, item summaries, fixed checkout bar,
   existing checkout API.
5. **Video media contract:** if selected, update PDD/API/data/frontend media
   model and replace poster-only surfaces with `MenuMedia`.
6. **Profile/orders polish:** restyle profile, addresses, loyalty, and order
   history without changing PII/auth/order behavior.

## Open Questions Before Code

- Should seasonal tabs such as "spring" be real menu categories/tags, or just
  a visual grouping of existing categories?
- Which reference elements are intentionally out of scope: favorites, gifts,
  mini-games, nutrition, allergen sheets, payment-provider picker?
