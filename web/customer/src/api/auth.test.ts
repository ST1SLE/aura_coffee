import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import * as tokenModule from '@/auth/token';

vi.mock('@/auth/token', () => ({
  getAccessToken: vi.fn(),
  getRefreshToken: vi.fn(),
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
  it('sends refresh_token in request body', async () => {
    (tokenModule.getAccessToken as Mock).mockReturnValue('access-tok');
    (tokenModule.getRefreshToken as Mock).mockReturnValue('refresh-tok');
    mockFetch.mockResolvedValue(new Response(null, { status: 200 }));

    const { logout } = await import('./auth');
    await logout();

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toBe('/api/v1/auth/logout');
    expect(opts.method).toBe('POST');
    expect(opts.headers['Authorization']).toBe('Bearer access-tok');

    const body = JSON.parse(opts.body);
    expect(body.refresh_token).toBe('refresh-tok');
  });

  it('sends null refresh_token when none stored', async () => {
    (tokenModule.getAccessToken as Mock).mockReturnValue('access-tok');
    (tokenModule.getRefreshToken as Mock).mockReturnValue(null);
    mockFetch.mockResolvedValue(new Response(null, { status: 200 }));

    const { logout } = await import('./auth');
    await logout();

    const body = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(body.refresh_token).toBeNull();
  });

  it('ignores network errors silently', async () => {
    (tokenModule.getAccessToken as Mock).mockReturnValue('access-tok');
    (tokenModule.getRefreshToken as Mock).mockReturnValue('refresh-tok');
    mockFetch.mockRejectedValue(new TypeError('Failed to fetch'));

    const { logout } = await import('./auth');
    await expect(logout()).resolves.toBeUndefined();
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
