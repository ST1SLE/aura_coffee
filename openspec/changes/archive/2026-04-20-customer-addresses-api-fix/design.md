## Context

Affected modules: **[web-customer]** only.

The Customer SPA module `web/customer/src/api/addresses.ts` has three wire-format drifts against the live core-api contract that are reproducible in Phase 4 manual QA (docs/phase4_manual_test_scenarios.md §6, validated by the working §5.2 curl recipes). The drifts were introduced when the backend schemas (`DeliveryAddressCreate`, `DeliveryAddressRead`, and the default-flag PATCH handler) were finalized after the SPA client was first written. Section 1 of the phase 4 scenarios — the UI-driven create / list / make-primary flow — is broken even though the corresponding §5 curl flow passes.

Current drifts:
1. **Request payload.** Client POSTs `{ text, lat, lon, apartment, …, label? }`. Server requires `{ label: str (min_length=1), address_text: str, lat, lon, apartment, … }`. Server responds `422 Field required` (`address_text`).
2. **List response envelope.** Server returns `JSON array`. Client parses `(res.json() as { items?: AddressResponse[] }).items ?? []` and always gets `[]`.
3. **Set-primary route.** Client POSTs `/api/v1/profile/addresses/{id}/set-primary` (no such route — 404/405). Correct call is `PATCH /api/v1/profile/addresses/{id}` body `{ "is_default": true }`.
4. **Response field name.** `DeliveryAddressRead` returns `is_default: bool`. Client types and consumers (`AddressesPage`, `CheckoutPage`) read `is_primary` — always `undefined`, so the primary badge never shows and the primary-address auto-select on checkout falls through to `items[0]` regardless of backend truth.

The backend contract is correct against PDD §5.2 and 152-FZ isolation (addresses live under `/profile/`, not in the anonymous cart). This change is purely frontend synchronization.

## Goals / Non-Goals

**Goals:**
- Customer SPA `addresses.ts` MUST wire-match the backend contract verified by `docs/phase4_manual_test_scenarios.md §5.2`.
- Phase 4 manual scenarios 1.3 (happy-path create), 1.5 (edit), 1.6 (make-primary), and the checkout auto-select primary flow MUST work end-to-end from the UI.
- All existing unit tests MUST be updated to assert the new shapes — no green-washing by deleting tests.
- Consumers that read `is_primary` (`AddressesPage`, `CheckoutPage`, test fixtures) MUST be updated atomically in the same change.

**Non-Goals:**
- No backend changes. `services/core-api/**/*.py` is out of scope.
- No new UI features or copy changes (i18n keys stay identical).
- No introduction of `zod` runtime validation in `addresses.ts` beyond parsing the bare-array list (the proposal's "z.array" hint is descriptive, not prescriptive — the codebase uses TS casts elsewhere in `api/menu.ts`, so we SHALL stay consistent with a plain cast).
- No refactor of `AddressApiError` or the 409-radius UX.
- No change to `AddressAutocomplete` or the Yandex maps proxy.

## Decisions

### D1 — Rename request field `text` → `address_text` at the API layer, not inside `AddressForm`

**Decision:** `AddressCreatePayload` exposes `address_text: string` (not `text`). `AddressForm.tsx` builds the payload with `address_text: address.text` (mapping from the local `AddressValue` state whose field stays `text`). The `AddressValue` type from `AddressAutocomplete` stays unchanged (`{ text, lat, lon }`) — renaming it would cascade into autocomplete, Yandex maps typing, and unrelated components.

**Alternatives:**
- Rename `AddressValue.text` → `AddressValue.address_text`: too invasive, touches geocoding code paths outside the bug zone.
- Keep `text` on the payload and transform in a wrapper: obscures the wire format — violates "Non-Goals #5" by introducing a new abstraction just to hide the fix.

**Rationale:** the bug is at the HTTP boundary, so fix it at the HTTP boundary. The local UI value object is fine.

### D2 — `label` becomes required on `AddressCreatePayload`, enforced in `AddressForm` before submit

**Decision:** `AddressCreatePayload.label: string` (non-optional, non-nullable). `AddressForm.tsx` disables the Submit button unless `label.trim().length > 0 && address.text.trim().length > 0` (currently only `address.text.trim()` is checked). `AddressUpdatePayload` stays `Partial<…>` so PATCH without a label is still allowed — matching backend behavior (`DeliveryAddressUpdate` has all optional fields).

**Alternatives:**
- Auto-derive `label` from the suggestion text when empty: hides the required-field contract from the user and would diverge from the "label min_length=1" server invariant the first time someone edits the label to an empty string. Rejected.
- Leave `label` optional on the TS type and rely on the server 422: pushes the validation error into the user's lap for a field that's already on the form. Rejected — we can catch it locally.

**Rationale:** label is already a user-visible, editable field — making it required has zero UX cost and eliminates the most common path to 422.

### D3 — `listAddresses` parses a bare array; no `{ items }` envelope

**Decision:**
```ts
const data = (await res.json()) as AddressResponse[];
return Array.isArray(data) ? data : [];
```

The `Array.isArray` guard is defensive — if the server ever reverts to an envelope, we fail soft to empty rather than throw a TypeError on `.map`. We SHALL NOT import zod for this single call; it would be inconsistent with `api/menu.ts` which uses the same TS-cast pattern.

**Alternatives:**
- Full zod schema + parse: over-engineered for one endpoint; the proposal's "z.array(AddressSchema).parse(res) (or equivalent)" explicitly permits the equivalent pattern from `api/menu.ts`.

### D4 — `setPrimaryAddress(id)` is implemented as `updateAddress(id, { is_default: true })`; the old function is removed

**Decision:** Rename the exported function `setPrimaryAddress` → `setDefaultAddress` and re-implement it as a thin wrapper over `PATCH /api/v1/profile/addresses/{id}` with body `{ is_default: true }`. All three callers (`AddressesPage.tsx:7`, `AddressesPage.tsx:53`) update their import.

**Alternatives:**
- Keep the name `setPrimaryAddress` and just change the URL/method: preserves API stability but perpetuates the `primary` / `default` lexical drift across the SPA. Rejected — we're already touching every caller for the `is_primary` → `is_default` field rename (D5), so renaming the function is free.

**Rationale:** aligns SPA vocabulary with backend (`is_default`) and avoids two names for one thing.

### D5 — `AddressResponse.is_primary` → `is_default`; call-site updates are atomic

**Decision:** Rename in `AddressResponse`, then update the three remaining consumers:
- `web/customer/src/pages/Profile/Addresses/AddressesPage.tsx` — three reads (`a.is_primary` badge, `!a.is_primary` for Make Primary button, plus any fixture in tests).
- `web/customer/src/pages/CheckoutPage.tsx:62` and `:188` — `items.find((a) => a.is_primary)` in two places.
- `web/customer/src/pages/CheckoutPage.test.tsx:82,94` — fixtures.
- `web/customer/src/api/addresses.test.ts` — fixture factory `addr()` default + `setPrimaryAddress` test body.
- `web/customer/src/pages/Profile/Addresses/AddressForm.test.tsx` — response fixture at line 45.

`grep -rn "is_primary" web/customer/src` is the authoritative change-list; the change SHALL leave zero matches in `web/customer/src/**/*.{ts,tsx}` after apply.

**Alternatives:**
- Keep `is_primary` as an alias and populate it from `is_default` in the API layer: creates dual-naming (backward-compat shim) for no reason — the user prefers "no backwards-compat shims" per CLAUDE.md. Rejected.

### D6 — No backend reach; verify only via unit tests + manual QA

**Decision:** No new integration test is added that spins up core-api. Verification path:
1. Unit tests (`addresses.test.ts`, `AddressForm.test.tsx`, `CheckoutPage.test.tsx`) pinning the new wire shapes.
2. `npm run -w customer typecheck` MUST pass (confirms all `is_primary` references are updated — the TS compiler is the brute-force linter here).
3. Manual run of Section 1.3 and 1.6 after apply (documented in tasks).

**Rationale:** the backend contract is already exercised by `services/core-api` tests; the drift is in the SPA, so the SPA test layer is the right gate.

## Risks / Trade-offs

- **[Risk] Missed `is_primary` call-site.** If a consumer outside the enumerated files still reads `.is_primary`, TypeScript catches it at compile time (field no longer exists). **Mitigation:** run `npm run -w customer typecheck` as a tasks.md gate.
- **[Risk] `label` becomes required — user on an existing saved address with a null/empty label.** Server stores `label` as `NOT NULL` with min_length=1 (per `DeliveryAddressCreate`), so no existing row can have an empty label; the Edit form therefore always has something to pre-fill. **Mitigation:** `AddressForm` uses `initial?.label ?? ''` and disables Save if empty — same UX as create.
- **[Risk] Bare-array parse breaks if server temporarily regresses to an envelope** (extremely unlikely, but docs used to describe one). **Mitigation:** `Array.isArray` guard returns `[]` on non-array body, which surfaces as empty state — exactly the current failure mode, not worse.
- **[Trade-off] Function rename `setPrimaryAddress` → `setDefaultAddress`.** Any outstanding PR touching the old name will get a merge conflict. **Mitigation:** the only caller is `AddressesPage.tsx` in this repo; grep confirms.
- **[Risk] CheckoutPage delivery flow regression.** `CheckoutPage.tsx` is the customer-facing happy path for delivery orders. **Mitigation:** update `CheckoutPage.test.tsx` fixtures in the same commit and keep the semantics ("pick primary on mount") identical — only the field name changes.

## Migration Plan

- Forward-only: this is a code-only fix (no DB, no env vars).
- Rollback: `git revert` the merge commit — the backend accepts both states (it was never the one changing), so there is no data-shape migration to undo.
- No feature flag — the fix either matches the backend or it doesn't; running both variants simultaneously would defeat the purpose.

## 152-FZ Compliance

Not impacted. Addresses remain under `/api/v1/profile/addresses` (authenticated, user-scoped), no new PII fields are introduced, no new logging surfaces touch the payload (PII-scrub patterns in `core-api` continue to apply server-side).

## Open Questions

None — the contract is already documented in `docs/phase4_manual_test_scenarios.md §5.2` with working curl recipes, and the Section 6 "Known gaps" block names exactly these three bugs.
