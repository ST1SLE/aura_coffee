## Why

Phase 1 (§7.1) requires a customer profile / "личный кабинет" — view and edit profile data, change language preference. Auth (OTP, JWT) and user models are already specified; the profile endpoints and UI screens are the missing piece to complete Phase 1 user-facing functionality.

## What Changes

- **New API endpoints** for customer profile: `GET /api/v1/profile` (view own profile), `PATCH /api/v1/profile` (update display_name, preferred_language).
- **Profile screen in web-customer** — displays phone (masked), display name, language switcher; allows editing name and language.
- **Phone display** — decrypted phone shown masked (e.g., +7 *** *** 45 67) in profile; no phone change flow in this change.
- **Backend service layer** — profile service reading/writing `user_profiles` table, respecting PII isolation (INV-013).

## Non-Goals

- **No avatar/bio/email fields.** The PDD `user_profiles` schema has no such columns; adding them is a separate change requiring PDD amendment.
- **No phone number change flow.** Changing phone requires re-verification via OTP — complex enough for a dedicated change.
- **No delivery address management.** Saved addresses are scoped to a separate change (delivery feature, Phase 4).
- **No account deletion.** PDD §6.5 defines the flow, but it's out of scope here.

## MVP Phase

Phase 1: Auth & User Profile (§7.1, item 3).

## Capabilities

### New Capabilities
- `user-profile-api`: Backend endpoints for viewing and updating customer profile (GET/PATCH /api/v1/profile).
- `user-profile-screen`: Customer-facing profile screen in web-customer SPA — view profile, edit name, switch language.

### Modified Capabilities
_None — no existing spec requirements change._

## Impact

- **core-api**: New router module `profile`, new service, Pydantic schemas for profile request/response.
- **web-customer**: New profile page/route, API client calls (auto-generated from OpenAPI spec).
- **packages/shared**: May need shared response schemas if not already present.
- **No database migrations** — `user_profiles` table already exists per user-models spec.
- **No new external dependencies.**
