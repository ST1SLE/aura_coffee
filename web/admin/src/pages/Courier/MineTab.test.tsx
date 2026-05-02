import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import i18n from '@/i18n/config';
import { ApiError } from '@/api/client';
import * as courierApi from '@/api/courier';
import { MineTab } from '@/pages/Courier/MineTab';
import type {
  CourierAssignmentResponse,
  CourierAssignmentStatus,
} from '@/api/courier';

vi.mock('@/api/courier', async (importOriginal) => {
  const original = await importOriginal<typeof courierApi>();
  return {
    ...original,
    listMine: vi.fn(),
    pickupAssignment: vi.fn(),
    deliverAssignment: vi.fn(),
  };
});

function makeAssignment(
  id: string,
  status: CourierAssignmentStatus,
): CourierAssignmentResponse {
  return {
    id,
    order_id: `o-${id}`,
    status,
    delivery_address: { address_line: `addr-${id}` },
    total: 30000,
    requested_time: null,
  };
}

function renderTab() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MineTab />
    </QueryClientProvider>,
  );
}

describe('MineTab', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    await i18n.changeLanguage('ru');
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('COURIER_ASSIGNED: показывает "Забрал" и вызывает pickupAssignment', async () => {
    vi.mocked(courierApi.listMine).mockResolvedValue([
      makeAssignment('a-assigned', 'COURIER_ASSIGNED'),
    ]);
    vi.mocked(courierApi.pickupAssignment).mockResolvedValue(
      makeAssignment('a-assigned', 'PICKED_UP'),
    );

    renderTab();

    const btn = await screen.findByRole('button', { name: /забрал/i });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(courierApi.pickupAssignment).toHaveBeenCalledWith('a-assigned');
    });
    expect(courierApi.deliverAssignment).not.toHaveBeenCalled();
  });

  it('PICKED_UP: показывает "Доставлен" и вызывает deliverAssignment', async () => {
    vi.mocked(courierApi.listMine).mockResolvedValue([
      makeAssignment('a-picked', 'PICKED_UP'),
    ]);
    vi.mocked(courierApi.deliverAssignment).mockResolvedValue(
      makeAssignment('a-picked', 'DELIVERED'),
    );

    renderTab();

    const btn = await screen.findByRole('button', { name: /доставлен/i });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(courierApi.deliverAssignment).toHaveBeenCalledWith('a-picked');
    });
    expect(courierApi.pickupAssignment).not.toHaveBeenCalled();
  });

  it('DELIVERED и CANCELLED: кнопки действия не рендерятся', async () => {
    vi.mocked(courierApi.listMine).mockResolvedValue([
      makeAssignment('a-done', 'DELIVERED'),
      makeAssignment('a-cancel', 'CANCELLED'),
    ]);

    renderTab();

    await screen.findByText('addr-a-done');
    expect(screen.queryByRole('button', { name: /забрал/i })).toBeNull();
    expect(screen.queryByRole('button', { name: /доставлен/i })).toBeNull();
  });

  it('403 на listMine показывает явную ошибку доступа', async () => {
    vi.mocked(courierApi.listMine).mockRejectedValue(
      new ApiError(403, { detail: 'forbidden' }, 'forbidden'),
    );

    renderTab();

    await waitFor(() => {
      expect(
        screen.getByText(/Доступ к курьерским заказам разрешён только курьерам/i),
      ).toBeDefined();
    });
  });

  it('пустой список показывает локализованный empty-state', async () => {
    vi.mocked(courierApi.listMine).mockResolvedValue([]);

    renderTab();

    await waitFor(() => {
      expect(screen.getByText(/У вас нет назначенных заказов/i)).toBeDefined();
    });
  });
});
