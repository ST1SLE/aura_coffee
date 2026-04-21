import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { getAdminStats, ApiError } from './admin-stats';
import type { AdminStatsResponse } from './admin-stats';

describe('api/admin-stats', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    localStorage.clear();
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

  const sampleResponse: AdminStatsResponse = {
    range: 'month',
    range_start: '2026-03-21T00:00:00Z',
    range_end: '2026-04-20T00:00:00Z',
    revenue_kopecks: 1234500,
    orders_count: 42,
    popular_items: [
      { name_ru: 'Латте', name_en: 'Latte', quantity: 28 },
    ],
  };

  it('getAdminStats — GET /api/v1/admin/stats?range=month', async () => {
    mockJson(sampleResponse);
    const res = await getAdminStats('month');
    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toContain('/api/v1/admin/stats');
    expect(url).toContain('range=month');
    expect(res).toEqual(sampleResponse);
  });

  it('getAdminStats — передаёт range=today', async () => {
    mockJson(sampleResponse);
    await getAdminStats('today');
    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toContain('range=today');
  });

  it('getAdminStats — передаёт range=week', async () => {
    mockJson(sampleResponse);
    await getAdminStats('week');
    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toContain('range=week');
  });

  it('getAdminStats — добавляет Authorization header', async () => {
    mockJson(sampleResponse);
    await getAdminStats('month');
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBe('Bearer test');
  });

  it('getAdminStats — пробрасывает 403 как ApiError', async () => {
    mockJson({ detail: 'forbidden' }, 403);
    await expect(getAdminStats('month')).rejects.toBeInstanceOf(ApiError);
    try {
      await getAdminStats('month');
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as ApiError;
      expect(apiErr.status).toBe(403);
      expect(apiErr.body).toEqual({ detail: 'forbidden' });
    }
  });

  it('getAdminStats — пробрасывает 500 как ApiError', async () => {
    mockJson({ detail: 'internal error' }, 500);
    await expect(getAdminStats('today')).rejects.toBeInstanceOf(ApiError);
  });
});
