import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';

vi.mock('./client', () => ({
  apiRequest: vi.fn(),
  authenticatedFetch: vi.fn(),
}));

import { apiRequest } from './client';
import { getCart, addItem, updateItem, removeItem } from './cart';
import type { CartItemCreate } from './cartTypes';

const cartResponse = {
  items: [],
  subtotal: 0,
  currency: 'RUB',
  expires_at: '2099-01-01T00:00:00Z',
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe('getCart', () => {
  it('calls GET /api/v1/cart', async () => {
    (apiRequest as Mock).mockResolvedValue(cartResponse);

    await getCart();

    expect(apiRequest).toHaveBeenCalledOnce();
    const [url, opts] = (apiRequest as Mock).mock.calls[0];
    expect(url).toBe('/api/v1/cart');
    expect(opts).toBeUndefined();
  });
});

describe('addItem', () => {
  it('passes POST with CartItemCreate body to /api/v1/cart/items', async () => {
    (apiRequest as Mock).mockResolvedValue(cartResponse);

    const payload: CartItemCreate = {
      menu_item_id: 3,
      size_option_id: 1,
      modifier_ids: [4],
      quantity: 1,
    };
    await addItem(payload);

    const [url, opts] = (apiRequest as Mock).mock.calls[0];
    expect(url).toBe('/api/v1/cart/items');
    expect(opts.method).toBe('POST');
    expect(JSON.parse(opts.body as string)).toEqual(payload);
  });
});

describe('updateItem', () => {
  it('passes PATCH with quantity body to /api/v1/cart/items/:id', async () => {
    (apiRequest as Mock).mockResolvedValue(cartResponse);

    await updateItem('abc', { quantity: 3 });

    const [url, opts] = (apiRequest as Mock).mock.calls[0];
    expect(url).toBe('/api/v1/cart/items/abc');
    expect(opts.method).toBe('PATCH');
    expect(JSON.parse(opts.body as string)).toEqual({ quantity: 3 });
  });
});

describe('removeItem', () => {
  it('sends DELETE to /api/v1/cart/items/:id', async () => {
    (apiRequest as Mock).mockResolvedValue(cartResponse);

    await removeItem('abc-123');

    const [url, opts] = (apiRequest as Mock).mock.calls[0];
    expect(url).toBe('/api/v1/cart/items/abc-123');
    expect(opts.method).toBe('DELETE');
  });
});
