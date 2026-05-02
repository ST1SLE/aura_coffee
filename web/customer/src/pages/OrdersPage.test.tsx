import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
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
    listOrders: vi.fn(),
    repeatOrder: vi.fn(),
  };
});

import { listOrders, repeatOrder, type OrderResponse } from '@/api/orders';
import { OrdersPage } from './OrdersPage';

const baseOrder: OrderResponse = {
  id: '12345678-0000-0000-0000-000000000000',
  status: 'paid',
  type: 'pickup',
  items: [
    {
      id: 'line-1',
      menu_item_name_ru: 'Латте',
      menu_item_name_en: 'Latte',
      size_label: '300 мл',
      unit_price: 25000,
      modifiers_snapshot: [{ name_ru: 'Ваниль', name_en: 'Vanilla' }],
      quantity: 2,
      line_total: 50000,
    },
  ],
  subtotal: 50000,
  discount_amount: 0,
  points_used: 0,
  delivery_fee: 0,
  total: 50000,
  estimated_accrual: 25,
  confirmation_url: null,
  created_at: '2026-05-02T10:00:00Z',
};

function renderPage() {
  return render(
    <MemoryRouter>
      <OrdersPage />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('OrdersPage', () => {
  it('renders empty history state', async () => {
    (listOrders as Mock).mockResolvedValue({
      orders: [],
      total_count: 0,
      page: 1,
      per_page: 20,
    });

    renderPage();

    expect(screen.getByRole('status').textContent).toMatch(
      /загружаем|loading/i,
    );
    await waitFor(() => {
      expect(screen.getByText(/заказов пока нет|no orders yet/i)).toBeDefined();
    });
  });

  it('splits active and completed orders and renders immutable item snapshots', async () => {
    (listOrders as Mock).mockResolvedValue({
      orders: [
        { ...baseOrder, id: 'active-0000', status: 'preparing' },
        { ...baseOrder, id: 'done-0000', status: 'completed' },
      ],
      total_count: 2,
      page: 1,
      per_page: 20,
    });

    renderPage();

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /^активные$|^active$/i }),
      ).toBeDefined();
    });
    expect(
      screen.getByRole('heading', { name: /^история$|^history$/i }),
    ).toBeDefined();
    expect(screen.getAllByText(/латте|latte/i)).toHaveLength(2);
    expect(screen.getAllByText(/ваниль|vanilla/i)).toHaveLength(2);
    expect(
      screen
        .getAllByRole('link', { name: /подробнее|details/i })[0]
        .getAttribute('href'),
    ).toBe('/orders/active-0000');
  });

  it('repeats an order and opens the cart', async () => {
    (listOrders as Mock).mockResolvedValue({
      orders: [baseOrder],
      total_count: 1,
      page: 1,
      per_page: 20,
    });
    (repeatOrder as Mock).mockResolvedValue({ added_to_cart: 1, skipped: [] });

    renderPage();

    await screen.findByText(/латте|latte/i);
    fireEvent.click(screen.getByRole('button', { name: /повторить|repeat/i }));

    await waitFor(() => {
      expect(repeatOrder).toHaveBeenCalledWith(baseOrder.id);
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
    (listOrders as Mock).mockResolvedValue({
      orders: [baseOrder],
      total_count: 1,
      page: 1,
      per_page: 20,
    });
    (repeatOrder as Mock).mockResolvedValue({ added_to_cart: 1, skipped });

    renderPage();

    await screen.findByText(/латте|latte/i);
    fireEvent.click(screen.getByRole('button', { name: /повторить|repeat/i }));

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/cart', {
        state: { repeatOrderSkipped: skipped },
      });
    });
  });
});
