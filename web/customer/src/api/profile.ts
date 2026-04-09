import { getAccessToken } from '@/auth/token';

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

async function authHeaders(): Promise<Record<string, string>> {
  const token = getAccessToken();
  if (!token) throw new Error('Not authenticated');
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  };
}

export async function getProfile(): Promise<ProfileData> {
  const res = await fetch(API_BASE, {
    headers: await authHeaders(),
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch profile: ${res.status}`);
  }
  return res.json();
}

export async function updateProfile(
  data: ProfileUpdateData,
): Promise<ProfileData> {
  const res = await fetch(API_BASE, {
    method: 'PATCH',
    headers: await authHeaders(),
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    throw new Error(`Failed to update profile: ${res.status}`);
  }
  return res.json();
}
