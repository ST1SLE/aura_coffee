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
