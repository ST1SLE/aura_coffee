import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';

vi.mock('./client', () => ({
  apiRequest: vi.fn(),
  authenticatedFetch: vi.fn(),
}));

import { apiRequest } from './client';
import { listCategories, listMenuItems, getMenuItem } from './menu';

beforeEach(() => {
  vi.clearAllMocks();
});

describe('listCategories', () => {
  it('calls GET /api/v1/menu/categories', async () => {
    (apiRequest as Mock).mockResolvedValue([]);

    await listCategories();

    expect(apiRequest).toHaveBeenCalledOnce();
    const [url] = (apiRequest as Mock).mock.calls[0];
    expect(url).toBe('/api/v1/menu/categories');
  });
});

describe('listMenuItems', () => {
  it('calls /api/v1/menu/items without filter', async () => {
    (apiRequest as Mock).mockResolvedValue([]);

    await listMenuItems();

    const [url] = (apiRequest as Mock).mock.calls[0];
    expect(url).toBe('/api/v1/menu/items');
  });

  it('appends category_id query param when provided', async () => {
    (apiRequest as Mock).mockResolvedValue([]);

    await listMenuItems({ categoryId: 7 });

    const [url] = (apiRequest as Mock).mock.calls[0];
    expect(url).toBe('/api/v1/menu/items?category_id=7');
  });
});

describe('getMenuItem', () => {
  it('calls /api/v1/menu/items/:id', async () => {
    (apiRequest as Mock).mockResolvedValue({ id: 3 });

    await getMenuItem(3);

    const [url] = (apiRequest as Mock).mock.calls[0];
    expect(url).toBe('/api/v1/menu/items/3');
  });
});

describe('error handling', () => {
  it('propagates rejection from apiRequest', async () => {
    (apiRequest as Mock).mockRejectedValue(new Error('HTTP 500: /api/v1/menu/categories'));

    await expect(listCategories()).rejects.toThrow('500');
  });
});
