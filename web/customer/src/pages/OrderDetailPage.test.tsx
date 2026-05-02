import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi, type Mock } from 'vitest';
import '@/i18n/config';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock('@/api/orders', async () => {
  const actual =
    await vi.importActual<typeof import('@/api/orders')>('@/api/orders');
  return {
    ...actual,
    getOrder: vi.fn(),
    cancelOrder: vi.fn(),
    repeatOrder: vi.fn(),
  };
});

import {
  cancelOrder,
  getOrder,
  repeatOrder,
  type OrderResponse,
  type OrderStatus,
} from '@/api/orders';
import { OrderDetailPage } from './OrderDetailPage';

const statusPattern: Record<OrderStatus, RegExp> = {
  created: /ожидает оплаты|awaiting payment/i,
  paid: /^оплачен$|^paid$/i,
  preparing: /готовится|preparing/i,
  ready: /готов|ready/i,
  in_delivery: /в доставке|in delivery/i,
  completed: /завершён|completed/i,
  cancelled: /отменён|cancelled/i,
};

const order: OrderResponse = {
  id: '12345678-0000-0000-0000-000000000000',
  status: 'paid',
  type: 'pickup',
  items: [
    {
      id: 'line-1',
      menu_item_name_ru: 'Капучино',
      menu_item_name_en: 'Cappuccino',
      size_label: '300 мл',
      unit_price: 22000,
      modifiers_snapshot: [],
      quantity: 1,
      line_total: 22000,
    },
  ],
  subtotal: 22000,
  discount_amount: 0,
  points_used: 0,
  delivery_fee: 0,
  total: 22000,
  estimated_accrual: 11,
  confirmation_url: null,
  created_at: '2026-05-02T10:00:00Z',
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={[`/orders/${order.id}`]}>
      <Routes>
        <Route path="/orders/:orderId" element={<OrderDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('OrderDetailPage status states', () => {
  it.each<OrderStatus>([
    'created',
    'paid',
    'preparing',
    'ready',
    'in_delivery',
    'completed',
    'cancelled',
  ])('renders %s state from server order', async (status) => {
    (getOrder as Mock).mockResolvedValue({ ...order, status });

    renderPage();

    await waitFor(() => {
      expect(
        screen.getByText(/заказ #12345678|order #12345678/i),
      ).toBeDefined();
    });
    expect(screen.getAllByText(statusPattern[status]).length).toBeGreaterThan(
      0,
    );
    expect(screen.getByText(/капучино|cappuccino/i)).toBeDefined();
  });

  it('shows cancel only while PAID and updates from cancel response', async () => {
    (getOrder as Mock).mockResolvedValue(order);
    (cancelOrder as Mock).mockResolvedValue({ ...order, status: 'cancelled' });

    renderPage();

    const cancelButton = await screen.findByRole('button', {
      name: /отменить заказ|cancel order/i,
    });
    fireEvent.click(cancelButton);

    await waitFor(() => {
      expect(cancelOrder).toHaveBeenCalledWith(order.id);
      expect(screen.getAllByText(/отменён|cancelled/i).length).toBeGreaterThan(
        0,
      );
    });
  });

  it('does not show cancel outside PAID', async () => {
    (getOrder as Mock).mockResolvedValue({ ...order, status: 'preparing' });

    renderPage();

    await screen.findByText(/капучино|cappuccino/i);
    expect(
      screen.queryByRole('button', { name: /отменить заказ|cancel order/i }),
    ).toBeNull();
  });

  it('treats zero-total PAID order as complete without payment redirect', async () => {
    (getOrder as Mock).mockResolvedValue({ ...order, total: 0 });

    renderPage();

    await waitFor(() => {
      expect(
        screen.getByText(/yukassa redirect is not needed|баллами/i),
      ).toBeDefined();
    });
  });

  it('repeats an order and opens the cart', async () => {
    (getOrder as Mock).mockResolvedValue(order);
    (repeatOrder as Mock).mockResolvedValue({ added_to_cart: 1, skipped: [] });

    renderPage();

    fireEvent.click(
      await screen.findByRole('button', { name: /повторить|repeat/i }),
    );

    await waitFor(() => {
      expect(repeatOrder).toHaveBeenCalledWith(order.id);
      expect(mockNavigate).toHaveBeenCalledWith('/cart');
    });
  });

  it('passes skipped repeat-order entries to the cart', async () => {
    const skipped = [
      {
        reason: 'menu_item_unavailable',
        message_ru: 'Латте сейчас недоступен',
        message_en: 'Latte is unavailable',
      },
    ];
    (getOrder as Mock).mockResolvedValue(order);
    (repeatOrder as Mock).mockResolvedValue({ added_to_cart: 1, skipped });

    renderPage();

    fireEvent.click(
      await screen.findByRole('button', { name: /повторить|repeat/i }),
    );

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/cart', {
        state: { repeatOrderSkipped: skipped },
      });
    });
  });
});

describe('OrderDetailPage payment handoff', () => {
  it('redirects to confirmation_url for CREATED orders', async () => {
    const originalLocation = window.location;
    const assign = vi.fn();
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { ...originalLocation, assign },
    });
    (getOrder as Mock).mockResolvedValue({
      ...order,
      status: 'created',
      confirmation_url: 'https://yookassa.example/pay/1',
    });

    try {
      renderPage();

      await waitFor(() => {
        expect(assign).toHaveBeenCalledWith('https://yookassa.example/pay/1');
      });
    } finally {
      Object.defineProperty(window, 'location', {
        configurable: true,
        value: originalLocation,
      });
    }
  });
});
