import { authenticatedFetch } from './client';

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

export async function getProfile(): Promise<ProfileData> {
  const res = await authenticatedFetch(API_BASE);
  if (!res.ok) {
    throw new Error(`Failed to fetch profile: ${res.status}`);
  }
  return res.json();
}

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
