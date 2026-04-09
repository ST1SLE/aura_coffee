## Context

Auth (OTP + JWT) and user models (`users`, `user_profiles`) are implemented. Phase 1 item 3 requires a customer profile screen: view profile, edit display name, switch language. The `user_profiles` table already stores `display_name` and `preferred_language` alongside encrypted `phone`.

**Affected modules:** [core-api], [web-customer], [shared]

## Goals / Non-Goals

**Goals:**
- Provide authenticated customers a way to view and edit their profile data.
- Expose profile API endpoints following existing auth patterns (JWT bearer, role check).
- Deliver a responsive profile screen in web-customer.

**Non-Goals:**
- Phone number change (requires OTP re-verification).
- Delivery address management (Phase 4).
- Account deletion flow.
- Avatar or additional PII fields beyond PDD schema.

## 152-FZ Compliance

Profile endpoints read/write `user_profiles` (PII-isolated table per INV-013). Phone is returned masked to the client — the API SHALL never expose plaintext phone in responses. Decryption occurs server-side only to produce a masked representation.

## Decisions

### 1. Profile router follows existing auth router pattern

**Decision:** Add `routers/profile.py` with a `profile_router` mounted at `/api/v1/profile`, following the same structure as `routers/auth.py`.

**Why:** Consistent code organization. The auth dependency (`deps/auth.py`) already extracts `current_user` from JWT — profile endpoints reuse this.

**Alternatives considered:**
- Embedding profile endpoints in the auth router — rejected because profile is a distinct domain concern.

### 2. Phone masking at the service layer

**Decision:** `services/profile.py` SHALL decrypt phone and return a masked string (e.g., `+7 *** *** 45 67`). The Pydantic response schema carries `phone_masked: str`, never raw phone.

**Why:** INV-013 / 152-FZ — minimize PII exposure. Masking at the service layer ensures no router or serializer accidentally leaks plaintext.

**Alternatives considered:**
- Masking in the frontend — rejected because it would require sending plaintext phone over the wire.
- Not showing phone at all — rejected because customers need to verify which number is associated with their account.

### 3. PATCH semantics for profile update

**Decision:** `PATCH /api/v1/profile` accepts a partial body with optional `display_name` and `preferred_language`. Only provided fields are updated.

**Why:** Standard REST PATCH semantics. Avoids requiring the client to send all fields.

### 4. Frontend profile page as a protected route

**Decision:** Add `/profile` route in web-customer behind auth guard. The page uses the auto-generated API client to fetch and update profile data. Language change triggers `i18next.changeLanguage()` alongside the API call.

**Why:** Consistent with existing frontend routing and auth state patterns. Language change MUST persist server-side (for SMS language) and client-side (for UI).

## Risks / Trade-offs

- **[Risk] Encryption key unavailable** → Profile GET fails if `ENCRYPTION_KEY` env var is missing. Mitigation: settings validation at startup (already enforced by `settings.py`).
- **[Risk] Stale language on frontend after update** → If preferred_language update succeeds on server but i18next fails to switch. Mitigation: sequence the operations — update server first, then switch i18next on success response.
- **[Trade-off] No optimistic UI updates** → Profile update waits for server response before reflecting changes. Acceptable for MVP; profile edits are infrequent.

## Open Questions

_None — scope is well-defined by PDD §7.1 Phase 1 item 3._
