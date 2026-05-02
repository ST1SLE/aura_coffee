# Customer UX / Design / Completeness Audit

Date: 2026-05-02  
Scope: `web/customer`, `docs/design`, customer-facing PDD flows.  
Method: source inspection, GRACE/PDD comparison, existing Vitest/lint run, light runtime probes against `http://localhost:240`. No runtime code was modified.

## Executive Summary

The customer app has a solid base for the menu/cart/profile slice: dark mobile-first shell, media-capable menu cards, item customization, server-owned cart snapshots, OTP login, saved addresses, and loyalty balance/history all exist and have good unit coverage.

The largest product gap is after checkout. `CheckoutPage` submits an order and navigates to `/orders/:id`, but the SPA only registers `/orders`, and `OrdersPage` is still a placeholder. That means payment redirect/polling, order status freshness, cancellation, history, and reorder are not usable from the customer UI even though the backend has several of those endpoints.

The Drinkit-inspired design pass is partially real on menu/detail/cart, but not yet coherent across auth, checkout, addresses, loyalty, and order status. The app also lacks the fast mobile ordering affordances that Drinkit-style UX depends on: persistent cart visibility on menu, full checkout summary, payment state, and repeat-order surfaces.

## What Works

- App shell: `web/customer/src/components/Layout.tsx` provides a dark sticky header, desktop nav, mobile bottom nav, language switcher, and logout.
- Menu browsing: `MenuPage`, `MenuItemCard`, and `MenuMedia` render categories, availability, image/video media, loading/error/empty states, and localized menu data from `/api/v1/menu`.
- Item detail: `ItemDetail` supports size selection, flat modifiers, unavailable modifier disabling, add-to-cart, success/error status text, and video/poster presentation.
- Cart: `CartPage` and `CartLine` handle loading/error/empty states, quantity changes, removal, clear cart, 410 expired-cart recovery, and server-provided line totals.
- OTP login: `LoginPage`, `VerifyPage`, `PhoneInput`, `OTPInput`, and `ResendTimer` cover phone entry, masked phone display, OTP paste, resend cooldown, and typed auth errors.
- Profile: `ProfilePage` supports masked phone, display name edit, language update, saved-address navigation, loyalty balance card, and logout.
- Saved addresses: `AddressesPage`, `AddressForm`, and `AddressAutocomplete` cover CRUD, default address, Yandex suggest fallback, create-time geocoding for typed addresses, localized server errors, and no raw-address console logging in the tested checkout save failure.
- Loyalty: `LoyaltyCard`, `LoyaltyPage`, and `TransactionRow` cover balance, lifetime accrued, paginated transactions, localized transaction types, signed amounts, and links to related orders.
- Design docs: `docs/design/drinkit-design-replication-guide.md` clearly separates safe design adaptation from product/API changes and calls out sticky cart/payment/status/repeat patterns.

## PDD Coverage Gaps

| Area | PDD Requirement | Current Customer UX | Severity |
| --- | --- | --- | --- |
| Order detail/status | PDD §4.4 requires order status page freshness within 10s; PDD §6.1 requires confirmation URL polling for payment | No `/orders/:id` route; checkout and loyalty links route into 404 after auth | P0 |
| Payment handoff | PDD §6.1 says customer gets `confirmation_url` via polling and is redirected to YuKassa; zero-total orders skip YuKassa | `createOrder` returns `confirmation_url`, but UI never polls, redirects to payment, or shows payment state | P0 |
| Order history | PDD §4.4 / §7.7 require history | `/orders` is placeholder only | P0 |
| Repeat order | PDD §7.7 requires repeat-order with skipped-item feedback | Backend route exists; no customer UI/API client | P1 |
| Customer cancellation | INV-005 / PDD §7.6 allow customer cancel only in `PAID` before `PREPARING` | Backend route exists; no customer action/status UI | P1 |
| Promocode | PDD §7.2 includes `promocode_code` validation and non-silent rejection | Backend schema supports it; checkout has no promo input and frontend payload type omits it | P1 |
| Points redemption | PDD §7.2 allows up to 100% goods amount with points | Loyalty is display-only; checkout has no points control and payload type omits `points_to_use` | P1 |
| Requested time | PDD §7.5 covers ASAP/specific time and working-hours errors | Checkout has no ASAP/scheduled time UI and payload type omits `requested_time` | P1 |
| Delivery fee UX | PDD §7.4 says show free-delivery difference and minimum delivery errors | Checkout relies on final server error only; no summary/progress before submit | P1 |
| Account deletion | PDD §6.5 / INV-013 include customer-requested deletion and PII anonymization | No customer deletion UI found | P2/PDD-dependent backend gap |

## Design And UX Inconsistencies

- Auth screens still look like an old light-form scaffold. `PhoneInput` uses gray borders/text and a hardcoded placeholder inside a dark app; OTP inputs have no visible Aura surface or Drinkit-style treatment.
- Checkout is functionally sparse: no cart summary, no subtotal/discount/points/delivery/total breakdown, no payment state, no sticky pay action, and no clear "what happens next" status.
- `/profile/addresses` and `/profile/loyalty` use simpler border/card styling than the redesigned menu/cart/profile shell, so the visual system feels unfinished beyond the main ordering screens.
- Menu has category tabs and media cards but no persistent cart bar or item-count badge on the menu surface. This weakens fast repeat ordering and makes the bottom nav carry too much responsibility.
- Drinkit-like "usual order", recent order, ready-status card, and post-order feedback patterns are not present. Some are product changes and should stay out of scope until PDD-approved, but order status and repeat are already PDD requirements.
- Unavailable items are visible and disabled, which is good, but empty media renders as a plain dark rectangle. It needs a branded fallback treatment for products without media.
- The `/menu/:categoryId` route exists but `MenuPage` does not read the route param, so deep links to a category do not select/scroll to that category.

## Accessibility And I18n Findings

- `MenuItemCard` is a `div role="button"` instead of a native button/link. It has keyboard handling, but native semantics would be more robust.
- `ItemDetail` close button uses `aria-label="close"` instead of i18n.
- `OTPInput` fields need accessible labels such as "Digit 1 of 6"; screen readers currently get six unlabeled textboxes.
- `AddressAutocomplete` should use combobox semantics (`role="combobox"`, `aria-expanded`, `aria-controls`, active option, keyboard up/down/enter). It currently supports mouse selection but not full keyboard navigation.
- `AddressesPage` hardcodes Russian apartment/entrance/floor prefixes (`кв.`, `подъезд`, `этаж`) even in English mode.
- `LoginPage` hardcodes loading as `...`; `PhoneInput` hardcodes the placeholder instead of using `auth.phone.placeholder`.
- Several focus/error flows need polish: after checkout server error, focus should move to the alert; after opening `ItemDetail`, focus should enter the dialog and return to the card on close.
- Mobile text overflow needs screenshot verification for long RU strings in checkout/address buttons and profile cards.

## Prioritized Fixes

### P0 - Make Checkout Lead To A Real Order Experience

1. Add `GET /api/v1/orders/{id}` client method and `OrderDetailPage` at `/orders/:orderId`.
2. After `createOrder`, route to the detail/status page and poll:
   - 1-2s while waiting for `confirmation_url` in `CREATED`.
   - Redirect to `confirmation_url` when present.
   - 10s status refresh after payment/status phase, per PDD §4.4.
3. Render status timeline for `CREATED`, `PAID`, `PREPARING`, `READY`, `IN_DELIVERY`, `COMPLETED`, `CANCELLED`.
4. Show receipt totals from server response and immutable item snapshots.
5. Add customer cancel button only when status is `PAID`; call `POST /api/v1/orders/{id}/cancel`.
6. Handle zero-total orders (`status=PAID`, no `confirmation_url`) as successful payment without redirect.

GRACE/LDD: required for implementation/tests touching order actions, payment/status polling behavior, and cancellation.

### P0 - Replace Placeholder Orders With Real History

1. Add `GET /api/v1/orders?page&per_page` customer client matching `order_history.py` response shape (`orders`, not `items`).
2. Replace `OrdersPage` placeholder with paginated history, active-order section, empty/error/loading states, and links to `/orders/:id`.
3. Add tests for empty history, active orders, item snapshot rendering, and broken-link regression from loyalty rows.

### P1 - Complete Checkout Inputs And Server-Owned Summary

1. Add promo code input that sends `promocode_code` and renders server rejection details.
2. Add points redemption control backed by `getLoyaltyBalance`; send `points_to_use`.
3. Add ASAP/scheduled time selector; send `requested_time`.
4. Show a server-owned order estimate or cart summary before submit. If there is no estimate endpoint, add a GRACE/PDD packet for one instead of calculating discounts/fees in React.
5. Show delivery minimum/free-delivery guidance from shop settings or an estimate endpoint.

### P1 - Implement Repeat Order

1. Add `POST /api/v1/orders/{id}/repeat` client.
2. Add "Repeat" buttons on history/detail.
3. On success, navigate to cart and show skipped items/modifiers from backend response.
4. Test all-skipped, partial-skipped, and successful repeat flows.

### P1 - Finish Drinkit-Inspired Mobile Ordering Affordances

1. Add item-count badge to cart nav and a sticky cart CTA on menu when cart has items.
2. Make cart/checkout a single continuous purchase surface with a persistent bottom action.
3. Add product-media fallback art/state for items without media.
4. Let the category rail update active category on scroll and respect `/menu/:categoryId`.

### P2 - Polish Profile, Addresses, Loyalty, And Auth Design

1. Bring auth/profile subpages onto the same `aura-surface` visual system.
2. Replace `window.confirm` address deletion with an in-app modal/sheet.
3. Add better address empty state and saved-address selection details in checkout.
4. Add account deletion UX only after backend/PDD endpoint confirmation.
5. Fix hardcoded/i18n text and accessibility issues listed above.

## Suggested Test And Screenshot Matrix

Add Playwright/manual screenshot checks at 375x812, 390x844, 430x932, 768x1024, and 1280x800:

- `/login`: empty, invalid phone, submitting, rate-limited.
- `/login/verify`: empty, paste code, invalid, expired, resend cooldown.
- `/menu`: loading, error, empty, normal seeded menu, unavailable item, no-media item.
- Item detail: video item, image fallback item, no-media item, unavailable modifier, long RU/EN names.
- `/cart`: empty, loading, expired toast, populated with modifiers, quantity 99, sticky footer.
- `/checkout`: pickup, delivery saved, delivery new, maps degraded, out-of-radius, below minimum, promo failure, points maxed, scheduled time error.
- `/orders`: empty, active order, completed history, cancelled order.
- `/orders/:id`: `CREATED` payment waiting, `PAID`, `PREPARING`, `READY`, delivery flow, cancellation allowed/forbidden, zero-total paid order.
- `/profile`, `/profile/addresses`, `/profile/loyalty`: loading/error/empty/populated, long text, English mode.

## Verification Performed

Commands run:

```bash
git status --short
find docs/audit-results -maxdepth 2 -type f | sort | tail -50
sed -n '1,220p' web/customer/AGENTS.md
rg -n "Customer|customer|OTP|loyalty|promocode|checkout|delivery|pickup|profile|reorder|order history|address|cart" docs/PRODUCT_DESIGN_DOCUMENT.md
sed -n '130,170p' docs/PRODUCT_DESIGN_DOCUMENT.md
sed -n '580,780p' docs/PRODUCT_DESIGN_DOCUMENT.md
sed -n '463,515p' docs/PRODUCT_DESIGN_DOCUMENT.md
sed -n '360,402p' docs/PRODUCT_DESIGN_DOCUMENT.md
sed -n '1,260p' docs/design/drinkit-design-replication-guide.md
find web/customer/src -maxdepth 3 -type f | sort
curl -sS -m 5 -D - http://localhost:240/api/v1/menu -o /tmp/aura-menu-body.json
curl -sS -m 5 -D - http://localhost:240/api/v1/cart -o /tmp/aura-cart-body.json
npm test
npm run lint
```

Results:

- `npm test`: passed, 33 files / 186 tests. Vitest emitted existing React `act(...)` warnings in `App.menuCart.test.tsx` and `LoyaltyCard.test.tsx`.
- `npm run lint`: passed.
- Runtime probe: `GET /api/v1/menu` returned seeded QA menu with 3 categories, 5 items, video/poster media fields, unavailable item/modifier coverage.
- Runtime probe: unauthenticated `GET /api/v1/cart` returned `401 Not authenticated`, as expected.
- `npm run build` was intentionally skipped because this repo tracks `web/customer/tsconfig.tsbuildinfo` and has `web/customer/dist`; the audit instruction allowed only creating/updating this markdown report.

## GRACE / LDD Decision

This audit created documentation only and did not modify runtime code, backend state transitions, transaction boundaries, auth/OTP/SMS behavior, payment webhooks, PII logging, or required marker emitters. LDD assertions were not applicable.

Future fixes for checkout/order status/payment/cancellation/reorder will touch order/payment/customer flows and should apply the GRACE verification gate, including required order/payment LDD marker assertions and INV-013 redaction checks where logs or PII are involved.
