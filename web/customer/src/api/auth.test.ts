import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AuthError } from './types';

// Мокаем fetch для изолированных тестов API клиента
const mockFetch = vi.fn();
vi.stubGlobal('fetch', mockFetch);

// Мокаем getAccessToken (используется в logout)
vi.mock('@/auth/token', () => ({
  getAccessToken: () => null,
}));

function jsonResponse(status: number, body: Record<string, unknown>): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as Response;
}

describe('verifyCode — HTTP 409 handling', () => {
  beforeEach(() => {
    vi.resetModules();
    mockFetch.mockReset();
  });

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
