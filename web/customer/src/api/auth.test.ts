import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import * as tokenModule from '@/auth/token';

vi.mock('@/auth/token', () => ({
  getAccessToken: vi.fn(),
  setAccessToken: vi.fn(),
  setRefreshToken: vi.fn(),
  clearAccessToken: vi.fn(),
  clearRefreshToken: vi.fn(),
  clearAllTokens: vi.fn(),
}));

const mockFetch = vi.fn();
vi.stubGlobal('fetch', mockFetch);

function jsonResponse(status: number, body: Record<string, unknown>): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as Response;
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.resetModules();
});

describe('logout', () => {
  it('uses the HttpOnly refresh cookie and Authorization header', async () => {
    (tokenModule.getAccessToken as Mock).mockReturnValue('access-tok');
    mockFetch.mockResolvedValue(new Response(null, { status: 200 }));

    const { logout } = await import('./auth');
    await logout();

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toBe('/api/v1/auth/logout');
    expect(opts.method).toBe('POST');
    expect(opts.credentials).toBe('include');
    expect(opts.headers['Authorization']).toBe('Bearer access-tok');

    const body = JSON.parse(opts.body);
    expect(body).toEqual({});
  });

  it('omits Authorization header when no access token is present', async () => {
    (tokenModule.getAccessToken as Mock).mockReturnValue(null);
    mockFetch.mockResolvedValue(new Response(null, { status: 200 }));

    const { logout } = await import('./auth');
    await logout();

    const [, opts] = mockFetch.mock.calls[0];
    expect(opts.headers['Authorization']).toBeUndefined();
    expect(opts.credentials).toBe('include');
  });

  it('ignores network errors silently', async () => {
    (tokenModule.getAccessToken as Mock).mockReturnValue('access-tok');
    mockFetch.mockRejectedValue(new TypeError('Failed to fetch'));

    const { logout } = await import('./auth');
    await expect(logout()).resolves.toBeUndefined();
  });

  it('refreshes once and retries logout when access token is expired', async () => {
    (tokenModule.getAccessToken as Mock).mockReturnValue('expired-access');
    mockFetch
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(
        jsonResponse(200, {
          access_token: 'fresh-access',
          refresh_token: 'legacy-response-field',
        }),
      )
      .mockResolvedValueOnce(new Response(null, { status: 200 }));

    const { logout } = await import('./auth');
    await logout();

    expect(mockFetch).toHaveBeenCalledTimes(3);
    expect(mockFetch.mock.calls[0][0]).toBe('/api/v1/auth/logout');
    expect(mockFetch.mock.calls[1][0]).toBe('/api/v1/auth/refresh');
    expect(mockFetch.mock.calls[2][0]).toBe('/api/v1/auth/logout');
    expect(tokenModule.setAccessToken).toHaveBeenCalledWith('fresh-access');
    expect(
      mockFetch.mock.calls[2][1].headers['Authorization'],
    ).toBe('Bearer fresh-access');
  });
});

describe('refreshTokens', () => {
  it('refreshes with credentials and no readable refresh token by default', async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse(200, {
        access_token: 'access-new',
        refresh_token: 'legacy-response-field',
      }),
    );

    const { refreshTokens } = await import('./auth');
    const tokens = await refreshTokens();

    expect(tokens.accessToken).toBe('access-new');
    const [, opts] = mockFetch.mock.calls[0];
    expect(opts.credentials).toBe('include');
    expect(JSON.parse(opts.body)).toEqual({});
  });

  it('keeps body fallback for non-browser callers', async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse(200, {
        access_token: 'access-new',
        refresh_token: 'legacy-response-field',
      }),
    );

    const { refreshTokens } = await import('./auth');
    await refreshTokens('legacy-refresh');

    const [, opts] = mockFetch.mock.calls[0];
    expect(JSON.parse(opts.body)).toEqual({ refresh_token: 'legacy-refresh' });
  });
});

describe('verifyCode — HTTP error handling', () => {
  it('throws CODE_NOT_DELIVERED on HTTP 409', async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse(409, { detail: 'OTP not yet delivered' }),
    );

    const { verifyCode } = await import('./auth');

    await expect(verifyCode('+79991234567', '123456')).rejects.toThrow(
      expect.objectContaining({
        code: 'CODE_NOT_DELIVERED',
        message: 'OTP not yet delivered',
      }),
    );
  });

  it('throws CODE_EXPIRED on HTTP 410', async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse(410, { detail: 'OTP expired' }),
    );

    const { verifyCode } = await import('./auth');

    await expect(verifyCode('+79991234567', '123456')).rejects.toThrow(
      expect.objectContaining({ code: 'CODE_EXPIRED' }),
    );
  });

  it('throws INVALID_CODE on HTTP 401 with "Wrong code"', async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse(401, { detail: 'Wrong code. 4 attempts remaining' }),
    );

    const { verifyCode } = await import('./auth');

    await expect(verifyCode('+79991234567', '123456')).rejects.toThrow(
      expect.objectContaining({ code: 'INVALID_CODE' }),
    );
  });

  it('throws RATE_LIMITED on HTTP 429', async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse(429, { detail: 'Too many requests', retry_after: 58 }),
    );

    const { verifyCode } = await import('./auth');

    await expect(verifyCode('+79991234567', '123456')).rejects.toThrow(
      expect.objectContaining({ code: 'RATE_LIMITED', retryAfter: 58 }),
    );
  });

  it('throws UNKNOWN_ERROR on unexpected status code', async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse(500, { detail: 'Internal server error' }),
    );

    const { verifyCode } = await import('./auth');

    await expect(verifyCode('+79991234567', '123456')).rejects.toThrow(
      expect.objectContaining({ code: 'UNKNOWN_ERROR' }),
    );
  });
});
