# Aura Coffee Design Workspace

This directory is the working area for customer-facing design references and
design-to-code notes.

Raw screenshot references belong in:

```text
docs/design/screenshots/
```

Current Drinkit research artifacts:

- `drinkit-public-screenshot-sources.md` - public-source scrape manifest and
  filename inventory.
- `drinkit-design-replication-guide.md` - pattern synthesis and Aura adaptation
  boundaries.
- `reference-map.md` - route/component mapping for existing local screenshots.

Use clear filenames so the implementation target is obvious, for example:

```text
01-home-menu.png
02-product-detail.png
03-cart.png
04-checkout-delivery.png
05-profile-orders.png
```

The `screenshots/` directory ignores raw image files by default. This keeps
third-party reference screenshots, proprietary app UI, or private notes out of
Git while still letting local agents inspect them during implementation. If a
specific image must become a committed project asset, move it to the appropriate
frontend asset directory and document why.

## What "Copying The Design" Means

For Aura Coffee, copying a design means adapting the visual language and UX
patterns to our product. It does not mean cloning another company's brand,
logos, illustrations, exact copywriting, icon set, or distinctive trade dress.

Good things to copy or adapt:

- mobile-first screen structure
- media-led product presentation with owned drink videos
- bottom navigation patterns
- product card hierarchy
- category browsing behavior
- item detail layout
- cart and checkout ergonomics
- spacing, density, rhythm, and interaction patterns
- mood, polish, and perceived quality

Things not to copy directly:

- another brand's logo, colors, mascots, illustrations, or marketing copy
- proprietary product names
- exact custom icons or artwork
- another company's drink videos or product photography
- screens that imply business behavior Aura Coffee does not support

## Hard Project Boundaries

The redesign target is `web/customer`, especially:

- `src/components/Layout.tsx`
- `src/pages/Menu/*`
- `src/pages/Cart/*`
- `src/pages/CheckoutPage.tsx`
- `src/pages/OrdersPage.tsx`
- `src/pages/Profile*`
- `src/index.css` and Tailwind styling

The UI must preserve the business rules owned by `services/core-api` and the
PDD/GRACE artifacts:

- pricing, discounts, points, delivery fees, and totals are server-owned
- delivery radius and minimum delivery amount are server-owned
- order/payment status transitions are server-owned
- checkout submits the existing API payload shapes
- auth checks in the frontend are UX only; backend authorization remains the
  source of truth
- PII such as phone numbers, addresses, names, and comments must not be logged

Visual redesign alone should not require backend changes. If a screenshot shows
a feature Aura Coffee does not have, first decide whether it is only a visual
pattern or a real product behavior change. Real product behavior changes must
start with the PDD/GRACE artifacts before code.

## Workflow

### 1. Drop References

Paste screenshots into `docs/design/screenshots/` with ordered filenames. Include
at least one screenshot per target screen. If possible, include both normal and
edge states such as empty cart, loading, error, selected item, active order, and
delivery checkout.

### 2. Create A Reference Map

Before editing code, produce a short design map in this directory, usually:

```text
docs/design/reference-map.md
```

The map should list:

- screenshot filename
- intended Aura route or component
- visible reusable UI parts
- data requirements from existing APIs
- behaviors that are visual-only
- behaviors that might be product changes
- risks against PDD invariants

No code should be changed during this mapping step.

### 2a. Decide The Media Contract

The reference design relies on videos of drinks, not static product photos. In
Aura Coffee this is a real product/media capability because the current menu
contract exposes `image_url` only.

**Decision:** use the video-first path with Aura-owned/generated drink videos.
Videos are product presentation only; they must not affect pricing, availability,
cart validation, payment, or order state.

**Asset decision:** generated videos are local static assets because they are
created once per menu item and changed rarely. Store URLs in the database as
public paths to committed/deployed assets, not as binary blobs and not as private
storage URLs.

**Admin decision:** the admin menu editor must support media fields in the first
media-contract wave so staff can attach or change local static asset paths from
the existing menu item form.

**Modifier decision:** grouped modifier categories and modifier quantities are a
separate product change. The video-led redesign must keep the current flat
modifier model unless a later PDD/GRACE packet explicitly changes it.

There are two safe paths:

- **Visual pass first:** restyle the customer UI using existing `image_url`
  posters/static images. This is fastest and should remain frontend-only.
- **Video-first pass:** add an explicit menu media contract before building the
  final experience. Do not overload `image_url` with `.mp4` URLs.

A video-first pass should define:

- menu item media fields such as `media_type`, `media_url`, and
  `media_poster_url`
- supported formats, aspect ratios, max file sizes, and local static asset path
  rules
- autoplay rules: muted, looped, `playsInline`, lazy-loaded, paused offscreen
- reduced-motion and low-bandwidth fallback to poster images
- admin menu workflow for attaching owned media paths to menu items

Because this changes the product/API/data contract, update the PDD/GRACE
artifacts first if we choose the video-first path.

### 3. Define Design Tokens

Extract only the durable style choices into frontend tokens:

- brand colors and neutrals
- typography scale
- border radius
- elevation/shadow rules
- spacing rhythm
- safe-area and mobile viewport behavior

Prefer updating `web/customer/src/index.css`, Tailwind classes, and existing UI
primitives before adding new abstractions. Avoid new dependencies unless there
is a clear need.

### 4. Implement In Small Packets

Work screen by screen, keeping each packet narrow:

1. App shell and bottom navigation.
2. Menu categories and product cards.
3. Item detail modal and add-to-cart controls.
4. Cart and sticky checkout summary.
5. Checkout pickup/delivery flow.
6. Drink video media support, if selected.
7. Orders, profile, addresses, and loyalty screens.

Each packet should preserve existing route paths, API calls, store behavior,
i18n keys, and tests unless the packet explicitly includes a product change.

### 5. Verify Each Packet

For pure customer-frontend visual packets, run the narrowest useful checks from
`web/customer`:

```bash
npm test
npm run build
```

When the app needs browser verification, run the project stack and compare
mobile screenshots at realistic widths such as 375px, 390px, and 430px.

GRACE LDD assertions are normally not required for pure visual changes. They
become required if the change touches backend state transitions, transaction
boundaries, auth/role logic, OTP/SMS, payments, PII logging, or required log
markers from `docs/verification-plan.xml`.

### 6. Review Against Business Logic

Before considering a screen done, check:

- no pricing or delivery calculations moved into React
- no invented order states or payment states
- checkout still uses server validation and server error messages
- bilingual user-facing text remains in i18n resources
- mobile layout handles long RU/EN text without overlap
- raw PII is not logged
- tests/build pass or failures are documented

### 7. Refresh GRACE Artifacts Only When Needed

Do not update PDD/XML artifacts for visual restyling only. Update them only when
the product behavior, module ownership, dependency graph, verification plan, or
state-machine behavior changes.

## Codex Prompt Pattern

Use two-step prompts for this work:

```text
Analyze the screenshots in docs/design/screenshots and create a reference map.
Do not edit app code yet. Use the GRACE/PDD boundaries.
```

Then:

```text
Implement packet 1 from docs/design/reference-map.md: app shell and bottom nav.
Keep routes/API/business logic unchanged. Run the narrowest customer frontend
verification.
```

This keeps design interpretation separate from code changes and makes regressions
easier to isolate.
