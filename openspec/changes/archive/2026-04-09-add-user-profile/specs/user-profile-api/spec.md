## ADDED Requirements

### Requirement: Get customer profile
The system SHALL provide `GET /api/v1/profile` endpoint that returns the authenticated customer's profile data. The endpoint SHALL require a valid JWT access token with `role: "customer"` (INV-002, INV-010). The response SHALL include `user_id`, `phone_masked`, `display_name`, and `preferred_language`.

#### Scenario: Authenticated customer views profile
- **WHEN** authenticated customer sends `GET /api/v1/profile` with valid JWT
- **THEN** system returns HTTP 200 with JSON body: `{user_id, phone_masked, display_name, preferred_language}`

#### Scenario: Phone is returned masked
- **WHEN** profile is retrieved for a user with phone `+79161234567`
- **THEN** `phone_masked` field contains `+7 *** *** 45 67` (last 4 digits visible)

#### Scenario: Unauthenticated request
- **WHEN** request to `GET /api/v1/profile` has no JWT or an expired/invalid JWT
- **THEN** system returns HTTP 401

#### Scenario: Non-customer role
- **WHEN** request to `GET /api/v1/profile` has a valid JWT with role other than `customer`
- **THEN** system returns HTTP 403

### Requirement: Update customer profile
The system SHALL provide `PATCH /api/v1/profile` endpoint that updates the authenticated customer's profile. Accepted fields: `display_name` (string, 1–100 chars) and `preferred_language` (enum: `ru`, `en`). The endpoint SHALL require a valid JWT with `role: "customer"` (INV-002, INV-010). The response SHALL return the full updated profile (same shape as GET).

#### Scenario: Update display name
- **WHEN** authenticated customer sends `PATCH /api/v1/profile` with `{display_name: "Михаил"}`
- **THEN** system updates `user_profiles.display_name` and returns HTTP 200 with full updated profile

#### Scenario: Update preferred language
- **WHEN** authenticated customer sends `PATCH /api/v1/profile` with `{preferred_language: "en"}`
- **THEN** system updates `user_profiles.preferred_language` and returns HTTP 200 with full updated profile

#### Scenario: Partial update — only provided fields change
- **WHEN** authenticated customer sends `PATCH /api/v1/profile` with only `display_name`
- **THEN** `preferred_language` remains unchanged

#### Scenario: Empty body
- **WHEN** authenticated customer sends `PATCH /api/v1/profile` with empty body `{}`
- **THEN** system returns HTTP 200 with current profile unchanged (no-op)

#### Scenario: Invalid display name — too long
- **WHEN** authenticated customer sends `PATCH /api/v1/profile` with `display_name` exceeding 100 characters
- **THEN** system returns HTTP 422 with validation error

#### Scenario: Invalid preferred language
- **WHEN** authenticated customer sends `PATCH /api/v1/profile` with `preferred_language: "fr"`
- **THEN** system returns HTTP 422 with validation error

### Requirement: Profile service with PII isolation
The system SHALL implement a profile service that reads from `user_profiles` table (PII-isolated per INV-013). Phone decryption SHALL use `ENCRYPTION_KEY` from environment (INV-015). The service SHALL mask phone numbers, exposing only the last 4 digits.

#### Scenario: Phone decrypted and masked
- **WHEN** profile service retrieves profile for a user
- **THEN** it decrypts `user_profiles.phone` using AES-256-GCM with `ENCRYPTION_KEY` and returns masked format `+X *** *** XX XX`

#### Scenario: Profile not found for user
- **WHEN** profile service is called with a `user_id` that has no `user_profiles` row
- **THEN** it raises a not-found error (HTTP 404)
