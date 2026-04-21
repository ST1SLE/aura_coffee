import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import '@testing-library/jest-dom';
import i18n from '@/i18n/config';
import { OrderDetailDialog } from './OrderDetailDialog';
import type { OrderResponse, OrderStatus, OrderType } from '@/api/admin-orders';
import type { StaffRole } from '@/lib/auth';

// Mock useCurrentRole — тест перезаписывает роль перед каждым блоком.
let currentRole: StaffRole | null = 'admin';
vi.mock('@/lib/auth', async () => {
  const actual = await vi.importActual<typeof import('@/lib/auth')>('@/lib/auth');
  return {
    ...actual,
    useCurrentRole: () => currentRole,
  };
});

function makeOrder(overrides: Partial<OrderResponse> = {}): OrderResponse {
  return {
    id: overrides.id ?? 'order-uuid-1',
    user_id: overrides.user_id ?? 'user-uuid-1',
    status: overrides.status ?? 'paid',
    type: overrides.type ?? 'pickup',
    subtotal: overrides.subtotal ?? 30000,
    discount_amount: overrides.discount_amount ?? 0,
    delivery_fee: overrides.delivery_fee ?? 0,
    total: overrides.total ?? 30000,
    created_at: overrides.created_at ?? '2026-04-20T10:00:00Z',
    items: overrides.items ?? [],
  };
}

function mockFetchJson(fetchMock: ReturnType<typeof vi.fn>, body: unknown, status = 200) {
  fetchMock.mockResolvedValue(
    new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    }),
  );
}

describe('OrderDetailDialog', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(async () => {
    await i18n.changeLanguage('ru');
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    localStorage.clear();
    localStorage.setItem('accessToken', 'test');
    currentRole = 'admin';
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  // ── 5.2 breakdown rendering ───────────────────────────────────────────────

  test('renders money breakdown in kopecks → rubles', () => {
    const order = makeOrder({
      subtotal: 35000,
      discount_amount: 5000,
      delivery_fee: 0,
      total: 30000,
    });
    render(
      <OrderDetailDialog
        order={order}
        open={true}
        onClose={vi.fn()}
        onAction={vi.fn()}
      />,
    );
    // Intl использует NBSP между числом и символом валюты
    expect(screen.getByText(/^350,00\s*₽$/)).toBeInTheDocument();
    expect(screen.getByText(/^-50,00\s*₽$/)).toBeInTheDocument();
    expect(screen.getByText(/^0,00\s*₽$/)).toBeInTheDocument();
    expect(screen.getByText(/^300,00\s*₽$/)).toBeInTheDocument();
  });

  // ── 5.3 omits PII keys ─────────────────────────────────────────────────────

  test('does not render PII field labels (display_name / address / points_used)', () => {
    const order = makeOrder();
    render(
      <OrderDetailDialog
        order={order}
        open={true}
        onClose={vi.fn()}
        onAction={vi.fn()}
      />,
    );
    expect(i18n.exists('pages.orders.detail.display_name')).toBe(false);
    expect(i18n.exists('pages.orders.detail.address')).toBe(false);
    expect(i18n.exists('pages.orders.detail.points_used')).toBe(false);
    expect(screen.queryByText(/display.?name/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/адрес/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/points/i)).not.toBeInTheDocument();
  });

  // ── 6.2–6.8 role-gated button visibility ──────────────────────────────────

  const cases: Array<{
    label: string;
    role: StaffRole;
    status: OrderStatus;
    type: OrderType;
    visible: string[];
    hidden: string[];
  }> = [
    {
      label: 'barista on PAID: sees accept, not cancel',
      role: 'barista',
      status: 'paid',
      type: 'pickup',
      visible: ['order-action-accept'],
      hidden: ['order-action-cancel', 'order-action-ready', 'order-action-handout'],
    },
    {
      label: 'admin on PAID: sees accept AND cancel',
      role: 'admin',
      status: 'paid',
      type: 'pickup',
      visible: ['order-action-accept', 'order-action-cancel'],
      hidden: ['order-action-ready', 'order-action-handout'],
    },
    {
      label: 'barista on PREPARING: sees ready, not cancel',
      role: 'barista',
      status: 'preparing',
      type: 'pickup',
      visible: ['order-action-ready'],
      hidden: ['order-action-cancel', 'order-action-accept', 'order-action-handout'],
    },
    {
      label: 'barista on READY pickup: sees handout',
      role: 'barista',
      status: 'ready',
      type: 'pickup',
      visible: ['order-action-handout'],
      hidden: ['order-action-accept', 'order-action-ready', 'order-action-cancel'],
    },
    {
      label: 'barista on READY delivery: does NOT see handout',
      role: 'barista',
      status: 'ready',
      type: 'delivery',
      visible: [],
      hidden: [
        'order-action-handout',
        'order-action-accept',
        'order-action-ready',
        'order-action-cancel',
      ],
    },
    {
      label: 'barista on COMPLETED: no action buttons',
      role: 'barista',
      status: 'completed',
      type: 'pickup',
      visible: [],
      hidden: [
        'order-action-accept',
        'order-action-ready',
        'order-action-handout',
        'order-action-cancel',
      ],
    },
    {
      label: 'admin on CANCELLED: no action buttons',
      role: 'admin',
      status: 'cancelled',
      type: 'pickup',
      visible: [],
      hidden: [
        'order-action-accept',
        'order-action-ready',
        'order-action-handout',
        'order-action-cancel',
      ],
    },
  ];

  for (const c of cases) {
    test(c.label, () => {
      currentRole = c.role;
      const order = makeOrder({ status: c.status, type: c.type });
      render(
        <OrderDetailDialog
          order={order}
          open={true}
          onClose={vi.fn()}
          onAction={vi.fn()}
        />,
      );
      for (const tid of c.visible) {
        expect(screen.getByTestId(tid)).toBeInTheDocument();
      }
      for (const tid of c.hidden) {
        expect(screen.queryByTestId(tid)).not.toBeInTheDocument();
      }
    });
  }

  // ── 6.9 click Accept → PATCH /status body {new_status: preparing} ─────────

  test('click accept → PATCH /status with {new_status: preparing} and calls onAction', async () => {
    currentRole = 'barista';
    mockFetchJson(fetchMock, { id: 'order-uuid-1', status: 'preparing' });
    const onAction = vi.fn();
    const order = makeOrder({ id: 'order-uuid-1', status: 'paid' });
    render(
      <OrderDetailDialog
        order={order}
        open={true}
        onClose={vi.fn()}
        onAction={onAction}
      />,
    );
    fireEvent.click(screen.getByTestId('order-action-accept'));
    await waitFor(() => expect(onAction).toHaveBeenCalledTimes(1));
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain('/api/v1/orders/order-uuid-1/status');
    expect(init.method).toBe('PATCH');
    expect(JSON.parse(init.body as string)).toEqual({ new_status: 'preparing' });
  });

  // ── 7.2 cancel happy path ─────────────────────────────────────────────────

  test('cancel happy-path: opens confirm → POST /cancel body {reason: null}', async () => {
    currentRole = 'admin';
    mockFetchJson(fetchMock, { id: 'order-uuid-1', status: 'cancelled' });
    const onAction = vi.fn();
    const order = makeOrder({ id: 'order-uuid-1', status: 'paid' });
    render(
      <OrderDetailDialog
        order={order}
        open={true}
        onClose={vi.fn()}
        onAction={onAction}
      />,
    );
    fireEvent.click(screen.getByTestId('order-action-cancel'));
    fireEvent.click(await screen.findByTestId('order-cancel-confirm'));
    await waitFor(() => expect(onAction).toHaveBeenCalledTimes(1));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain('/api/v1/orders/order-uuid-1/cancel');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body as string)).toEqual({ reason: null });
  });

  // ── 7.3 cancel abort path ─────────────────────────────────────────────────

  test('cancel abort-path: abort closes sub-dialog, no fetch call', async () => {
    currentRole = 'admin';
    const order = makeOrder({ status: 'paid' });
    render(
      <OrderDetailDialog
        order={order}
        open={true}
        onClose={vi.fn()}
        onAction={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByTestId('order-action-cancel'));
    fireEvent.click(await screen.findByTestId('order-cancel-abort'));
    // После закрытия sub-dialog confirm/abort кнопки уходят из DOM.
    await waitFor(() =>
      expect(screen.queryByTestId('order-cancel-confirm')).not.toBeInTheDocument(),
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
