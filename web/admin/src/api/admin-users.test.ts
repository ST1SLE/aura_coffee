import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  listUsers,
  getUser,
  blockUser,
  unblockUser,
  adjustLoyalty,
  parseAdjustError,
  ApiError,
} from './admin-users';
import { clearAuthTokens, setAccessToken } from './client';

describe('api/admin-users', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    localStorage.clear();
    clearAuthTokens();
    setAccessToken('test');
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

  function mockError(body: unknown, status: number) {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify(body), {
        status,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
  }

  it('listUsers — status/search/page/per_page encoded', async () => {
    mockJson({ items: [], page: 2, per_page: 50, total: 0 });
    await listUsers({ status: 'active', search: 'ivan', page: 2, perPage: 50 });
    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toContain('/api/v1/admin/users');
    expect(url).toContain('status=active');
    expect(url).toContain('search=ivan');
    expect(url).toContain('page=2');
    expect(url).toContain('per_page=50');
  });

  it('listUsers — status=all omits param', async () => {
    mockJson({ items: [], page: 1, per_page: 20, total: 0 });
    await listUsers({ status: 'all', page: 1, perPage: 20 });
    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toContain('/api/v1/admin/users');
    expect(url).not.toContain('status=');
    expect(url).toContain('page=1');
    expect(url).toContain('per_page=20');
  });

  it('getUser — GET by id', async () => {
    mockJson({ id: 'abc', status: 'active' });
    await getUser('abc');
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain('/api/v1/admin/users/abc');
    expect(init.method ?? 'GET').toBe('GET');
  });

  it('blockUser — POST /block with no body', async () => {
    mockJson({ user_id: 'abc', status: 'blocked', cancelled_orders_count: 0 });
    await blockUser('abc');
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain('/api/v1/admin/users/abc/block');
    expect(init.method).toBe('POST');
    expect(init.body).toBeUndefined();
  });

  it('unblockUser — POST /unblock', async () => {
    mockJson({ user_id: 'abc', status: 'active' });
    await unblockUser('abc');
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain('/api/v1/admin/users/abc/unblock');
    expect(init.method).toBe('POST');
  });

  it('adjustLoyalty — POST /loyalty/adjust with JSON body', async () => {
    mockJson({ transaction_id: 't-1', new_balance: 50, delta: -50 });
    await adjustLoyalty('abc', { delta: -50, reason: 'test' });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain('/api/v1/admin/users/abc/loyalty/adjust');
    expect(init.method).toBe('POST');
    const headers = init.headers as Record<string, string>;
    expect(headers['Content-Type']).toBe('application/json');
    const body = JSON.parse(init.body as string);
    expect(body).toEqual({ delta: -50, reason: 'test' });
  });

  it('adjustLoyalty — 422 rejects with ApiError preserving status and body', async () => {
    mockError({ detail: 'insufficient_balance' }, 422);
    await expect(
      adjustLoyalty('abc', { delta: -9999, reason: 'bust' }),
    ).rejects.toMatchObject({
      name: 'ApiError',
      status: 422,
      body: { detail: 'insufficient_balance' },
    });
  });

  it('parseAdjustError — recognizes insufficient_balance in detail string', () => {
    const err = new ApiError(422, { detail: 'insufficient_balance' }, 'HTTP 422');
    expect(parseAdjustError(err)).toBe('insufficient_balance');
  });

  it('parseAdjustError — recognizes insufficient_balance in code field', () => {
    const err = new ApiError(422, { code: 'insufficient_balance' }, 'HTTP 422');
    expect(parseAdjustError(err)).toBe('insufficient_balance');
  });

  it('parseAdjustError — returns null for non-matching 422', () => {
    const err = new ApiError(422, { detail: [{ loc: ['body', 'delta'], msg: 'int_parsing' }] }, 'HTTP 422');
    expect(parseAdjustError(err)).toBeNull();
  });

  it('parseAdjustError — returns null for non-ApiError', () => {
    expect(parseAdjustError(new Error('boom'))).toBeNull();
  });
});
