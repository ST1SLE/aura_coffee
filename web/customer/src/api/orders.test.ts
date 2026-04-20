import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';

vi.mock('./client', () => ({
  authenticatedFetch: vi.fn(),
  apiRequest: vi.fn(),
}));

import { authenticatedFetch } from './client';
import { createOrder, OrderApiError } from './orders';

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
  status: 'CREATED',
  type: 'PICKUP',
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

describe('createOrder PICKUP', () => {
  it('POSTs to /api/v1/orders with type=PICKUP only', async () => {
    (authenticatedFetch as Mock).mockResolvedValue(asOk(orderResp));

    await createOrder({ type: 'PICKUP' });

    const [url, opts] = (authenticatedFetch as Mock).mock.calls[0];
    expect(url).toBe('/api/v1/orders');
    expect(opts.method).toBe('POST');
    const body = JSON.parse(opts.body);
    expect(body.type).toBe('PICKUP');
    expect(body.delivery_address).toBeUndefined();
    expect(body.delivery_address_id).toBeUndefined();
  });
});

describe('createOrder DELIVERY saved', () => {
  it('sends delivery_address_id only', async () => {
    (authenticatedFetch as Mock).mockResolvedValue(asOk(orderResp));

    await createOrder({
      type: 'DELIVERY',
      delivery_address_id: 'a1',
    });

    const [, opts] = (authenticatedFetch as Mock).mock.calls[0];
    const body = JSON.parse(opts.body);
    expect(body.type).toBe('DELIVERY');
    expect(body.delivery_address_id).toBe('a1');
    expect(body.delivery_address).toBeUndefined();
  });
});

describe('createOrder DELIVERY new', () => {
  it('sends delivery_address only', async () => {
    (authenticatedFetch as Mock).mockResolvedValue(asOk(orderResp));

    await createOrder({
      type: 'DELIVERY',
      delivery_address: {
        text: 'X',
        lat: 1,
        lon: 2,
        apartment: '5',
      },
    });

    const [, opts] = (authenticatedFetch as Mock).mock.calls[0];
    const body = JSON.parse(opts.body);
    expect(body.type).toBe('DELIVERY');
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
      await createOrder({ type: 'PICKUP' });
      throw new Error('expected throw');
    } catch (e) {
      expect(e).toBeInstanceOf(OrderApiError);
      const err = e as OrderApiError;
      expect(err.status).toBe(409);
      expect(err.detail).toContain('вне зоны');
    }
  });
});
