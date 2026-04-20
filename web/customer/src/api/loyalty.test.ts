import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';

vi.mock('./client', () => ({
  authenticatedFetch: vi.fn(),
}));

import { authenticatedFetch } from './client';
import {
  getLoyaltyBalance,
  listLoyaltyTransactions,
  type LoyaltyTransaction,
} from './loyalty';

const asOk = (body: unknown, status = 200): Response =>
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

const tx = (over: Partial<LoyaltyTransaction> = {}): LoyaltyTransaction => ({
  id: '11111111-1111-1111-1111-111111111111',
  order_id: '22222222-2222-2222-2222-222222222222',
  type: 'accrual',
  amount: 50,
  balance_after: 240,
  description: null,
  created_at: '2026-04-20T12:00:00Z',
  ...over,
});

beforeEach(() => {
  vi.clearAllMocks();
});

describe('getLoyaltyBalance', () => {
  it('GETs /api/v1/profile/loyalty and returns balance shape', async () => {
    (authenticatedFetch as Mock).mockResolvedValue(
      asOk({ balance: 240, lifetime_accrued: 1200 }),
    );

    const result = await getLoyaltyBalance();

    const [url, opts] = (authenticatedFetch as Mock).mock.calls[0];
    expect(url).toBe('/api/v1/profile/loyalty');
    expect(opts).toBeUndefined();
    expect(result).toEqual({ balance: 240, lifetime_accrued: 1200 });
  });

  it('throws on non-ok response', async () => {
    (authenticatedFetch as Mock).mockResolvedValue(asError(500));
    await expect(getLoyaltyBalance()).rejects.toBeDefined();
  });

  it('throws on malformed payload (missing balance)', async () => {
    (authenticatedFetch as Mock).mockResolvedValue(
      asOk({ lifetime_accrued: 1200 }),
    );
    await expect(getLoyaltyBalance()).rejects.toBeDefined();
  });
});

describe('listLoyaltyTransactions', () => {
  it('GETs /api/v1/profile/loyalty/transactions with query params', async () => {
    (authenticatedFetch as Mock).mockResolvedValue(
      asOk({
        items: [tx(), tx({ id: '33333333-3333-3333-3333-333333333333' })],
        page: 1,
        per_page: 20,
        total: 2,
      }),
    );

    const result = await listLoyaltyTransactions(1, 20);

    const [url] = (authenticatedFetch as Mock).mock.calls[0];
    expect(url).toBe('/api/v1/profile/loyalty/transactions?page=1&per_page=20');
    expect(result.items).toHaveLength(2);
    expect(result.page).toBe(1);
    expect(result.per_page).toBe(20);
    expect(result.total).toBe(2);
  });

  it('parses nullable order_id and description', async () => {
    (authenticatedFetch as Mock).mockResolvedValue(
      asOk({
        items: [
          tx({ order_id: null, description: 'Admin bonus', type: 'admin_adjustment' }),
        ],
        page: 1,
        per_page: 20,
        total: 1,
      }),
    );
    const result = await listLoyaltyTransactions(1, 20);
    expect(result.items[0].order_id).toBeNull();
    expect(result.items[0].description).toBe('Admin bonus');
    expect(result.items[0].type).toBe('admin_adjustment');
  });

  it('throws on non-ok response', async () => {
    (authenticatedFetch as Mock).mockResolvedValue(asError(401));
    await expect(listLoyaltyTransactions(1, 20)).rejects.toBeDefined();
  });
});
