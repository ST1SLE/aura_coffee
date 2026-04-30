# Video-Led Customer Menu GRACE Plan

This plan covers adding first-class drink video media and then adapting the
customer UI toward the reference screenshots. It is a plan only; no runtime code
is implemented here.

## Scope And Target Modules

Primary modules:

- `M-DATABASE`: migration for presentational menu media fields.
- `M-CORE-API`: ORM/schema/public/admin menu response and mutation changes.
- `M-WEB-CUSTOMER`: video-aware menu/product UI.
- `M-WEB-ADMIN`: admin menu item form support for media paths.

Supporting surfaces:

- local static media asset directory and menu seed data.
- `docs/PRODUCT_DESIGN_DOCUMENT.md`, `docs/development-plan.xml`,
  `docs/verification-plan.xml`, and `docs/knowledge-graph.xml` stay aligned.

Out of scope for the first execution wave:

- changing pricing, order creation, payment, loyalty, delivery, or state
  machines
- copying third-party media
- favorites, gifts, mini-games, nutrition, allergen data, and payment-provider
  selection unless separately specified
- grouped modifier categories or modifier quantities unless explicitly approved

## Relevant GRACE Anchors

- PDD §5.2 menu data model: media fields live on `menu_items`.
- PDD INV-004: media must not touch atomic financial flows.
- PDD INV-014: media migration must not mutate `order_items`.
- PDD INV-015: public media URLs must not expose secrets or signed storage
  credentials.
- PDD INV-016: media must not introduce order/payment state transitions.
- `docs/verification-plan.xml` V-M-DATABASE, V-M-CORE-API, V-M-WEB-CUSTOMER.
- `docs/knowledge-graph.xml` M-WEB-CUSTOMER -> M-CORE-API dependency.

## Required Invariants

- Pricing remains server-owned and stored in kopecks.
- Availability remains server-owned.
- Cart/add-to-cart payload shape remains:
  `menu_item_id`, `size_option_id`, `modifier_ids`, `quantity`.
- Checkout still uses the existing core-api order creation flow.
- `order_items` snapshots do not include or depend on media fields.
- Media is public presentation data only, not PII and not secret-bearing.
- Frontend auth remains UX-only; server authorization remains authoritative.

## Decisions Already Made

- Use Aura-owned/generated videos, not third-party coffee-chain videos.
- Implement a real media contract instead of overloading `image_url`.
- Keep `image_url` as a legacy/poster fallback during migration.
- Use video only where safe for UX: muted, looped, playsInline, lazy-loaded,
  pausable, and with poster fallback.
- Store generated videos as local static frontend assets because they are set
  once and change rarely.
- Store only public static asset paths in the database, never binary video data.
- Add admin menu item form support for media fields in the first media-contract
  wave.
- Keep grouped modifier categories and modifier quantities as a separate product
  change.

## Decisions To Confirm Before Execution

Stop and ask if these cannot be inferred from local context:

1. First asset source: generated placeholder videos for development, or real
   final drink videos before UI work begins.
2. Exact static asset directory convention, recommended:
   `web/customer/public/media/menu/{item-slug}/hero.mp4` and
   `web/customer/public/media/menu/{item-slug}/poster.webp`.
3. Whether admin should validate paths only by string format in wave 1, or also
   preview/check local asset existence in the browser.
4. Seasonal navigation: map reference tabs to existing categories, or add a
   separate tag/collection model later.

## Smallest Viable Change

Add nullable menu media fields and display them in the customer menu while
leaving ordering behavior unchanged:

```text
menu_items.media_type        image | video | null
menu_items.media_url         nullable string URL
menu_items.media_poster_url  nullable string URL
```

Compatibility:

- For old rows, `media_type = null`, `media_url = null`,
  `media_poster_url = null`, and `image_url` continues to render.
- For videos, `media_type = video`, `media_url` points to the generated video,
  and `media_poster_url` points to the generated poster image.
- For local static assets, `media_url` and `media_poster_url` are public absolute
  paths such as `/media/menu/iced-matcha-taro/hero.mp4` and
  `/media/menu/iced-matcha-taro/poster.webp`.

## Worktree Safety Model

Every implementation packet must run in its own Git worktree. Do not implement
multiple packets in the same working tree unless the user explicitly approves a
single sequential worktree.

Recommended worktrees:

```text
.worktrees/video-media-backend
.worktrees/video-media-admin
.worktrees/video-media-customer-media
.worktrees/video-media-customer-redesign
.worktrees/video-media-polish
```

Rules:

- Create worktrees from the same clean base branch.
- Each worktree owns a disjoint write scope.
- Never revert files outside the worktree's packet.
- Rebase or merge in packet order only after the packet's verification passes.
- If two worktrees need the same file, split the work into sequential packets
  instead of parallel edits.
- Each packet final report must list changed files, verification commands,
  GRACE/LDD decision, asserted markers, redaction checks, and untested risks.
- Close or remove stale worktrees after merge.

Suggested merge order:

1. Backend/database/admin API media contract.
2. Admin menu form media fields.
3. Customer `MenuMedia` foundation.
4. Customer menu/item-detail redesign.
5. Cart/checkout/profile polish.

## Codex Agent Work Plan

Only spawn sub-agents if explicitly requested for parallel agent work. If agents
are used, keep write scopes disjoint.

### Packet 0: Baseline Inspection

Status: [x] Complete — implementation checklist and stop-and-ask conflicts
reported.

Owner: main Codex agent.

Read:

- `database/migrations/versions/*menu*`
- `packages/shared/src/shared/models/menu.py`
- `services/core-api/src/core_api/schemas/menu.py`
- `services/core-api/src/core_api/services/menu_public.py`
- `services/core-api/src/core_api/services/menu_admin.py`
- `services/core-api/src/core_api/routers/menu_admin.py`
- `web/customer/src/api/menuTypes.ts`
- `web/customer/src/pages/Menu/*`
- `web/admin/src/api/menu.ts`
- `web/admin/src/pages/Menu/MenuItemFormDialog.tsx`
- current menu/admin seed files

Output:

- final implementation checklist with exact files
- any stop-and-ask conflicts

### Packet 1: Database And Backend Media Contract

Status: [x] Complete — implemented and verified in
`.worktrees/video-media-backend`, then merged into the main worktree.

Owner: backend/database worker if agents are used.

Worktree:

```bash
git worktree add .worktrees/video-media-backend HEAD
```

Write scope:

- `database/migrations/versions/`
- shared/core menu ORM model files
- core-api menu schemas/services
- core-api admin menu schemas/services/routes as needed
- backend tests for public and admin menu media responses/mutations

Expected changes:

- migration adds nullable media fields
- ORM model exposes fields
- Pydantic public and admin menu DTOs include media fields
- public menu service maps fields
- admin menu create/update accepts `media_type`, `media_url`,
  `media_poster_url`
- validation forbids secret-bearing URLs and malformed media combinations
- tests assert legacy image fallback, video fields, and admin update behavior

Verification:

```bash
env PYTHONPATH=services/core-api/src:packages/shared/src pytest services/core-api/tests/ -k menu -v
```

If Docker DB is required:

```bash
docker compose exec core-api pytest services/core-api/tests/ -k menu -v
```

LDD:

- Not expected if limited to menu media read/schema behavior.
- Because admin menu mutation endpoints already rely on server-side admin auth,
  existing auth tests should remain green. New LDD assertions are not expected
  unless auth/role-check implementation is changed.
- Required if the packet changes auth behavior, state transitions,
  transactions, payments, OTP/SMS, PII logging, or required log markers.

### Packet 2: Admin Menu Media Fields

Status: [x] Complete — implemented and verified in
`.worktrees/video-media-admin`, then applied to the main worktree.

Owner: admin frontend worker if agents are used.

Worktree:

```bash
git worktree add .worktrees/video-media-admin HEAD
```

Write scope:

- `web/admin/src/api/menu.ts`
- `web/admin/src/pages/Menu/MenuItemFormDialog.tsx`
- `web/admin/src/pages/Menu/MenuItemFormDialog.test.tsx`
- admin i18n locale files

Expected changes:

- admin menu API types include media fields
- menu item form includes media type, video path, and poster path controls
- existing `image_url` field remains as legacy image/poster fallback
- form validates the required poster path when `media_type = video`
- form does not upload binaries; it stores local static asset paths only
- optional preview can be image/poster-only unless video preview is trivial

Verification:

```bash
cd web/admin && npm test -- MenuItemFormDialog
cd web/admin && npm run build
```

### Packet 3: Customer `MenuMedia` Foundation

Status: [x] Complete — implemented and verified in
`.worktrees/video-media-customer-media`, then applied to the main worktree.

Owner: frontend worker if agents are used.

Worktree:

```bash
git worktree add .worktrees/video-media-customer-media HEAD
```

Write scope:

- `web/customer/src/api/menuTypes.ts`
- `web/customer/src/components/` or `web/customer/src/pages/Menu/`
- focused Vitest tests

Expected changes:

- add a reusable `MenuMedia` component
- render `<video>` for `media_type = video`
- render poster/image fallback for missing, failed, or reduced-motion media
- no business payload changes

Verification:

```bash
cd web/customer && npm test -- MenuMedia
cd web/customer && npm run build
```

### Packet 4: Menu And Item Detail Redesign

Status: [x] Complete — implemented and verified in
`.worktrees/video-media-customer-redesign`, visually checked with a temporary
Vite harness, then applied to the main worktree.

Owner: frontend worker or main agent.

Worktree:

```bash
git worktree add .worktrees/video-media-customer-redesign HEAD
```

Write scope:

- `web/customer/src/components/Layout.tsx`
- `web/customer/src/pages/Menu/MenuPage.tsx`
- `web/customer/src/pages/Menu/MenuItemCard.tsx`
- `web/customer/src/pages/Menu/ItemDetail.tsx`
- `web/customer/src/index.css`
- tests for menu/item detail behavior

Expected changes:

- dark mobile-first shell
- horizontal category browsing
- media-led product cards
- immersive item detail using `MenuMedia`
- fixed add-to-cart bar
- unchanged `addItem` payload

Verification:

```bash
cd web/customer && npm test -- Menu
cd web/customer && npm run build
```

Visual verification:

- run local stack
- capture mobile widths 375px, 390px, 430px
- confirm videos/posters render and text does not overlap in RU/EN

### Packet 5: Cart, Checkout, Profile Polish

Status: [x] Complete — implemented and verified in
`.worktrees/video-media-polish`, then applied to the main worktree.

Owner: frontend worker or main agent.

Worktree:

```bash
git worktree add .worktrees/video-media-polish HEAD
```

Write scope:

- `web/customer/src/pages/Cart/*`
- `web/customer/src/pages/CheckoutPage.tsx`
- `web/customer/src/pages/Profile*`
- related tests/i18n

Expected changes:

- match dark rounded mobile visual language
- keep checkout API and server error handling
- no new payment behavior
- no raw PII logging

Verification:

```bash
cd web/customer && npm test
cd web/customer && npm run build
```

## What Could Go Wrong

- Video files are too large and hurt mobile performance.
- Local static asset paths break if nginx/Vite routing does not serve
  `/media/menu/*` consistently in dev and production.
- Autoplay behavior differs by browser if videos are not muted/playsInline.
- Missing poster images create blank cards.
- Reduced-motion users still get motion if the component does not check media
  preferences.
- Overeager UI redesign changes cart/checkout payloads.
- Media URL storage accidentally exposes private storage credentials.
- Admin seed data diverges from production content workflow.
- Admin form accepts a path to an asset that was not committed/deployed.
- Frontend tests become brittle if they assert exact layout instead of behavior.

## Rollback Path

- Database fields are additive and nullable; old `image_url` rendering remains
  valid.
- Frontend `MenuMedia` can fall back to image-only mode.
- UI packets can be reverted independently if route/API contracts are preserved.
- If video hosting is not ready, keep `media_type/media_url` null and ship the
  poster-based visual pass without changing backend behavior.
- If admin media support causes delays, merge backend nullable fields first and
  keep existing `image_url` editing until the admin packet is fixed.

## Verification Checklist

- PDD/XML/docs updated before implementation.
- Migration applies cleanly.
- Public menu response includes media fields and legacy fallback behavior.
- No order, payment, delivery, loyalty, or state-machine tests are changed just
  for media.
- Customer menu renders video, poster fallback, and no-media states.
- Add-to-cart payload remains unchanged.
- Checkout still uses core-api validation.
- `npm test` and `npm run build` pass in `web/customer`.
- Backend menu tests pass.
- Admin menu form tests/build pass.
- LDD final report states LDD not applicable for pure media/UI packets, or lists
  markers asserted if a packet touches a GRACE-sensitive path.
