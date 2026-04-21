## Why

Three confirmed schema-drift bugs between Customer SPA (`web/customer/src/api/addresses.ts`) and core-api break the phase 4 delivery happy-path: create-address returns 422, list-addresses parses an empty list, and set-primary 404s on a non-existent route. Documented in `docs/phase4_manual_test_scenarios.md §6` (Customer SPA ↔ core-api schema drift) and validated against §5.2 (Delivery addresses CRUD). Without this fix the Phase 4 delivery feature is unusable from the UI even though the backend is correct.

MVP Phase: **Phase 4 — Delivery** (PDD §7.1).

## What Changes

- **BREAKING (frontend-only):** `createAddress` payload: rename request field `text` → `address_text`; add required `label` (min_length=1) — value sourced from the already-editable label input in `AddressForm.tsx`.
- **BREAKING (frontend-only):** `listAddresses` — parse the bare JSON array returned by the server; remove the `{ items: [...] }` envelope assumption.
- **BREAKING (frontend-only):** `setPrimaryAddress` — replace `POST /api/v1/profile/addresses/{id}/set-primary` with `PATCH /api/v1/profile/addresses/{id}` body `{ "is_default": true }`.
- **BREAKING (frontend-only):** `AddressResponse.is_primary` → `is_default` (backend source of truth); update all readers in `CheckoutPage.tsx` (lines ~62, ~188) and `AddressesPage`/`AddressForm` paths; tests updated accordingly.
- Backend schema (`DeliveryAddressCreate` / `DeliveryAddressRead` / PATCH handler) stays unchanged — this is client-only synchronization.

## Capabilities

### New Capabilities
- (none — this is a bugfix against existing capabilities)

### Modified Capabilities
- `customer-addresses-api-client`: `createAddress` request shape (`address_text` + required `label`), `listAddresses` response parsing (bare array), `setPrimaryAddress` replaced by `setDefaultAddress` via `PATCH … { is_default: true }`, `AddressResponse.is_primary` → `is_default`.
- `customer-addresses-ui`: AddressForm SHALL require `label` before submit; list-rendering SHALL read `is_default`; "Сделать основным" action SHALL call the PATCH-based default API.
- `customer-checkout-delivery-ui`: Saved-address selector SHALL read `is_default` (not `is_primary`) when choosing the initial default address on mount.

## Impact

Affected code:
- `web/customer/src/api/addresses.ts` (core of the fix)
- `web/customer/src/api/addresses.test.ts`
- `web/customer/src/pages/Profile/Addresses/AddressForm.tsx`
- `web/customer/src/pages/Profile/Addresses/AddressForm.test.tsx`
- `web/customer/src/pages/Profile/Addresses/AddressesPage.tsx` (reads `is_primary`)
- `web/customer/src/pages/CheckoutPage.tsx` (reads `.is_primary` in two spots)
- `web/customer/src/pages/CheckoutPage.test.tsx` (fixture uses `is_primary`)

Non-goals (Non-Goals — required):
1. **No backend schema changes.** `DeliveryAddressCreate` / `DeliveryAddressRead` / `PATCH` handlers stay as-is; if the backend contract drifts again, a separate change will align it.
2. **No new UI features.** Behavior of Addresses page, AddressForm, and CheckoutPage delivery selector must be preserved — only the wire format changes.
3. **No change to error contract.** `AddressApiError(status, detail)` and the 409-radius flow are untouched.
4. **No change to map/autocomplete logic.** `AddressAutocomplete`, Yandex proxy, and geocode cache are out of scope.
5. **No refactor of the API client layer.** We will not switch `addresses.ts` to zod / schema validation beyond what the list-parsing fix minimally requires (bare-array parse).

Systems: browser only. No migrations, no env vars, no Celery tasks, no backend routes.

Invariants touched: none (INV-002 auth still enforced server-side; INV-013 PII isolation unchanged — addresses already lived in the profile namespace).
