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
  setDefaultAddress,
  AddressApiError,
  type AddressResponse,
  type AddressCreatePayload,
} from './addresses';

const addr = (over: Partial<AddressResponse> = {}): AddressResponse => ({
  id: 'a1',
  address_text: 'ул. Ленина 1',
  lat: 1,
  lon: 2,
  label: null,
  apartment: null,
  entrance: null,
  floor: null,
  comment: null,
  is_default: false,
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
  it('GETs /api/v1/profile/addresses and returns a bare array', async () => {
    (authenticatedFetch as Mock).mockResolvedValue(
      asOk([addr({ id: 'a1' }), addr({ id: 'a2' })]),
    );

    const result = await listAddresses();

    const [url, opts] = (authenticatedFetch as Mock).mock.calls[0];
    expect(url).toBe('/api/v1/profile/addresses');
    expect(opts).toBeUndefined();
    expect(result).toHaveLength(2);
    expect(result[0].id).toBe('a1');
  });

  it('returns [] when server body is not an array (fail-soft)', async () => {
    (authenticatedFetch as Mock).mockResolvedValue(
      asOk({ items: [addr(), addr()] }),
    );

    const result = await listAddresses();

    expect(result).toEqual([]);
  });
});

describe('createAddress', () => {
  it('POSTs JSON body with address_text and label to /api/v1/profile/addresses', async () => {
    (authenticatedFetch as Mock).mockResolvedValue(asOk(addr(), 201));

    const payload: AddressCreatePayload = {
      label: 'Дом',
      address_text: 'x',
      lat: 1,
      lon: 2,
      apartment: '5',
      entrance: null,
      floor: null,
      comment: null,
    };
    await createAddress(payload);

    const [url, opts] = (authenticatedFetch as Mock).mock.calls[0];
    expect(url).toBe('/api/v1/profile/addresses');
    expect(opts.method).toBe('POST');
    expect(opts.headers['Content-Type']).toBe('application/json');
    const parsed = JSON.parse(opts.body);
    expect(parsed.address_text).toBe('x');
    expect(parsed.label).toBe('Дом');
    expect(parsed.apartment).toBe('5');
    expect(parsed).not.toHaveProperty('text');
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

describe('setDefaultAddress', () => {
  it('PATCHes /{id} with is_default=true', async () => {
    (authenticatedFetch as Mock).mockResolvedValue(
      asOk(addr({ is_default: true })),
    );

    await setDefaultAddress('a1');

    const [url, opts] = (authenticatedFetch as Mock).mock.calls[0];
    expect(url).toBe('/api/v1/profile/addresses/a1');
    expect(opts.method).toBe('PATCH');
    expect(opts.headers['Content-Type']).toBe('application/json');
    expect(JSON.parse(opts.body)).toEqual({ is_default: true });
  });
});

describe('errors', () => {
  it('throws AddressApiError with status and detail on 409', async () => {
    (authenticatedFetch as Mock).mockResolvedValue(
      asError(409, { detail: 'Адрес вне зоны доставки (максимум 10 км).' }),
    );

    try {
      await createAddress({
        label: 'Дом',
        address_text: 'x',
        lat: 1,
        lon: 2,
        apartment: null,
        entrance: null,
        floor: null,
        comment: null,
      });
      throw new Error('expected throw');
    } catch (e) {
      expect(e).toBeInstanceOf(AddressApiError);
      const err = e as AddressApiError;
      expect(err.status).toBe(409);
      expect(err.detail).toContain('вне зоны');
    }
  });

  it('does not expose FastAPI validation-error objects as renderable detail', async () => {
    (authenticatedFetch as Mock).mockResolvedValue(
      asError(422, {
        detail: [
          {
            type: 'float_type',
            loc: ['body', 'lat'],
            msg: 'Input should be a valid number',
            input: null,
          },
        ],
      }),
    );

    try {
      await createAddress({
        label: 'Дом',
        address_text: 'ул. Пушкина 1',
        lat: null,
        lon: null,
        apartment: null,
        entrance: null,
        floor: null,
        comment: null,
      });
      throw new Error('expected throw');
    } catch (e) {
      expect(e).toBeInstanceOf(AddressApiError);
      const err = e as AddressApiError;
      expect(err.status).toBe(422);
      expect(err.detail).toBeUndefined();
    }
  });
});
