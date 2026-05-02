import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import '@testing-library/jest-dom/vitest';
import i18n from '@/i18n/config';

vi.mock('@/api/loyalty', async () => {
  const actual =
    await vi.importActual<typeof import('@/api/loyalty')>('@/api/loyalty');
  return {
    ...actual,
    getLoyaltyBalance: vi.fn(),
  };
});

import { getLoyaltyBalance } from '@/api/loyalty';
import { LoyaltyCard } from './LoyaltyCard';

beforeEach(async () => {
  vi.clearAllMocks();
  await i18n.changeLanguage('en');
});

describe('LoyaltyCard', () => {
  it('renders balance once loaded', async () => {
    (getLoyaltyBalance as Mock).mockResolvedValue({
      balance: 240,
      lifetime_accrued: 1200,
    });

    render(
      <MemoryRouter>
        <LoyaltyCard />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText('240')).toBeInTheDocument();
    });
  });

  it('renders link to /profile/loyalty', async () => {
    (getLoyaltyBalance as Mock).mockResolvedValue({
      balance: 0,
      lifetime_accrued: 0,
    });

    render(
      <MemoryRouter>
        <LoyaltyCard />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText('0')).toBeInTheDocument();
    });

    const link = screen.getByRole('link');
    expect(link).toHaveAttribute('href', '/profile/loyalty');
  });
});
