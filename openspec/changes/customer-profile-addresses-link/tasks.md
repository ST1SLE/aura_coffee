## 1. i18n keys

- [x] 1.1 PREREQ [web-customer] Add `pages.profile.addressesLink.title` and `pages.profile.addressesLink.subtitle` to `web/customer/src/i18n/locales/ru/common.json` (values: "Адреса доставки" / "Управление сохранёнными адресами").
- [x] 1.2 PREREQ [web-customer] Add `pages.profile.addressesLink.title` and `pages.profile.addressesLink.subtitle` to `web/customer/src/i18n/locales/en/common.json` (values: "Delivery addresses" / "Manage saved addresses").

## 2. UI entry-point on ProfilePage

- [x] 2.1 IMPL [web-customer] In `web/customer/src/pages/ProfilePage.tsx`, insert a `<Link to="/profile/addresses">` card between the language block and `<LoyaltyCard />`. Card renders `t('pages.profile.addressesLink.title')` as primary text and `t('pages.profile.addressesLink.subtitle')` as secondary. Styling mirrors `LoyaltyCard` (same border/padding/hover utility classes). No data fetch, no `useEffect`.

## 3. Test

- [x] 3.1 TEST [web-customer] Create `web/customer/src/pages/ProfilePage.test.tsx`. One test `renders link to /profile/addresses` that mounts `ProfilePage` inside a `MemoryRouter` with a mocked `getProfile` (returning a minimal valid `ProfileData`) and asserts `getByRole('link', { name: /адреса|addresses/i })` has `href="/profile/addresses"`. Mirror the shape of `web/customer/src/pages/Profile/LoyaltyCard.test.tsx:42-55`.

## 4. Verify

- [x] 4.1 VERIFY [web-customer] Run `npm test` inside the web-customer container — expect all existing tests green plus the new one from 3.1 passing. Report total pass count. (Result: 31 files / 170 tests passed; new `ProfilePage.test.tsx` 1/1 green.)
- [ ] 4.2 VERIFY [web-customer] Manual smoke: open `$BASE/profile` in a browser after login; confirm the "Адреса доставки" card is visible and clicking navigates to `/profile/addresses`, which renders `AddressesPage` with the two seeded addresses from §1.4-B of `docs/phase6_manual_test_scenarios.md`.
