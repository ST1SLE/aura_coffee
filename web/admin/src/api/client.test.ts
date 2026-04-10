import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { authenticatedFetch, ApiError } from './client';

// Мок import.meta.env — Vitest подставляет его через define в vite.config
// BASE_URL будет пустой строкой (default), path передаётся как есть

describe('authenticatedFetch', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
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
});
