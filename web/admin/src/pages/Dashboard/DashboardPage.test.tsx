import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import '@testing-library/jest-dom';
import i18n from '@/i18n/config';
import { DashboardPage } from './DashboardPage';
import * as statsApi from '@/api/admin-stats';
import type { AdminStatsResponse } from '@/api/admin-stats';

vi.mock('@/api/admin-stats', async () => {
  const actual = await vi.importActual<typeof import('@/api/admin-stats')>('@/api/admin-stats');
  return {
    ...actual,
    getAdminStats: vi.fn(),
  };
});

function makeResponse(range: 'today' | 'week' | 'month', over: Partial<AdminStatsResponse> = {}): AdminStatsResponse {
  return {
    range,
    range_start: '2026-03-21T00:00:00Z',
    range_end: '2026-04-20T00:00:00Z',
    revenue_kopecks: 1234500,
    orders_count: 42,
    popular_items: [
      { name_ru: 'Латте', name_en: 'Latte', quantity: 28 },
    ],
    ...over,
  };
}

describe('DashboardPage', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    await i18n.changeLanguage('en');
  });

  test('default range=month — вызывает getAdminStats("month") при mount', async () => {
    vi.mocked(statsApi.getAdminStats).mockResolvedValue(makeResponse('month'));
    render(<DashboardPage />);
    await waitFor(() => expect(statsApi.getAdminStats).toHaveBeenCalledTimes(1));
    expect(vi.mocked(statsApi.getAdminStats).mock.calls[0][0]).toBe('month');
  });

  test('показывает данные из успешного ответа', async () => {
    vi.mocked(statsApi.getAdminStats).mockResolvedValue(
      makeResponse('month', { revenue_kopecks: 1234500, orders_count: 42 }),
    );
    render(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getByTestId('stats-card-revenue')).toBeInTheDocument();
    });
    const revenueCard = screen.getByTestId('stats-card-revenue');
    expect(revenueCard.textContent).toMatch(/12/);
    expect(revenueCard.textContent).toMatch(/345/);
    expect(screen.getByTestId('stats-card-orders')).toHaveTextContent('42');
    expect(screen.getByText('Latte')).toBeInTheDocument();
  });

  test('клик на "Today" → refetch с range=today', async () => {
    vi.mocked(statsApi.getAdminStats).mockResolvedValue(makeResponse('month'));
    render(<DashboardPage />);
    await waitFor(() => expect(statsApi.getAdminStats).toHaveBeenCalledTimes(1));

    vi.mocked(statsApi.getAdminStats).mockResolvedValue(
      makeResponse('today', { orders_count: 3 }),
    );
    fireEvent.click(screen.getByTestId('range-tab-today'));

    await waitFor(() => expect(statsApi.getAdminStats).toHaveBeenCalledTimes(2));
    expect(vi.mocked(statsApi.getAdminStats).mock.calls[1][0]).toBe('today');
    await waitFor(() => {
      expect(screen.getByTestId('stats-card-orders')).toHaveTextContent('3');
    });
  });

  test('пустой popular_items → показывает empty-state', async () => {
    vi.mocked(statsApi.getAdminStats).mockResolvedValue(
      makeResponse('month', { popular_items: [] }),
    );
    render(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getByTestId('popular-items-empty')).toBeInTheDocument();
    });
  });

  test('ApiError(500) → показывает error notification, не крашится', async () => {
    vi.mocked(statsApi.getAdminStats).mockRejectedValue(
      new statsApi.ApiError(500, { detail: 'boom' }, 'HTTP 500'),
    );
    render(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getByText('Failed to load statistics')).toBeInTheDocument();
    });
    // Страница рендерится (не throw'ит).
    expect(screen.getByTestId('dashboard-page')).toBeInTheDocument();
  });

  test('ApiError(403) тоже отображается как loadFailed', async () => {
    vi.mocked(statsApi.getAdminStats).mockRejectedValue(
      new statsApi.ApiError(403, { detail: 'forbidden' }, 'HTTP 403'),
    );
    render(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getByText('Failed to load statistics')).toBeInTheDocument();
    });
  });
});
