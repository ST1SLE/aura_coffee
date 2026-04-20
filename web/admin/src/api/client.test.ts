import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  authenticatedFetch,
  ApiError,
  getAccessToken,
  setAccessToken,
  clearAccessToken,
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
    expect((init.headers as Record<string, string>)['Authorization']).toBeUndefined();
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
      new Response('{}', { status: 401, headers: { 'Content-Type': 'application/json' } }),
    );

    const err = await authenticatedFetch('/api/v1/admin/menu/categories').catch((e) => e);

    expect(window.location.assign).toHaveBeenCalledWith(
      '/admin/login?returnUrl=%2Fmenu',
    );
    expect(localStorage.getItem('accessToken')).toBeNull();
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(401);
  });

  // --- 2.2b: 401 на /staff/auth/login — НЕ вызывает assign, НЕ очищает токен ---
  it('401 на /api/v1/staff/auth/login: не вызывает assign и не очищает токен', async () => {
    localStorage.setItem('accessToken', 'some-token');
    const assignMock = vi.fn();
    vi.stubGlobal('location', { pathname: '/admin/login', search: '', assign: assignMock });
    fetchMock.mockResolvedValue(
      new Response('{}', { status: 401, headers: { 'Content-Type': 'application/json' } }),
    );

    await authenticatedFetch('/api/v1/staff/auth/login').catch(() => {});

    expect(assignMock).not.toHaveBeenCalled();
    expect(localStorage.getItem('accessToken')).toBe('some-token');
  });

  // --- 2.2c: 500 — НЕ вызывает assign ---
  it('500 на любом маршруте: не вызывает window.location.assign', async () => {
    const assignMock = vi.fn();
    vi.stubGlobal('location', { pathname: '/admin/menu', search: '', assign: assignMock });
    fetchMock.mockResolvedValue(
      new Response('{}', { status: 500, headers: { 'Content-Type': 'application/json' } }),
    );

    await authenticatedFetch('/api/v1/admin/menu').catch(() => {});

    expect(assignMock).not.toHaveBeenCalled();
  });

  // --- 2.2d: 200 — НЕ вызывает assign ---
  it('200: не вызывает window.location.assign', async () => {
    const assignMock = vi.fn();
    vi.stubGlobal('location', { pathname: '/admin/menu', search: '', assign: assignMock });
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

  it('clearAccessToken: удаляет токен', () => {
    setAccessToken('my-token');
    clearAccessToken();
    expect(getAccessToken()).toBeNull();
  });

  it('getAccessToken: возвращает null если токена нет', () => {
    expect(getAccessToken()).toBeNull();
  });
});

// --- Тесты для logout ---
describe('logout', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('очищает токен и вызывает window.location.assign("/admin/login")', () => {
    setAccessToken('tok');
    const assignMock = vi.fn();
    vi.stubGlobal('location', { pathname: '/', search: '', assign: assignMock });

    logout();

    expect(getAccessToken()).toBeNull();
    expect(assignMock).toHaveBeenCalledWith('/admin/login');
  });

  it('очищает и accessToken, и staffRole', () => {
    setAccessToken('tok');
    localStorage.setItem('staffRole', 'courier');
    vi.stubGlobal('location', { pathname: '/', search: '', assign: vi.fn() });

    logout();

    expect(localStorage.getItem('accessToken')).toBeNull();
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
    vi.stubGlobal('location', { pathname: '/admin/login', search: '', assign: assignMock });
    localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('успешный логин: возвращает access_token и role', async () => {
    fetchMock.mockResolvedValue(
      new Response(
        JSON.stringify({ access_token: 'tok', refresh_token: 'ref', token_type: 'bearer', role: 'admin' }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    );

    const result = await staffLogin('admin', 'secret');
    expect(result.access_token).toBe('tok');
    expect(result.role).toBe('admin');
  });

  it('401 от staffLogin: бросает ApiError(401), НЕ вызывает window.location.assign', async () => {
    fetchMock.mockResolvedValue(
      new Response('{}', { status: 401, headers: { 'Content-Type': 'application/json' } }),
    );

    const err = await staffLogin('admin', 'wrong').catch((e) => e);

    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(401);
    expect(window.location.assign).not.toHaveBeenCalled();
  });
});
