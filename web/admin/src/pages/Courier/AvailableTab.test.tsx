import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import i18n from '@/i18n/config';
import { ApiError } from '@/api/client';
import * as courierApi from '@/api/courier';
import { AvailableTab } from '@/pages/Courier/AvailableTab';
import {
  CourierNotifierProvider,
  useCourierNotifier,
} from '@/pages/Courier/notifier-context';
import { NotificationList } from '@/components/ui/notifier';
import type { CourierAssignmentResponse } from '@/api/courier';

function NotifierSink() {
  const { notifications, dismiss } = useCourierNotifier();
  return <NotificationList notifications={notifications} onDismiss={dismiss} />;
}

vi.mock('@/api/courier', async (importOriginal) => {
  const original = await importOriginal<typeof courierApi>();
  return {
    ...original,
    listAvailable: vi.fn(),
    takeAssignment: vi.fn(),
  };
});

function makeAssignment(
  overrides: Partial<CourierAssignmentResponse> = {},
): CourierAssignmentResponse {
  return {
    id: 'a-1',
    order_id: 'o-1',
    status: 'AWAITING_COURIER',
    delivery_address: { address_line: 'ул. Пушкина, 10' },
    total: 45000,
    requested_time: null,
    ...overrides,
  };
}

function renderTab() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return {
    qc,
    ...render(
      <QueryClientProvider client={qc}>
        <CourierNotifierProvider>
          <AvailableTab />
          <NotifierSink />
        </CourierNotifierProvider>
      </QueryClientProvider>,
    ),
  };
}

describe('AvailableTab', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    await i18n.changeLanguage('ru');
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('рендерит карточки для заказов из listAvailable', async () => {
    vi.mocked(courierApi.listAvailable).mockResolvedValue([
      makeAssignment({ id: 'a-1', delivery_address: { address_line: 'адрес-1' } }),
      makeAssignment({ id: 'a-2', delivery_address: { address_line: 'адрес-2' } }),
    ]);

    renderTab();

    await waitFor(() => {
      expect(screen.getByText('адрес-1')).toBeDefined();
      expect(screen.getByText('адрес-2')).toBeDefined();
    });
  });

  it('клик на "Взять" вызывает takeAssignment с id', async () => {
    vi.mocked(courierApi.listAvailable).mockResolvedValue([
      makeAssignment({ id: 'aid-7' }),
    ]);
    vi.mocked(courierApi.takeAssignment).mockResolvedValue(
      makeAssignment({ id: 'aid-7', status: 'COURIER_ASSIGNED' }),
    );

    renderTab();

    const btn = await screen.findByRole('button', { name: /взять/i });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(courierApi.takeAssignment).toHaveBeenCalledWith('aid-7');
    });
  });

  it('409 на takeAssignment показывает тост "Заказ уже взят другим курьером"', async () => {
    vi.mocked(courierApi.listAvailable).mockResolvedValue([
      makeAssignment({ id: 'aid-9' }),
    ]);
    vi.mocked(courierApi.takeAssignment).mockRejectedValue(
      new ApiError(409, { detail: 'already_taken' }, 'conflict'),
    );

    renderTab();

    const btn = await screen.findByRole('button', { name: /взять/i });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(screen.getByText(/Заказ уже взят другим курьером/i)).toBeDefined();
    });
  });

  it('пустой список показывает локализованный empty-state', async () => {
    vi.mocked(courierApi.listAvailable).mockResolvedValue([]);

    renderTab();

    await waitFor(() => {
      expect(screen.getByText(/Сейчас нет доступных заказов/i)).toBeDefined();
    });
  });
});
