## 1. API client tests (RED)

- [x] 1.1 RED [web-customer] Update `web/customer/src/api/addresses.test.ts` fixture `addr()` helper: replace `text` with `address_text`, replace `is_primary` with `is_default` — test file MUST fail to compile against current `addresses.ts` (which still exports `text`/`is_primary`).
- [x] 1.2 RED [web-customer] In `web/customer/src/api/addresses.test.ts` rewrite `listAddresses` test: mock `authenticatedFetch` to resolve with a bare array `[addr(), addr()]` (not `{items: ...}`); assert result has length 2. Fails against current implementation that parses `{ items }`.
- [x] 1.3 RED [web-customer] In `addresses.test.ts` add `listAddresses` test: mock response with legacy `{ items: [...] }` body; assert result is `[]` (fail-soft guard). Fails today because current code returns `body.items ?? []` which would succeed — the new guard returns `[]` only when body is non-array.
- [x] 1.4 RED [web-customer] In `addresses.test.ts` rewrite `createAddress` test: call with `{ label: 'Дом', address_text: 'x', lat: 1, lon: 2, apartment: '5', entrance: null, floor: null, comment: null }`, assert POST body parsed JSON has key `address_text` (not `text`) and key `label`. Fails against current types/impl.
- [x] 1.5 RED [web-customer] In `addresses.test.ts` replace the `setPrimaryAddress` describe block with a `setDefaultAddress` describe block: call `setDefaultAddress('a1')`, assert URL is `/api/v1/profile/addresses/a1`, method is `PATCH`, body is `{"is_default": true}`. Fails today (function does not exist; old one POSTs to `/set-primary`).

## 2. API client implementation (GREEN)

- [x] 2.1 GREEN [web-customer] In `web/customer/src/api/addresses.ts` update `AddressResponse` interface: remove `text`, add `address_text: string`; remove `is_primary`, add `is_default: boolean`. Satisfies 1.1.
- [x] 2.2 GREEN [web-customer] In `addresses.ts` update `AddressCreatePayload`: remove `text`, add `address_text: string`; make `label: string` required (not optional, not nullable). `AddressUpdatePayload` → `Partial<AddressCreatePayload> & { is_default?: boolean }`. Satisfies 1.4.
- [x] 2.3 GREEN [web-customer] In `addresses.ts` rewrite `listAddresses`: parse `res.json()` as `unknown`, cast via `Array.isArray(data) ? (data as AddressResponse[]) : []`. Satisfies 1.2 and 1.3.
- [x] 2.4 GREEN [web-customer] In `addresses.ts` replace `setPrimaryAddress` export with `setDefaultAddress(id: string)` that calls `PATCH /api/v1/profile/addresses/{id}` body `{ is_default: true }` via the same error-handling path (`parseError`). Remove the old function entirely. Satisfies 1.5.
- [x] 2.5 VERIFY [web-customer] Run `cd web/customer && npm run test -- addresses.test.ts` — all assertions in group 1 pass. If any fail, stop and diagnose.

## 3. AddressForm tests (RED)

- [x] 3.1 RED [web-customer] In `web/customer/src/pages/Profile/Addresses/AddressForm.test.tsx` update the `createAddress` mock resolve value: replace `text: '...'` with `address_text: '...'`, replace `is_primary: false` with `is_default: false`. Test file fails to compile until type changes land.
- [x] 3.2 RED [web-customer] In `AddressForm.test.tsx` rewrite the "calls createAddress with form data" test: also type `label: 'Дом'` into the label input (inputs[0]); assert submitted payload has `address_text: 'Ул. Ленина 1'`, `label: 'Дом'`, `apartment: '42'`, and does NOT have the key `text`. Fails against current form that sends `text`.
- [x] 3.3 RED [web-customer] In `AddressForm.test.tsx` add a new test "Save button disabled without label": render form, type only into the address input (inputs[1]), assert the Save button is disabled. Fails because current form only checks `address.text.trim()`.

## 4. AddressForm implementation (IMPL)

- [x] 4.1 IMPL [web-customer] In `web/customer/src/pages/Profile/Addresses/AddressForm.tsx` update the `payload` builder in `handleSubmit`: send `{ label: label.trim(), address_text: address.text, lat, lon, apartment: apartment.trim() || null, entrance: ..., floor: ..., comment: ... }`. For edit-mode PATCH the same payload shape is acceptable (backend accepts partials).
- [x] 4.2 IMPL [web-customer] In `AddressForm.tsx` update Save button disabled-check: `disabled={submitting || !address.text.trim() || !label.trim()}`. Satisfies 3.3.
- [x] 4.3 IMPL [web-customer] In `AddressForm.tsx` update initial label fallback on edit: `initial?.label ?? ''` stays (already correct), but since label is now required, no further change needed — verify the edit flow pre-fills from `initial.label`.
- [x] 4.4 VERIFY [web-customer] Run `cd web/customer && npm run test -- AddressForm.test.tsx` — tests 3.1–3.3 pass.

## 5. AddressesPage update (IMPL)

- [x] 5.1 IMPL [web-customer] In `web/customer/src/pages/Profile/Addresses/AddressesPage.tsx` replace import of `setPrimaryAddress` with `setDefaultAddress`; rename the handler `handleSetPrimary` callsite to call `setDefaultAddress(id)` (keep handler name `handleSetPrimary` for UX consistency, or rename — designer's call).
- [x] 5.2 IMPL [web-customer] In `AddressesPage.tsx` replace all three `a.is_primary` reads with `a.is_default`: line 102 (`{a.is_primary && (…primary badge…)}`), line 109 (`{!a.is_primary && (…Make Primary button…)}`). Also replace `a.text` with `a.address_text` on line 92 (rendered address text).
- [x] 5.3 VERIFY [web-customer] Grep the file: `grep -n "is_primary\|\\.text\b" web/customer/src/pages/Profile/Addresses/AddressesPage.tsx` MUST return no matches for `is_primary`; `.text` reference on the AddressResponse object SHALL be gone (references on other values like `e.target.value` are fine).

## 6. CheckoutPage update (IMPL)

- [x] 6.1 IMPL [web-customer] In `web/customer/src/pages/CheckoutPage.tsx` replace both `items.find((a) => a.is_primary)` (line ~62) and `saved.find((a) => a.is_primary)` (line ~188) with `…find((a) => a.is_default)`. If CheckoutPage reads `a.text` anywhere in the saved-address branch, replace with `a.address_text`. Also fix save-for-future createAddress call to new `{label, address_text, ...}` shape.
- [x] 6.2 IMPL [web-customer] In `web/customer/src/pages/CheckoutPage.test.tsx` update fixtures on lines 82 and 94: rename `is_primary` → `is_default` and `text` → `address_text`. Any assertion that references `is_primary` or `.text` on a saved address SHALL be updated accordingly.
- [x] 6.3 VERIFY [web-customer] Run `cd web/customer && npm run test -- CheckoutPage.test.tsx` — all tests pass.

## 7. Full-repo sync + gates

- [x] 7.1 VERIFY [web-customer] `grep -rn "is_primary" web/customer/src` returns zero matches.
- [x] 7.2 VERIFY [web-customer] `./node_modules/.bin/tsc -b --noEmit` in `web/customer/`: only 3 pre-existing unrelated errors remain (unused imports in `App.test.tsx` and `VerifyPage.test.tsx` — both outside the change scope). No new errors introduced by the fix.
- [x] 7.3 VERIFY [web-customer] `./node_modules/.bin/vitest run` in `web/customer/`: 26 files, 149 tests — all pass.
- [ ] 7.4 VERIFY [web-customer] (Optional manual — document only, not required for CI) Run Phase 4 manual scenario 1.3 (add address happy path) and 1.6 (make primary) in a browser against a stack with real `YANDEX_MAPS_API_KEY`. Append result (✓/✗ + screenshot path) to this file under "Manual QA results".
