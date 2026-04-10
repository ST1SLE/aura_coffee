import { describe, it, test, expect, vi, beforeEach, type Mock } from 'vitest';
import { expectTypeOf } from 'vitest';

vi.mock('./client', () => ({
  apiRequest: vi.fn(),
  authenticatedFetch: vi.fn(),
}));

import { apiRequest } from './client';
import { fetchPublicMenu } from './menu';
import type { PublicMenuResponse, PublicCategory } from './menuTypes';

beforeEach(() => {
  vi.clearAllMocks();
});

// Задача 1.1: типы экспортируются с правильной структурой
test('menuTypes exports PublicMenuResponse with categories: PublicCategory[]', () => {
  expectTypeOf<PublicMenuResponse['categories']>().toEqualTypeOf<PublicCategory[]>();
});

describe('fetchPublicMenu', () => {
  // Задача 2.1
  it('GETs /api/v1/menu with Accept-Language header', async () => {
    const mockMenu: PublicMenuResponse = { categories: [] };
    (apiRequest as Mock).mockResolvedValue(mockMenu);

    const result = await fetchPublicMenu('en');

    expect(apiRequest).toHaveBeenCalledOnce();
    const [url, opts] = (apiRequest as Mock).mock.calls[0];
    expect(url).toBe('/api/v1/menu');
    expect((opts as RequestInit | undefined)?.headers).toMatchObject({ 'Accept-Language': 'en' });
    expect(result).toBe(mockMenu);
  });

  // Задача 2.2
  it('sends Accept-Language: ru', async () => {
    (apiRequest as Mock).mockResolvedValue({ categories: [] });

    await fetchPublicMenu('ru');

    const [, opts] = (apiRequest as Mock).mock.calls[0];
    expect((opts as RequestInit | undefined)?.headers).toMatchObject({ 'Accept-Language': 'ru' });
  });

  it('propagates rejection from apiRequest', async () => {
    (apiRequest as Mock).mockRejectedValue(new Error('HTTP 500: /api/v1/menu'));

    await expect(fetchPublicMenu('ru')).rejects.toThrow('500');
  });
});
