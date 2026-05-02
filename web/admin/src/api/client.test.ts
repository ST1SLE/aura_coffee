import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  authenticatedFetch,
  ApiError,
  getAccessToken,
  getRefreshToken,
  setAccessToken,
  setRefreshToken,
  clearAccessToken,
  clearAuthTokens,
  logout,
  staffLogin,
} from './client';

// Мок import.meta.env — Vitest подставляет его через define в vite.config
// BASE_URL будет пустой строкой (default), path передаётся как есть

describe('authenticatedFetch', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    vi.stubGlobal('location', {
      pathname: '/admin/menu',
      search: '',
      assign: vi.fn(),
    });
    localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function okResponse(body: unknown = {}, status = 200) {
    const json = JSON.stringify(body);
    return new Response(json, {
      status,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  it('добавляет Authorization header, если токен есть', async () => {
    localStorage.setItem('accessToken', 'test-token');
    fetchMock.mockResolvedValue(okResponse());

    await authenticatedFetch('/test');

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect((init.headers as Record<string, string>)['Authorization']).toBe(
      'Bearer test-token',
    );
  });

  it('не добавляет Authorization header, если токен отсутствует', async () => {
    fetchMock.mockResolvedValue(okResponse());

    await authenticatedFetch('/test');

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(
      (init.headers as Record<string, string>)['Authorization'],
    ).toBeUndefined();
  });

  it('сохраняет caller-supplied заголовки (Content-Type)', async () => {
    localStorage.setItem('accessToken', 'tok');
    fetchMock.mockResolvedValue(okResponse());

    await authenticatedFetch('/test', {
      headers: { 'Content-Type': 'application/json' },
    });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Record<string, string>;
    expect(headers['Content-Type']).toBe('application/json');
    expect(headers['Authorization']).toBe('Bearer tok');
  });

  it('бросает ApiError с числовым status и телом при non-2xx', async () => {
    const errBody = { detail: 'Not found' };
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify(errBody), {
        status: 404,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    const err = await authenticatedFetch('/missing').catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(404);
    expect(err.body).toEqual(errBody);
  });

  // --- 2.2a: 401 на защищённом маршруте — редирект + очистка токена + бросает ApiError ---
  it('401 на /api/v1/admin/menu/categories: вызывает assign, очищает токен, бросает ApiError', async () => {
    localStorage.setItem('accessToken', 'expired-token');
    vi.stubGlobal('location', {
      pathname: '/admin/menu',
      search: '',
      assign: vi.fn(),
    });
    fetchMock.mockResolvedValue(
      new Response('{}', {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    const err = await authenticatedFetch('/api/v1/admin/menu/categories').catch(
      (e) => e,
    );

    expect(window.location.assign).toHaveBeenCalledWith(
      '/admin/login?returnUrl=%2Fmenu',
    );
    expect(localStorage.getItem('accessToken')).toBeNull();
    expect(localStorage.getItem('refreshToken')).toBeNull();
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(401);
  });

  it('401 на защищённом маршруте: refreshes from cookie, retries once, stores access token', async () => {
    localStorage.setItem('accessToken', 'expired-token');
    localStorage.setItem('staffRole', 'barista');
    const assignMock = vi.fn();
    vi.stubGlobal('location', {
      pathname: '/admin/orders',
      search: '',
      assign: assignMock,
    });
    fetchMock
      .mockResolvedValueOnce(
        new Response('{}', {
          status: 401,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
      .mockResolvedValueOnce(
        okResponse({
          access_token: 'access-new',
          refresh_token: 'refresh-new',
          role: 'admin',
        }),
      )
      .mockResolvedValueOnce(okResponse({ ok: true }));

    const response = await authenticatedFetch('/api/v1/admin/orders');

    expect(response.ok).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    const [refreshUrl, refreshInit] = fetchMock.mock.calls[1] as [
      string,
      RequestInit,
    ];
    expect(refreshUrl).toBe('/api/v1/staff/auth/refresh');
    expect(refreshInit.credentials).toBe('include');
    expect(JSON.parse(refreshInit.body as string)).toEqual({});
    const [, retryInit] = fetchMock.mock.calls[2] as [string, RequestInit];
    expect((retryInit.headers as Record<string, string>)['Authorization']).toBe(
      'Bearer access-new',
    );
    expect(localStorage.getItem('accessToken')).toBe('access-new');
    expect(localStorage.getItem('refreshToken')).toBeNull();
    expect(localStorage.getItem('staffRole')).toBe('admin');
    expect(assignMock).not.toHaveBeenCalled();
  });

  it('401 после refresh retry: очищает обе пары токенов и редиректит', async () => {
    localStorage.setItem('accessToken', 'expired-token');
    localStorage.setItem('staffRole', 'admin');
    const assignMock = vi.fn();
    vi.stubGlobal('location', {
      pathname: '/admin/orders',
      search: '',
      assign: assignMock,
    });
    fetchMock
      .mockResolvedValueOnce(
        new Response('{}', {
          status: 401,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
      .mockResolvedValueOnce(
        okResponse({
          access_token: 'access-new',
          refresh_token: 'refresh-new',
          role: 'admin',
        }),
      )
      .mockResolvedValueOnce(
        new Response('{}', {
          status: 401,
          headers: { 'Content-Type': 'application/json' },
        }),
      );

    const err = await authenticatedFetch('/api/v1/admin/orders').catch(
      (e) => e,
    );

    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(401);
    expect(localStorage.getItem('accessToken')).toBeNull();
    expect(localStorage.getItem('refreshToken')).toBeNull();
    expect(localStorage.getItem('staffRole')).toBeNull();
    expect(assignMock).toHaveBeenCalledWith('/admin/login?returnUrl=%2Forders');
  });

  it('401 и сетевой сбой refresh: очищает токены и редиректит', async () => {
    localStorage.setItem('accessToken', 'expired-token');
    localStorage.setItem('staffRole', 'admin');
    const assignMock = vi.fn();
    vi.stubGlobal('location', {
      pathname: '/admin/orders',
      search: '',
      assign: assignMock,
    });
    fetchMock
      .mockResolvedValueOnce(
        new Response('{}', {
          status: 401,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
      .mockRejectedValueOnce(new Error('network'));

    const err = await authenticatedFetch('/api/v1/admin/orders').catch(
      (e) => e,
    );

    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(401);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(localStorage.getItem('accessToken')).toBeNull();
    expect(localStorage.getItem('refreshToken')).toBeNull();
    expect(localStorage.getItem('staffRole')).toBeNull();
    expect(assignMock).toHaveBeenCalledWith('/admin/login?returnUrl=%2Forders');
  });

  // --- 2.2b: 401 на /staff/auth/login — НЕ вызывает assign, НЕ очищает токен ---
  it('401 на /api/v1/staff/auth/login: не вызывает assign и не очищает токен', async () => {
    localStorage.setItem('accessToken', 'some-token');
    const assignMock = vi.fn();
    vi.stubGlobal('location', {
      pathname: '/admin/login',
      search: '',
      assign: assignMock,
    });
    fetchMock.mockResolvedValue(
      new Response('{}', {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    await authenticatedFetch('/api/v1/staff/auth/login').catch(() => {});

    expect(assignMock).not.toHaveBeenCalled();
    expect(localStorage.getItem('accessToken')).toBe('some-token');
  });

  // --- 2.2c: 500 — НЕ вызывает assign ---
  it('500 на любом маршруте: не вызывает window.location.assign', async () => {
    const assignMock = vi.fn();
    vi.stubGlobal('location', {
      pathname: '/admin/menu',
      search: '',
      assign: assignMock,
    });
    fetchMock.mockResolvedValue(
      new Response('{}', {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    await authenticatedFetch('/api/v1/admin/menu').catch(() => {});

    expect(assignMock).not.toHaveBeenCalled();
  });

  // --- 2.2d: 200 — НЕ вызывает assign ---
  it('200: не вызывает window.location.assign', async () => {
    const assignMock = vi.fn();
    vi.stubGlobal('location', {
      pathname: '/admin/menu',
      search: '',
      assign: assignMock,
    });
    fetchMock.mockResolvedValue(okResponse({ ok: true }));

    await authenticatedFetch('/api/v1/admin/menu');

    expect(assignMock).not.toHaveBeenCalled();
  });
});

// --- Тесты для токен-хелперов ---
describe('token helpers', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('setAccessToken / getAccessToken: round-trip', () => {
    setAccessToken('my-token');
    expect(getAccessToken()).toBe('my-token');
  });

  it('setRefreshToken / getRefreshToken: never exposes browser refresh tokens', () => {
    setRefreshToken('my-refresh');
    expect(getRefreshToken()).toBeNull();
    expect(localStorage.getItem('refreshToken')).toBeNull();
  });

  it('clearAccessToken: удаляет токен', () => {
    setAccessToken('my-token');
    clearAccessToken();
    expect(getAccessToken()).toBeNull();
  });

  it('clearAuthTokens: удаляет accessToken и refreshToken', () => {
    setAccessToken('my-token');
    setRefreshToken('my-refresh');
    clearAuthTokens();
    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
  });

  it('getAccessToken: возвращает null если токена нет', () => {
    expect(getAccessToken()).toBeNull();
  });
});

// --- Тесты для logout ---
describe('logout', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('revokes cookie session, clears token, and navigates to /admin/login', async () => {
    setAccessToken('tok');
    const assignMock = vi.fn();
    vi.stubGlobal('location', {
      pathname: '/',
      search: '',
      assign: assignMock,
    });
    fetchMock.mockResolvedValue(new Response('{}', { status: 200 }));

    await logout();

    expect(getAccessToken()).toBeNull();
    expect(assignMock).toHaveBeenCalledWith('/admin/login');
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/staff/auth/logout');
  });

  it('очищает accessToken, refreshToken и staffRole', async () => {
    setAccessToken('tok');
    setRefreshToken('ref');
    localStorage.setItem('staffRole', 'courier');
    vi.stubGlobal('location', { pathname: '/', search: '', assign: vi.fn() });
    fetchMock.mockResolvedValue(new Response('{}', { status: 200 }));

    await logout();

    expect(localStorage.getItem('accessToken')).toBeNull();
    expect(localStorage.getItem('refreshToken')).toBeNull();
    expect(localStorage.getItem('staffRole')).toBeNull();
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/staff/auth/logout');
    expect((init.headers as Record<string, string>)['Authorization']).toBe(
      'Bearer tok',
    );
    expect(init.credentials).toBe('include');
    expect(JSON.parse(init.body as string)).toEqual({});
  });

  it('очищает локальную сессию даже если backend logout падает', async () => {
    setAccessToken('tok');
    setRefreshToken('ref');
    localStorage.setItem('staffRole', 'admin');
    vi.stubGlobal('location', { pathname: '/', search: '', assign: vi.fn() });
    fetchMock.mockRejectedValue(new Error('network'));

    await logout();

    expect(localStorage.getItem('accessToken')).toBeNull();
    expect(localStorage.getItem('refreshToken')).toBeNull();
    expect(localStorage.getItem('staffRole')).toBeNull();
  });

  it('refreshes before revocation when logout sees expired access token', async () => {
    setAccessToken('expired-access');
    setRefreshToken('refresh-old');
    localStorage.setItem('staffRole', 'admin');
    vi.stubGlobal('location', { pathname: '/', search: '', assign: vi.fn() });
    fetchMock
      .mockResolvedValueOnce(new Response('{}', { status: 401 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            access_token: 'access-new',
            refresh_token: 'refresh-new',
            role: 'admin',
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      )
      .mockResolvedValueOnce(new Response('{}', { status: 200 }));

    await logout();

    expect(fetchMock).toHaveBeenCalledTimes(3);
    const [refreshUrl, refreshInit] = fetchMock.mock.calls[1] as [
      string,
      RequestInit,
    ];
    expect(refreshUrl).toBe('/api/v1/staff/auth/refresh');
    expect(refreshInit.credentials).toBe('include');
    expect(JSON.parse(refreshInit.body as string)).toEqual({});
    const [logoutUrl, logoutInit] = fetchMock.mock.calls[2] as [
      string,
      RequestInit,
    ];
    expect(logoutUrl).toBe('/api/v1/staff/auth/logout');
    expect(
      (logoutInit.headers as Record<string, string>)['Authorization'],
    ).toBe('Bearer access-new');
    expect(logoutInit.credentials).toBe('include');
    expect(JSON.parse(logoutInit.body as string)).toEqual({});
    expect(localStorage.getItem('accessToken')).toBeNull();
    expect(localStorage.getItem('refreshToken')).toBeNull();
    expect(localStorage.getItem('staffRole')).toBeNull();
  });

  it('refreshes then revokes when only the refresh cookie remains', async () => {
    setRefreshToken('refresh-old');
    localStorage.setItem('staffRole', 'admin');
    vi.stubGlobal('location', { pathname: '/', search: '', assign: vi.fn() });
    fetchMock
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            access_token: 'access-new',
            refresh_token: 'refresh-new',
            role: 'admin',
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      )
      .mockResolvedValueOnce(new Response('{}', { status: 200 }));

    await logout();

    expect(fetchMock).toHaveBeenCalledTimes(2);
    const [refreshUrl, refreshInit] = fetchMock.mock.calls[0] as [
      string,
      RequestInit,
    ];
    expect(refreshUrl).toBe('/api/v1/staff/auth/refresh');
    expect(refreshInit.credentials).toBe('include');
    expect(JSON.parse(refreshInit.body as string)).toEqual({});
    const [logoutUrl, logoutInit] = fetchMock.mock.calls[1] as [
      string,
      RequestInit,
    ];
    expect(logoutUrl).toBe('/api/v1/staff/auth/logout');
    expect(
      (logoutInit.headers as Record<string, string>)['Authorization'],
    ).toBe('Bearer access-new');
    expect(logoutInit.credentials).toBe('include');
    expect(JSON.parse(logoutInit.body as string)).toEqual({});
    expect(localStorage.getItem('accessToken')).toBeNull();
    expect(localStorage.getItem('refreshToken')).toBeNull();
    expect(localStorage.getItem('staffRole')).toBeNull();
  });
});

// --- Тесты для staffLogin ---
describe('staffLogin', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    const assignMock = vi.fn();
    vi.stubGlobal('location', {
      pathname: '/admin/login',
      search: '',
      assign: assignMock,
    });
    localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('успешный логин: возвращает access_token и role', async () => {
    fetchMock.mockResolvedValue(
      new Response(
        JSON.stringify({
          access_token: 'tok',
          refresh_token: 'ref',
          token_type: 'bearer',
          role: 'admin',
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    );

    const result = await staffLogin('admin', 'secret');
    expect(result.access_token).toBe('tok');
    expect(result.refresh_token).toBe('ref');
    expect(result.role).toBe('admin');
    expect(fetchMock.mock.calls[0][1].credentials).toBe('include');
  });

  it('401 от staffLogin: бросает ApiError(401), НЕ вызывает window.location.assign', async () => {
    fetchMock.mockResolvedValue(
      new Response('{}', {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    const err = await staffLogin('admin', 'wrong').catch((e) => e);

    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(401);
    expect(window.location.assign).not.toHaveBeenCalled();
  });
});
