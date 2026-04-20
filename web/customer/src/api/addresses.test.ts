import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';

vi.mock('./client', () => ({
  authenticatedFetch: vi.fn(),
  apiRequest: vi.fn(),
}));

import { authenticatedFetch } from './client';
import {
  listAddresses,
  createAddress,
  updateAddress,
  deleteAddress,
  setPrimaryAddress,
  AddressApiError,
  type AddressResponse,
  type AddressCreatePayload,
} from './addresses';

const addr = (over: Partial<AddressResponse> = {}): AddressResponse => ({
  id: 'a1',
  text: 'ул. Ленина 1',
  lat: 1,
  lon: 2,
  label: null,
  apartment: null,
  entrance: null,
  floor: null,
  comment: null,
  is_primary: false,
  ...over,
});

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

beforeEach(() => {
  vi.clearAllMocks();
});

describe('listAddresses', () => {
  it('GETs /api/v1/profile/addresses and returns items', async () => {
    (authenticatedFetch as Mock).mockResolvedValue(
      asOk({ items: [addr({ id: 'a1' }), addr({ id: 'a2' })] }),
    );

    const result = await listAddresses();

    const [url, opts] = (authenticatedFetch as Mock).mock.calls[0];
    expect(url).toBe('/api/v1/profile/addresses');
    expect(opts).toBeUndefined();
    expect(result).toHaveLength(2);
    expect(result[0].id).toBe('a1');
  });
});

describe('createAddress', () => {
  it('POSTs JSON body to /api/v1/profile/addresses', async () => {
    (authenticatedFetch as Mock).mockResolvedValue(asOk(addr(), 201));

    const payload: AddressCreatePayload = {
      text: 'x',
      lat: 1,
      lon: 2,
      label: 'Дом',
      apartment: '5',
    };
    await createAddress(payload);

    const [url, opts] = (authenticatedFetch as Mock).mock.calls[0];
    expect(url).toBe('/api/v1/profile/addresses');
    expect(opts.method).toBe('POST');
    expect(opts.headers['Content-Type']).toBe('application/json');
    expect(JSON.parse(opts.body)).toEqual(payload);
  });
});

describe('updateAddress', () => {
  it('PATCHes with id in URL', async () => {
    (authenticatedFetch as Mock).mockResolvedValue(asOk(addr()));

    await updateAddress('a1', { comment: 'домофон 42' });

    const [url, opts] = (authenticatedFetch as Mock).mock.calls[0];
    expect(url).toBe('/api/v1/profile/addresses/a1');
    expect(opts.method).toBe('PATCH');
    expect(JSON.parse(opts.body)).toEqual({ comment: 'домофон 42' });
  });
});

describe('deleteAddress', () => {
  it('DELETEs /api/v1/profile/addresses/:id', async () => {
    (authenticatedFetch as Mock).mockResolvedValue({
      ok: true,
      status: 204,
      json: async () => ({}),
    } as unknown as Response);

    await deleteAddress('a1');

    const [url, opts] = (authenticatedFetch as Mock).mock.calls[0];
    expect(url).toBe('/api/v1/profile/addresses/a1');
    expect(opts.method).toBe('DELETE');
  });
});

describe('setPrimaryAddress', () => {
  it('POSTs to /{id}/set-primary', async () => {
    (authenticatedFetch as Mock).mockResolvedValue(asOk(addr({ is_primary: true })));

    await setPrimaryAddress('a1');

    const [url, opts] = (authenticatedFetch as Mock).mock.calls[0];
    expect(url).toBe('/api/v1/profile/addresses/a1/set-primary');
    expect(opts.method).toBe('POST');
  });
});

describe('errors', () => {
  it('throws AddressApiError with status and detail on 409', async () => {
    (authenticatedFetch as Mock).mockResolvedValue(
      asError(409, { detail: 'Адрес вне зоны доставки (максимум 10 км).' }),
    );

    try {
      await createAddress({ text: 'x', lat: 1, lon: 2 });
      throw new Error('expected throw');
    } catch (e) {
      expect(e).toBeInstanceOf(AddressApiError);
      const err = e as AddressApiError;
      expect(err.status).toBe(409);
      expect(err.detail).toContain('вне зоны');
    }
  });
});
