import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import '@testing-library/jest-dom/vitest';
import i18n from '@/i18n/config';

vi.mock('@/api/loyalty', async () => {
  const actual =
    await vi.importActual<typeof import('@/api/loyalty')>('@/api/loyalty');
  return {
    ...actual,
    getLoyaltyBalance: vi.fn(),
    listLoyaltyTransactions: vi.fn(),
  };
});

import {
  getLoyaltyBalance,
  listLoyaltyTransactions,
  type LoyaltyTransaction,
} from '@/api/loyalty';
import { LoyaltyPage } from './LoyaltyPage';

const tx = (over: Partial<LoyaltyTransaction> = {}): LoyaltyTransaction => ({
  id: crypto.randomUUID(),
  order_id: null,
  type: 'accrual',
  amount: 10,
  balance_after: 100,
  description: null,
  created_at: '2026-04-20T12:00:00Z',
  ...over,
});

function renderPage() {
  return render(
    <MemoryRouter>
      <LoyaltyPage />
    </MemoryRouter>,
  );
}

beforeEach(async () => {
  vi.clearAllMocks();
  await i18n.changeLanguage('en');
});

describe('LoyaltyPage balance header', () => {
  it('renders balance and lifetime_accrued', async () => {
    (getLoyaltyBalance as Mock).mockResolvedValue({
      balance: 240,
      lifetime_accrued: 1200,
    });
    (listLoyaltyTransactions as Mock).mockResolvedValue({
      items: [],
      page: 1,
      per_page: 20,
      total: 0,
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText('240')).toBeInTheDocument();
    });
    expect(screen.getByText(/1200/)).toBeInTheDocument();
  });
});

describe('LoyaltyPage empty state', () => {
  it('shows empty copy when no transactions', async () => {
    (getLoyaltyBalance as Mock).mockResolvedValue({
      balance: 0,
      lifetime_accrued: 0,
    });
    (listLoyaltyTransactions as Mock).mockResolvedValue({
      items: [],
      page: 1,
      per_page: 20,
      total: 0,
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/No transactions yet/i)).toBeInTheDocument();
    });
  });
});

describe('LoyaltyPage order link', () => {
  it('row renders link to /orders/{order_id} with short id', async () => {
    const orderId = 'abcdef12-3456-7890-abcd-ef1234567890';
    (getLoyaltyBalance as Mock).mockResolvedValue({
      balance: 50,
      lifetime_accrued: 50,
    });
    (listLoyaltyTransactions as Mock).mockResolvedValue({
      items: [tx({ order_id: orderId, amount: 50 })],
      page: 1,
      per_page: 20,
      total: 1,
    });

    renderPage();

    await waitFor(() => {
      const link = screen.getByRole('link');
      expect(link).toHaveAttribute('href', `/orders/${orderId}`);
      expect(link.textContent).toContain('abcdef12');
    });
  });
});

describe('LoyaltyPage pagination', () => {
  it('loads next page when "load more" clicked and previous page was full', async () => {
    const fullPage = Array.from({ length: 20 }, () => tx());
    (getLoyaltyBalance as Mock).mockResolvedValue({
      balance: 240,
      lifetime_accrued: 1200,
    });
    (listLoyaltyTransactions as Mock)
      .mockResolvedValueOnce({
        items: fullPage,
        page: 1,
        per_page: 20,
        total: 30,
      })
      .mockResolvedValueOnce({
        items: [tx(), tx()],
        page: 2,
        per_page: 20,
        total: 30,
      });

    renderPage();

    const loadMore = await screen.findByRole('button', { name: /load more/i });
    fireEvent.click(loadMore);

    await waitFor(() => {
      expect(listLoyaltyTransactions).toHaveBeenCalledTimes(2);
      expect(listLoyaltyTransactions).toHaveBeenLastCalledWith(2, 20);
    });
  });

  it('does not show "load more" when first page is not full', async () => {
    (getLoyaltyBalance as Mock).mockResolvedValue({
      balance: 10,
      lifetime_accrued: 10,
    });
    (listLoyaltyTransactions as Mock).mockResolvedValue({
      items: [tx()],
      page: 1,
      per_page: 20,
      total: 1,
    });

    renderPage();

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /load more/i })).toBeNull();
    });
  });
});
