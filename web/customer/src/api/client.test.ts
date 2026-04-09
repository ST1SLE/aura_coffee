import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import {
  authenticatedFetch,
  registerAuthFailureHandler,
} from './client';
import * as tokenModule from '@/auth/token';
import * as authApi from './auth';

vi.mock('@/auth/token', () => ({
  getAccessToken: vi.fn(),
  getRefreshToken: vi.fn(),
  setAccessToken: vi.fn(),
  setRefreshToken: vi.fn(),
  clearAllTokens: vi.fn(),
}));

vi.mock('./auth', () => ({
  refreshTokens: vi.fn(),
}));

const mockFetch = vi.fn();
vi.stubGlobal('fetch', mockFetch);

function jsonResponse(status: number, body: unknown = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  registerAuthFailureHandler(null as unknown as () => void);
});

describe('authenticatedFetch', () => {
  it('attaches Authorization header when access token exists', async () => {
    (tokenModule.getAccessToken as Mock).mockReturnValue('tok-123');
    mockFetch.mockResolvedValue(jsonResponse(200));

    await authenticatedFetch('/api/v1/profile');

    const headers = mockFetch.mock.calls[0][1].headers as Headers;
    expect(headers.get('Authorization')).toBe('Bearer tok-123');
  });

  it('sends request without auth header when no token', async () => {
    (tokenModule.getAccessToken as Mock).mockReturnValue(null);
    mockFetch.mockResolvedValue(jsonResponse(200));

    await authenticatedFetch('/api/v1/menu');

    const headers = mockFetch.mock.calls[0][1].headers as Headers;
    expect(headers.has('Authorization')).toBe(false);
  });

  it('preserves caller-provided headers', async () => {
    (tokenModule.getAccessToken as Mock).mockReturnValue('tok-123');
    mockFetch.mockResolvedValue(jsonResponse(200));

    await authenticatedFetch('/api/v1/profile', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
    });

    const headers = mockFetch.mock.calls[0][1].headers as Headers;
    expect(headers.get('Content-Type')).toBe('application/json');
    expect(headers.get('Authorization')).toBe('Bearer tok-123');
  });

  it('passes through non-401 errors without interception', async () => {
    (tokenModule.getAccessToken as Mock).mockReturnValue('tok-123');
    mockFetch.mockResolvedValue(jsonResponse(403));

    const res = await authenticatedFetch('/api/v1/admin');

    expect(res.status).toBe(403);
    expect(mockFetch).toHaveBeenCalledTimes(1);
    expect(authApi.refreshTokens).not.toHaveBeenCalled();
  });

  it('refreshes and retries on 401', async () => {
    (tokenModule.getAccessToken as Mock).mockReturnValue('expired-tok');
    (tokenModule.getRefreshToken as Mock).mockReturnValue('rt-valid');
    (authApi.refreshTokens as Mock).mockResolvedValue({
      accessToken: 'new-access',
      refreshToken: 'new-refresh',
    });

    mockFetch
      .mockResolvedValueOnce(jsonResponse(401))
      .mockResolvedValueOnce(jsonResponse(200, { name: 'ok' }));

    const res = await authenticatedFetch('/api/v1/profile');

    expect(res.status).toBe(200);
    expect(authApi.refreshTokens).toHaveBeenCalledWith('rt-valid');
    expect(tokenModule.setAccessToken).toHaveBeenCalledWith('new-access');
    expect(tokenModule.setRefreshToken).toHaveBeenCalledWith('new-refresh');

    const retryHeaders = mockFetch.mock.calls[1][1].headers as Headers;
    expect(retryHeaders.get('Authorization')).toBe('Bearer new-access');
  });

  it('calls failure handler and returns 401 when no refresh token', async () => {
    const failHandler = vi.fn();
    registerAuthFailureHandler(failHandler);

    (tokenModule.getAccessToken as Mock).mockReturnValue('expired-tok');
    (tokenModule.getRefreshToken as Mock).mockReturnValue(null);
    mockFetch.mockResolvedValue(jsonResponse(401));

    const res = await authenticatedFetch('/api/v1/profile');

    expect(res.status).toBe(401);
    expect(tokenModule.clearAllTokens).toHaveBeenCalled();
    expect(failHandler).toHaveBeenCalled();
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it('calls failure handler when refresh fails', async () => {
    const failHandler = vi.fn();
    registerAuthFailureHandler(failHandler);

    (tokenModule.getAccessToken as Mock).mockReturnValue('expired-tok');
    (tokenModule.getRefreshToken as Mock).mockReturnValue('rt-expired');
    (authApi.refreshTokens as Mock).mockRejectedValue(new Error('invalid'));
    mockFetch.mockResolvedValue(jsonResponse(401));

    const res = await authenticatedFetch('/api/v1/profile');

    expect(res.status).toBe(401);
    expect(tokenModule.clearAllTokens).toHaveBeenCalled();
    expect(failHandler).toHaveBeenCalled();
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it('clears tokens even without registered handler', async () => {
    (tokenModule.getAccessToken as Mock).mockReturnValue('expired-tok');
    (tokenModule.getRefreshToken as Mock).mockReturnValue(null);
    mockFetch.mockResolvedValue(jsonResponse(401));

    await authenticatedFetch('/api/v1/profile');

    expect(tokenModule.clearAllTokens).toHaveBeenCalled();
  });

  it('deduplicates concurrent refresh calls', async () => {
    (tokenModule.getAccessToken as Mock).mockReturnValue('expired-tok');
    (tokenModule.getRefreshToken as Mock).mockReturnValue('rt-valid');

    let resolveRefresh!: (v: unknown) => void;
    (authApi.refreshTokens as Mock).mockReturnValue(
      new Promise((r) => { resolveRefresh = r; }),
    );

    mockFetch.mockResolvedValue(jsonResponse(401));

    const p1 = authenticatedFetch('/api/v1/profile');
    const p2 = authenticatedFetch('/api/v1/orders');

    mockFetch.mockResolvedValue(jsonResponse(200));
    resolveRefresh({ accessToken: 'new-tok', refreshToken: 'new-rt' });

    const [r1, r2] = await Promise.all([p1, p2]);

    expect(r1.status).toBe(200);
    expect(r2.status).toBe(200);
    expect(authApi.refreshTokens).toHaveBeenCalledTimes(1);
  });
});
