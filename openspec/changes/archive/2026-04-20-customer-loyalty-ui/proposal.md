## Why

Customers need visibility into their loyalty point balance and transaction history from the web app. Backend loyalty schema and endpoints exist (PDD §3, §4.4), but the customer frontend has no UI to surface balance or history. This change closes that gap as part of Phase 5 (Loyalty & Promocodes).

## What Changes

- New route `/profile/loyalty` (ProtectedRoute) — balance header + paginated transaction history.
- New entry-point card on `/profile` (`LoyaltyCard`) showing balance and linking to `/profile/loyalty`.
- New API client module `api/loyalty.ts` wrapping `GET /api/v1/profile/loyalty` and `GET /api/v1/profile/loyalty/transactions` with zod-validated responses.
- i18n keys for RU + EN covering card, page, transaction types, and row metadata.
- Transaction row UI: color-coded amount (+green / −red / =black), optional link to owning order by short UUID, localized transaction type labels.
- Vitest coverage for `LoyaltyPage`, `LoyaltyCard`, `TransactionRow`.

## Capabilities

### New Capabilities
- `customer-loyalty-ui`: Customer-facing React UI for viewing loyalty balance, lifetime accrued total, and paginated loyalty transaction history.

### Modified Capabilities
(none — `/profile` gains a card import but no spec-level requirement change to `user-profile-screen`.)

## Impact

- Code: `web/customer/src/api/loyalty.ts` (new), `web/customer/src/pages/Profile/Loyalty/` (new), `web/customer/src/pages/Profile/LoyaltyCard.tsx` (new), `web/customer/src/pages/ProfilePage.tsx` (edit), `web/customer/src/App.tsx` (edit), `web/customer/src/i18n/locales/{ru,en}.json` (edit).
- APIs consumed (existing backend): `GET /api/v1/profile/loyalty`, `GET /api/v1/profile/loyalty/transactions?page&per_page`.
- No schema, backend, or migration changes.
- No polling/WebSocket; no redeem action (that belongs in checkout path).
- PDD references: §3 Loyalty, §4.4 Customer Frontend, §7.1 Phase 5 item 2.

## Non-Goals

- Redeeming points in this UI — spending is only in the checkout flow (separate change).
- Realtime updates / polling / WebSocket — balance is refreshed on page navigation only.
- Admin adjustments UI — admin tooling is out of scope for this change.
- Exporting transaction history — not required by PDD.

## MVP Phase

Phase 5 — Loyalty & Promocodes (PDD §7.1 item 2).
