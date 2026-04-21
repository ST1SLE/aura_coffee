import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import '@testing-library/jest-dom/vitest';
import i18n from '@/i18n/config';

vi.mock('@/api/profile', async () => {
  const actual =
    await vi.importActual<typeof import('@/api/profile')>('@/api/profile');
  return {
    ...actual,
    getProfile: vi.fn(),
    updateProfile: vi.fn(),
  };
});

vi.mock('@/api/loyalty', async () => {
  const actual =
    await vi.importActual<typeof import('@/api/loyalty')>('@/api/loyalty');
  return {
    ...actual,
    getLoyaltyBalance: vi.fn(),
  };
});

vi.mock('@/auth/useAuth', () => ({
  useAuth: () => ({
    user: { id: 'u1', role: 'customer' },
    isAuthenticated: true,
    isLoading: false,
    login: vi.fn(),
    verifyCode: vi.fn(),
    logout: vi.fn(),
  }),
}));

import { getProfile } from '@/api/profile';
import { getLoyaltyBalance } from '@/api/loyalty';
import { ProfilePage } from './ProfilePage';

beforeEach(async () => {
  vi.clearAllMocks();
  await i18n.changeLanguage('en');
  (getLoyaltyBalance as Mock).mockResolvedValue({
    balance: 0,
    lifetime_accrued: 0,
  });
});

describe('ProfilePage', () => {
  it('renders link to /profile/addresses', async () => {
    (getProfile as Mock).mockResolvedValue({
      user_id: 'u1',
      phone_masked: '+7999***4567',
      display_name: 'Qa',
      preferred_language: 'en',
    });

    render(
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>,
    );

    const link = await waitFor(() =>
      screen.getByRole('link', { name: /addresses/i }),
    );
    expect(link).toHaveAttribute('href', '/profile/addresses');
  });
});
