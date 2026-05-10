import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  getSettings,
  updateSettings,
  parseFieldErrorsDeep,
  toKopecks,
  kopecksToRubles,
  ApiError,
} from './admin-settings';
import type { ShopSettingsUpdate } from './admin-settings';
import { clearAuthTokens, setAccessToken } from './client';

function fullPayload(): ShopSettingsUpdate {
  return {
    shop_lat: 55.75,
    shop_lon: 37.62,
    delivery_radius_km: 5,
    min_delivery_amount: 50000,
    free_delivery_threshold: 150000,
    delivery_fee: 15000,
    loyalty_percent: 5,
    default_prep_time_minutes: 10,
    estimated_delivery_time_minutes: 30,
    auto_close_minutes: 60,
    working_hours: {
      mon: { open: '08:00', close: '22:00' },
      tue: { open: '08:00', close: '22:00' },
      wed: { open: '08:00', close: '22:00' },
      thu: { open: '08:00', close: '22:00' },
      fri: { open: '08:00', close: '22:00' },
      sat: { open: '10:00', close: '20:00' },
      sun: null,
    },
  };
}

describe('api/admin-settings', () => {
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

  it('getSettings — GET /api/v1/admin/settings', async () => {
    mockJson({ ...fullPayload(), updated_at: '2026-04-20T10:00:00Z' });
    await getSettings();
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit | undefined];
    expect(url).toContain('/api/v1/admin/settings');
    expect(init?.method).toBeUndefined();
  });

  it('updateSettings — PUT with JSON body', async () => {
    mockJson({ ...fullPayload(), updated_at: '2026-04-20T10:00:00Z' });
    const payload = fullPayload();
    await updateSettings(payload);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain('/api/v1/admin/settings');
    expect(init.method).toBe('PUT');
    expect((init.headers as Record<string, string>)['Content-Type']).toBe('application/json');
    const body = JSON.parse(init.body as string);
    expect(body.loyalty_percent).toBe(5);
    expect(body.working_hours.sun).toBeNull();
    expect(body.auto_close_minutes).toBe(60);
  });

  it('updateSettings — throws ApiError on 422', async () => {
    mockJson(
      {
        detail: [{ loc: ['body', 'loyalty_percent'], msg: 'out_of_range' }],
      },
      422,
    );
    await expect(updateSettings(fullPayload())).rejects.toBeInstanceOf(ApiError);
  });

  it('getSettings — throws ApiError on 500', async () => {
    fetchMock.mockResolvedValue(new Response('server down', { status: 500 }));
    await expect(getSettings()).rejects.toBeInstanceOf(ApiError);
  });

  it('parseFieldErrorsDeep — вложенный loc в точечный путь', () => {
    const err = new ApiError(
      422,
      {
        detail: [
          {
            loc: ['body', 'working_hours', 'mon', 'open'],
            msg: 'invalid',
          },
        ],
      },
      'HTTP 422',
    );
    expect(parseFieldErrorsDeep(err)).toEqual({
      'working_hours.mon.open': 'invalid',
    });
  });

  it('parseFieldErrorsDeep — плоский loc', () => {
    const err = new ApiError(
      422,
      {
        detail: [{ loc: ['body', 'loyalty_percent'], msg: 'too_big' }],
      },
      'HTTP 422',
    );
    expect(parseFieldErrorsDeep(err)).toEqual({ loyalty_percent: 'too_big' });
  });

  it('parseFieldErrorsDeep — не ApiError → пустой объект', () => {
    expect(parseFieldErrorsDeep(new Error('boom'))).toEqual({});
  });

  it('parseFieldErrorsDeep — body без detail → пустой объект', () => {
    const err = new ApiError(422, {}, 'HTTP 422');
    expect(parseFieldErrorsDeep(err)).toEqual({});
  });

  it('toKopecks — целые рубли', () => {
    expect(toKopecks(100)).toBe(10000);
    expect(toKopecks(0)).toBe(0);
  });

  it('toKopecks — дробные рубли округляются', () => {
    expect(toKopecks(1.5)).toBe(150);
    expect(toKopecks(1.234)).toBe(123);
  });

  it('kopecksToRubles — целое число без .00', () => {
    expect(kopecksToRubles(10000)).toBe('100');
    expect(kopecksToRubles(0)).toBe('0');
  });

  it('kopecksToRubles — с копейками сохраняет дробь', () => {
    expect(kopecksToRubles(12345)).toBe('123.45');
  });
});
