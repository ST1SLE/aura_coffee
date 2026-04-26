import { authenticatedFetch } from './client';

// START_MODULE_CONTRACT
//   PURPOSE: Profile REST client — GET/PATCH /api/v1/profile for display name
//            and preferred language. Phone number is masked server-side
//            (phone_masked) to satisfy INV-013 (no raw phone in UI surfaces).
//   SCOPE:   ProfileData, ProfileUpdateData DTOs, getProfile, updateProfile.
//   DEPENDS: M-CORE-API (HTTP /api/v1/profile), ./client (authenticatedFetch).
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §8 profile;
//            INV-013 (phone_masked is server-rendered).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   ProfileData          - GET /profile response (user_id, phone_masked, name, lang)
//   ProfileUpdateData    - partial PATCH body (display_name, preferred_language)
//   getProfile           - GET /profile
//   updateProfile        - PATCH /profile with partial fields
// END_MODULE_MAP

const API_BASE = '/api/v1/profile';

export interface ProfileData {
  user_id: string;
  phone_masked: string;
  display_name: string | null;
  preferred_language: string;
}

export interface ProfileUpdateData {
  display_name?: string;
  preferred_language?: 'ru' | 'en';
}

// START_CONTRACT: getProfile
//   PURPOSE: Fetch the current user's profile.
//   INPUTS:  none.
//   OUTPUTS: Promise<ProfileData> — { user_id, phone_masked, display_name,
//            preferred_language }.
//   SIDE_EFFECTS: HTTP GET /api/v1/profile (authenticated). Throws plain Error
//                 with status code on non-2xx.
//   LINKS:   PDD §8 profile; ProfilePage uses this on mount.
// END_CONTRACT: getProfile
export async function getProfile(): Promise<ProfileData> {
  const res = await authenticatedFetch(API_BASE);
  if (!res.ok) {
    throw new Error(`Failed to fetch profile: ${res.status}`);
  }
  return res.json();
}

// START_CONTRACT: updateProfile
//   PURPOSE: Patch display name and/or preferred language on the user's profile.
//   INPUTS:  data: ProfileUpdateData — partial { display_name, preferred_language }.
//   OUTPUTS: Promise<ProfileData> — updated profile.
//   SIDE_EFFECTS: HTTP PATCH /api/v1/profile; throws plain Error on non-2xx.
//                 INV-013 — display_name is PII; UI must not log raw value.
//   LINKS:   PDD §8 profile; ProfilePage saves name and language toggle.
// END_CONTRACT: updateProfile
export async function updateProfile(
  data: ProfileUpdateData,
): Promise<ProfileData> {
  const res = await authenticatedFetch(API_BASE, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    throw new Error(`Failed to update profile: ${res.status}`);
  }
  return res.json();
}
