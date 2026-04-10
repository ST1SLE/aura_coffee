import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  listCategories,
  createItem,
  setItemAvailability,
  deleteCategory,
  ApiError,
} from './menu';

describe('api/menu', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    localStorage.clear();
    // Токен для прохождения authenticatedFetch без авторизации
    localStorage.setItem('accessToken', 'test');
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function mockJson(body: unknown, status = 200) {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify(body), {
        status,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
  }

  it('listCategories — GET /api/v1/admin/menu/categories', async () => {
    const data = [{ id: 1, name: 'Кофе' }];
    mockJson(data);

    const result = await listCategories();

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toContain('/api/v1/admin/menu/categories');
    expect(result).toEqual(data);
  });

  it('createItem — POST /api/v1/admin/menu/items', async () => {
    const created = { id: 10, name: 'Латте', price_kopecks: 35000 };
    mockJson(created, 201);

    const result = await createItem({
      category_id: 1,
      name: 'Латте',
      price_kopecks: 35000,
    });

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain('/api/v1/admin/menu/items');
    expect(init.method).toBe('POST');
    expect(result).toMatchObject({ id: 10, name: 'Латте' });
  });

  it('setItemAvailability — PATCH с телом { available: false }', async () => {
    const updated = { id: 5, availability: 'STOP_LIST' };
    mockJson(updated);

    await setItemAvailability(5, false);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain('/items/5/availability');
    expect(init.method).toBe('PATCH');
    expect(JSON.parse(init.body as string)).toEqual({ available: false });
  });

  it('deleteCategory 409 — бросает ApiError(409)', async () => {
    mockJson({ detail: 'referenced' }, 409);

    const err = await deleteCategory(1).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(409);
  });
});
