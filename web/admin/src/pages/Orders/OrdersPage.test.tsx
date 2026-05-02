import { act, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import i18n from '@/i18n/config';
import { OrdersPage } from './OrdersPage';
import * as ordersApi from '@/api/admin-orders';
import type { OrderListResponse } from '@/api/admin-orders';

vi.mock('@/api/admin-orders', async (importOriginal) => {
  const original = await importOriginal<typeof ordersApi>();
  return {
    ...original,
    listAdminOrders: vi.fn(),
    getAdminOrder: vi.fn(),
  };
});

function emptyOrders(): OrderListResponse {
  return {
    orders: [],
    total_count: 0,
    page: 1,
    per_page: 20,
  };
}

function renderOrdersPage(initialPath = '/orders') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/orders" element={<OrdersPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

async function flushEffects(): Promise<void> {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe('OrdersPage polling', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('en');
    vi.useFakeTimers();
    vi.mocked(ordersApi.listAdminOrders).mockResolvedValue(emptyOrders());
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('polls the active feed every 5 seconds while visible', async () => {
    renderOrdersPage();

    await flushEffects();
    expect(ordersApi.listAdminOrders).toHaveBeenCalledTimes(1);
    expect(ordersApi.listAdminOrders).toHaveBeenLastCalledWith({
      status: 'active',
      page: 1,
      per_page: 20,
    });

    await act(async () => {
      vi.advanceTimersByTime(4_999);
    });
    expect(ordersApi.listAdminOrders).toHaveBeenCalledTimes(1);

    await act(async () => {
      vi.advanceTimersByTime(1);
    });
    await flushEffects();
    expect(ordersApi.listAdminOrders).toHaveBeenCalledTimes(2);
  });

  it('does not poll non-active status filters', async () => {
    renderOrdersPage('/orders?status=completed');

    await flushEffects();
    expect(ordersApi.listAdminOrders).toHaveBeenCalledTimes(1);
    expect(ordersApi.listAdminOrders).toHaveBeenLastCalledWith({
      status: 'completed',
      page: 1,
      per_page: 20,
    });

    await act(async () => {
      vi.advanceTimersByTime(10_000);
    });

    expect(ordersApi.listAdminOrders).toHaveBeenCalledTimes(1);
    expect(screen.getByText('No orders')).toBeInTheDocument();
  });
});
