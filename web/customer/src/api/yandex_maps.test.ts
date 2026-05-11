import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';

vi.mock('./client', () => ({
  authenticatedFetch: vi.fn(),
  apiRequest: vi.fn(),
}));

import { authenticatedFetch } from './client';
import {
  suggest,
  geocode,
  MapsUnavailableError,
  type SuggestResult,
} from './yandex_maps';

const asOk = (body: unknown): Response =>
  ({
    ok: true,
    status: 200,
    json: async () => body,
  }) as unknown as Response;

const asStatus = (status: number): Response =>
  ({
    ok: false,
    status,
    json: async () => ({}),
  }) as unknown as Response;

beforeEach(() => {
  vi.clearAllMocks();
});

describe('suggest', () => {
  it('posts text and lang in the body', async () => {
    (authenticatedFetch as Mock).mockResolvedValue(asOk({ items: [] }));

    await suggest('Нев', 'ru_RU');

    expect(authenticatedFetch).toHaveBeenCalledOnce();
    const [url, init] = (authenticatedFetch as Mock).mock.calls[0];
    expect(url).toBe('/api/v1/maps/suggest');
    expect(init).toMatchObject({
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    expect(JSON.parse(init.body)).toEqual({ text: 'Нев', lang: 'ru_RU' });
  });

  it('returns items from bare-array server response', async () => {
    const items: SuggestResult[] = [
      { text: 'Невский пр., 1', lat: 59.93, lon: 30.36 },
      { text: 'Невский пр., 2', lat: 59.93, lon: 30.37 },
    ];
    (authenticatedFetch as Mock).mockResolvedValue(asOk(items));

    const result = await suggest('Нев', 'ru_RU');

    expect(result).toEqual(items);
  });

  it('tolerates legacy {items} server response', async () => {
    const items: SuggestResult[] = [
      { text: 'Невский пр., 1', lat: 59.93, lon: 30.36 },
    ];
    (authenticatedFetch as Mock).mockResolvedValue(asOk({ items }));

    await expect(suggest('Нев', 'ru_RU')).resolves.toEqual(items);
  });

  it('signals MapsUnavailable on 503', async () => {
    (authenticatedFetch as Mock).mockResolvedValue(asStatus(503));

    await expect(suggest('Нев', 'ru_RU')).rejects.toBeInstanceOf(
      MapsUnavailableError,
    );
  });

  it('signals MapsUnavailable on 5xx', async () => {
    (authenticatedFetch as Mock).mockResolvedValue(asStatus(500));

    await expect(suggest('Нев', 'ru_RU')).rejects.toBeInstanceOf(
      MapsUnavailableError,
    );
  });

  it('signals MapsUnavailable on network error', async () => {
    (authenticatedFetch as Mock).mockRejectedValue(
      new TypeError('Failed to fetch'),
    );

    await expect(suggest('Нев', 'ru_RU')).rejects.toBeInstanceOf(
      MapsUnavailableError,
    );
  });

  it('accepts en_US lang', async () => {
    (authenticatedFetch as Mock).mockResolvedValue(asOk({ items: [] }));

    await suggest('Nevs', 'en_US');

    const [, init] = (authenticatedFetch as Mock).mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({ text: 'Nevs', lang: 'en_US' });
  });
});

describe('geocode', () => {
  it('posts text with default lang=ru_RU', async () => {
    (authenticatedFetch as Mock).mockResolvedValue(
      asOk({ canonical_text: 'x', lat: 1, lon: 2, precision: 'exact' }),
    );

    await geocode('Невский 1');

    const [url, init] = (authenticatedFetch as Mock).mock.calls[0];
    expect(url).toBe('/api/v1/maps/geocode');
    expect(init).toMatchObject({
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    expect(JSON.parse(init.body)).toEqual({
      text: 'Невский 1',
      lang: 'ru_RU',
    });
  });

  it('passes explicit lang when provided', async () => {
    (authenticatedFetch as Mock).mockResolvedValue(
      asOk({ canonical_text: 'x', lat: 1, lon: 2, precision: 'exact' }),
    );

    await geocode('Nevskiy 1', 'en_US');

    const [, init] = (authenticatedFetch as Mock).mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({
      text: 'Nevskiy 1',
      lang: 'en_US',
    });
  });

  it('returns canonical geocode payload from server', async () => {
    const body = {
      canonical_text: 'Россия, Москва, Невский 1',
      lat: 55.75,
      lon: 37.61,
      precision: 'exact',
    };
    (authenticatedFetch as Mock).mockResolvedValue(asOk(body));

    await expect(geocode('Невский 1')).resolves.toEqual(body);
  });

  it('signals MapsUnavailable on geocode 5xx', async () => {
    (authenticatedFetch as Mock).mockResolvedValue(asStatus(500));

    await expect(geocode('Невский 1')).rejects.toBeInstanceOf(
      MapsUnavailableError,
    );
  });
});
