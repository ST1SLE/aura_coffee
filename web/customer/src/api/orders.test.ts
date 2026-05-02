import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';

vi.mock('./client', () => ({
  authenticatedFetch: vi.fn(),
  apiRequest: vi.fn(),
}));

import { authenticatedFetch } from './client';
import {
  cancelOrder,
  createOrder,
  getOrder,
  listOrders,
  OrderApiError,
  repeatOrder,
} from './orders';

const asOk = (body: unknown, status = 201): Response =>
  ({
    ok: true,
    status,
    json: async () => body,
  }) as unknown as Response;

const asError = (status: number, body: unknown = { detail: 'err' }): Response =>
  ({
    ok: false,
    status,
    json: async () => body,
  }) as unknown as Response;

const orderResp = {
  id: '00000000-0000-0000-0000-000000000001',
  status: 'created',
  type: 'pickup',
  items: [],
  subtotal: 0,
  discount_amount: 0,
  points_used: 0,
  delivery_fee: 0,
  total: 0,
  estimated_accrual: 0,
  created_at: '2026-04-20T00:00:00Z',
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe('createOrder pickup', () => {
  it('POSTs to /api/v1/orders with type=pickup only', async () => {
    (authenticatedFetch as Mock).mockResolvedValue(asOk(orderResp));

    await createOrder({ type: 'pickup' });

    const [url, opts] = (authenticatedFetch as Mock).mock.calls[0];
    expect(url).toBe('/api/v1/orders');
    expect(opts.method).toBe('POST');
    const body = JSON.parse(opts.body);
    expect(body.type).toBe('pickup');
    expect(body.delivery_address).toBeUndefined();
    expect(body.delivery_address_id).toBeUndefined();
  });
});

describe('createOrder delivery saved', () => {
  it('sends delivery_address_id only', async () => {
    (authenticatedFetch as Mock).mockResolvedValue(asOk(orderResp));

    await createOrder({
      type: 'delivery',
      delivery_address_id: 'a1',
    });

    const [, opts] = (authenticatedFetch as Mock).mock.calls[0];
    const body = JSON.parse(opts.body);
    expect(body.type).toBe('delivery');
    expect(body.delivery_address_id).toBe('a1');
    expect(body.delivery_address).toBeUndefined();
  });
});

describe('createOrder delivery new', () => {
  it('sends delivery_address only', async () => {
    (authenticatedFetch as Mock).mockResolvedValue(asOk(orderResp));

    await createOrder({
      type: 'delivery',
      delivery_address: {
        text: 'X',
        lat: 1,
        lon: 2,
        apartment: '5',
      },
    });

    const [, opts] = (authenticatedFetch as Mock).mock.calls[0];
    const body = JSON.parse(opts.body);
    expect(body.type).toBe('delivery');
    expect(body.delivery_address).toEqual({
      text: 'X',
      lat: 1,
      lon: 2,
      apartment: '5',
    });
    expect(body.delivery_address_id).toBeUndefined();
  });
});

describe('createOrder errors', () => {
  it('throws OrderApiError with status and detail on 409', async () => {
    (authenticatedFetch as Mock).mockResolvedValue(
      asError(409, { detail: 'Адрес вне зоны доставки (максимум 10 км).' }),
    );

    try {
      await createOrder({ type: 'pickup' });
      throw new Error('expected throw');
    } catch (e) {
      expect(e).toBeInstanceOf(OrderApiError);
      const err = e as OrderApiError;
      expect(err.status).toBe(409);
      expect(err.detail).toContain('вне зоны');
    }
  });
});

describe('order detail and history', () => {
  it('GETs /api/v1/orders/{id}', async () => {
    (authenticatedFetch as Mock).mockResolvedValue(asOk(orderResp));

    await getOrder('o1');

    expect(authenticatedFetch).toHaveBeenCalledWith('/api/v1/orders/o1');
  });

  it('GETs paginated history and requires orders[] shape', async () => {
    const body = {
      orders: [{ ...orderResp, id: 'o2' }],
      total_count: 1,
      page: 1,
      per_page: 20,
    };
    (authenticatedFetch as Mock).mockResolvedValue(asOk(body));

    const result = await listOrders(1, 20);

    expect(authenticatedFetch).toHaveBeenCalledWith(
      '/api/v1/orders?page=1&per_page=20',
    );
    expect(result.orders[0].id).toBe('o2');
  });

  it('rejects older items[] history shape', async () => {
    (authenticatedFetch as Mock).mockResolvedValue(
      asOk({
        items: [{ ...orderResp, id: 'o2' }],
        total_count: 1,
        page: 1,
        per_page: 20,
      }),
    );

    await expect(listOrders()).rejects.toMatchObject({
      status: 500,
      detail: 'Invalid order history payload',
    });
  });
});

describe('order actions', () => {
  it('POSTs customer cancel with null reason body', async () => {
    (authenticatedFetch as Mock).mockResolvedValue(
        asOk({ ...orderResp, status: 'cancelled' }),
    );

    await cancelOrder('o1');

    const [url, opts] = (authenticatedFetch as Mock).mock.calls[0];
    expect(url).toBe('/api/v1/orders/o1/cancel');
    expect(opts.method).toBe('POST');
    expect(JSON.parse(opts.body)).toEqual({ reason: null });
  });

  it('POSTs repeat order without inventing payload', async () => {
    (authenticatedFetch as Mock).mockResolvedValue(
      asOk({ added_to_cart: 2, skipped: [] }),
    );

    const result = await repeatOrder('o1');

    expect(authenticatedFetch).toHaveBeenCalledWith(
      '/api/v1/orders/o1/repeat',
      { method: 'POST' },
    );
    expect(result.added_to_cart).toBe(2);
  });
});
