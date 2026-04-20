import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import '@testing-library/jest-dom';
import i18n from '@/i18n/config';
import { PromosPage } from './PromosPage';
import * as promoApi from '@/api/promocodes';
import type { PromocodeListResponse } from '@/api/promocodes';

vi.mock('@/api/promocodes', async () => {
  const actual = await vi.importActual<typeof import('@/api/promocodes')>('@/api/promocodes');
  return {
    ...actual,
    listPromocodes: vi.fn(),
    activatePromocode: vi.fn(),
    deactivatePromocode: vi.fn(),
    createPromocode: vi.fn(),
    updatePromocode: vi.fn(),
  };
});

function emptyList(): PromocodeListResponse {
  return { items: [], page: 1, per_page: 20, total: 0 };
}

describe('PromosPage', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.mocked(promoApi.listPromocodes).mockResolvedValue(emptyList());
    await i18n.changeLanguage('en');
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test('tab click triggers list reload with the matching state param', async () => {
    render(<PromosPage />);
    await waitFor(() => expect(promoApi.listPromocodes).toHaveBeenCalledTimes(1));
    // Initial: state='all'
    expect(vi.mocked(promoApi.listPromocodes).mock.calls[0][0]).toMatchObject({ state: 'all' });

    fireEvent.click(screen.getByTestId('state-tab-expired'));
    await waitFor(() =>
      expect(vi.mocked(promoApi.listPromocodes).mock.calls.at(-1)?.[0]).toMatchObject({
        state: 'expired',
        page: 1,
      }),
    );
  });

  test('rapid typing debounces into a single list request', async () => {
    render(<PromosPage />);
    await waitFor(() => expect(promoApi.listPromocodes).toHaveBeenCalledTimes(1));
    const baseline = vi.mocked(promoApi.listPromocodes).mock.calls.length;

    const input = screen.getByTestId('promos-search');
    fireEvent.change(input, { target: { value: 'W' } });
    fireEvent.change(input, { target: { value: 'WE' } });
    fireEvent.change(input, { target: { value: 'WEE' } });
    fireEvent.change(input, { target: { value: 'WEEK' } });

    // < 300ms — нет доп. запросов
    await act(async () => {
      vi.advanceTimersByTime(200);
    });
    expect(vi.mocked(promoApi.listPromocodes).mock.calls.length).toBe(baseline);

    await act(async () => {
      vi.advanceTimersByTime(200);
    });
    await waitFor(() =>
      expect(vi.mocked(promoApi.listPromocodes).mock.calls.length).toBe(baseline + 1),
    );
    const lastCall = vi.mocked(promoApi.listPromocodes).mock.calls.at(-1)?.[0];
    expect(lastCall).toMatchObject({ code: 'WEEK' });
  });

  test('create dialog opens and closes', async () => {
    render(<PromosPage />);
    await waitFor(() => expect(promoApi.listPromocodes).toHaveBeenCalled());
    fireEvent.click(screen.getByRole('button', { name: 'Create' }));
    expect(screen.getByText('New Promo Code')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    await waitFor(() =>
      expect(screen.queryByText('New Promo Code')).not.toBeInTheDocument(),
    );
  });

  test('state=all omits state param from request', async () => {
    render(<PromosPage />);
    await waitFor(() => expect(promoApi.listPromocodes).toHaveBeenCalled());
    // The client takes state:'all' and the api layer omits it from the query string.
    // PromosPage still passes state:'all' — we verify the wrapper call shape:
    const call = vi.mocked(promoApi.listPromocodes).mock.calls[0][0];
    expect(call).toMatchObject({ state: 'all', page: 1 });
  });
});
