## 1. Prereqs

- [x] 1.1 [web-customer] PREREQ: Confirm backend endpoints and zod-friendly schema shape by reading `services/core-api/app/schemas/loyalty.py` and the loyalty router — no code change, just capture the wire shape for step 2.

## 2. API client (logic — RED/GREEN/REFACTOR)

- [x] 2.1 [web-customer] RED: add `web/customer/src/api/loyalty.test.ts` with vitest cases asserting `getLoyaltyBalance()` hits `GET /api/v1/profile/loyalty` and rejects malformed payloads; `listLoyaltyTransactions(page, per_page)` hits `/api/v1/profile/loyalty/transactions?page&per_page` and parses items. Tests MUST fail (no module yet).
- [x] 2.2 [web-customer] GREEN: create `web/customer/src/api/loyalty.ts` exporting zod schemas (`LoyaltyBalanceSchema`, `LoyaltyTransactionSchema`, `LoyaltyTransactionsPageSchema`), inferred types, and the two async functions using the shared authenticated `client`. Passes 2.1.
- [x] 2.3 [web-customer] REFACTOR: align naming/exports with `api/addresses.ts` + `api/orders.ts`; ensure no duplication of fetch plumbing.

## 3. TransactionRow component (IMPL → TEST)

- [x] 3.1 [web-customer] IMPL: create `web/customer/src/pages/Profile/Loyalty/TransactionRow.tsx` implementing three-column layout, sign-based color, localized type labels, optional `/orders/{id}` link with short-id, and `balance_after` suffix.
- [x] 3.2 [web-customer] TEST: create `web/customer/src/pages/Profile/Loyalty/TransactionRow.test.tsx` covering: positive amount → green class; negative → red; zero → default; `order_id=null` → no link; `order_id=uuid` → link renders with first-8-chars label and href `/orders/<uuid>`; localized type label.

## 4. LoyaltyPage (IMPL → TEST)

- [x] 4.1 [web-customer] IMPL: create `web/customer/src/pages/Profile/Loyalty/LoyaltyPage.tsx` with `useQuery(['loyalty','balance'])` for header and `useInfiniteQuery(['loyalty','transactions'])` for history; empty state copy; load-more trigger returning next page when previous was full.
- [x] 4.2 [web-customer] TEST: create `web/customer/src/pages/Profile/Loyalty/LoyaltyPage.test.tsx` covering balance + lifetime render, empty state, load-more pagination fetch, and clicking a row with `order_id` navigates to `/orders/{order_id}`.

## 5. LoyaltyCard component (IMPL → TEST)

- [x] 5.1 [web-customer] IMPL: create `web/customer/src/pages/Profile/LoyaltyCard.tsx` using the same `['loyalty','balance']` query key; renders title, big balance number, and "История" link to `/profile/loyalty`.
- [x] 5.2 [web-customer] TEST: create `web/customer/src/pages/Profile/LoyaltyCard.test.tsx` asserting balance rendered and link target is `/profile/loyalty`.

## 6. Wiring

- [x] 6.1 [web-customer] IMPL: edit `web/customer/src/pages/ProfilePage.tsx` to import and render `<LoyaltyCard />` between the language block and the logout button.
- [x] 6.2 [web-customer] IMPL: edit `web/customer/src/App.tsx` to add the `<Route path="/profile/loyalty" element={<LoyaltyPage />} />` entry under the existing `ProtectedRoute` where `/profile/addresses` lives.

## 7. i18n

- [x] 7.1 [web-customer] IMPL: edit `web/customer/src/i18n/locales/ru.json` adding `pages.profile.loyaltyCard.{title,balance_suffix,view_history}` and `pages.loyalty.{title,balance_label,lifetime_label,history_title,empty,load_more,txType.{accrual,redemption,reversal,admin_adjustment},txRow.{balance_after,order_link}}`.
- [x] 7.2 [web-customer] IMPL: edit `web/customer/src/i18n/locales/en.json` adding the same keys in English.

## 8. Verification

- [x] 8.1 [web-customer] VERIFY: run `npm run test` inside `web/customer/` — all new vitest suites green, no regressions.
- [x] 8.2 [web-customer] VERIFY: run `npm run typecheck` (or project equivalent) — no TS errors introduced.
