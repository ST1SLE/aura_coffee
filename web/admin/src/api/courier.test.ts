import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ApiError, clearAuthTokens, setAccessToken } from '@/api/client';
import {
  listAvailable,
  takeAssignment,
  listMine,
  pickupAssignment,
  deliverAssignment,
} from '@/api/courier';

function okResponse(body: unknown = [], status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function errResponse(status: number, body: unknown = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('courier API client', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    vi.stubGlobal('location', {
      pathname: '/admin/courier',
      search: '',
      assign: vi.fn(),
    });
    localStorage.clear();
    clearAuthTokens();
    setAccessToken('tok');
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('listAvailable: GET /api/v1/courier/assignments/available с bearer', async () => {
    fetchMock.mockResolvedValue(okResponse([]));
    await listAvailable();

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/courier/assignments/available');
    expect((init.headers as Record<string, string>)['Authorization']).toBe(
      'Bearer tok',
    );
  });

  it('takeAssignment: POST /api/v1/courier/assignments/{id}/take', async () => {
    fetchMock.mockResolvedValue(okResponse({ id: 'aid-1' }));
    await takeAssignment('aid-1');

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/courier/assignments/aid-1/take');
    expect(init.method).toBe('POST');
  });

  it('takeAssignment 409: бросает ApiError(409)', async () => {
    fetchMock.mockResolvedValue(errResponse(409, { detail: 'already_taken' }));
    const err = await takeAssignment('aid-1').catch((e) => e);

    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(409);
    expect(err.body).toEqual({ detail: 'already_taken' });
  });

  it('listMine: GET /api/v1/courier/assignments/mine', async () => {
    fetchMock.mockResolvedValue(okResponse([]));
    await listMine();

    const [url] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/courier/assignments/mine');
  });

  it('pickupAssignment: POST /api/v1/courier/assignments/{id}/pickup', async () => {
    fetchMock.mockResolvedValue(okResponse({ id: 'aid-2', status: 'PICKED_UP' }));
    await pickupAssignment('aid-2');

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/courier/assignments/aid-2/pickup');
    expect(init.method).toBe('POST');
  });

  it('deliverAssignment: POST /api/v1/courier/assignments/{id}/deliver', async () => {
    fetchMock.mockResolvedValue(okResponse({ id: 'aid-3', status: 'DELIVERED' }));
    await deliverAssignment('aid-3');

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/courier/assignments/aid-3/deliver');
    expect(init.method).toBe('POST');
  });

  it('500 на любом endpoint: бросает ApiError', async () => {
    fetchMock.mockResolvedValue(errResponse(500));
    const err = await listAvailable().catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(500);
  });
});
