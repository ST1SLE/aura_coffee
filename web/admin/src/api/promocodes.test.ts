import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  listPromocodes,
  getPromocode,
  createPromocode,
  updatePromocode,
  activatePromocode,
  deactivatePromocode,
  parseFieldErrors,
  ApiError,
} from './promocodes';
import { clearAuthTokens, setAccessToken } from './client';
import type {
  PromocodeCreateInput,
  PromocodeUpdateInput,
} from './promocodes';

describe('api/promocodes', () => {
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

  it('listPromocodes — state=all omits param', async () => {
    mockJson({ items: [], page: 1, per_page: 20, total: 0 });
    await listPromocodes({ state: 'all', page: 1, per_page: 20 });
    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toContain('/api/v1/admin/promocodes');
    expect(url).not.toContain('state=');
    expect(url).toContain('page=1');
    expect(url).toContain('per_page=20');
  });

  it('listPromocodes — state/code/page/per_page encoded', async () => {
    mockJson({ items: [], page: 2, per_page: 10, total: 0 });
    await listPromocodes({ state: 'active', code: 'WEEK', page: 2, per_page: 10 });
    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toContain('state=active');
    expect(url).toContain('code=WEEK');
    expect(url).toContain('page=2');
    expect(url).toContain('per_page=10');
  });

  it('getPromocode — GET by id', async () => {
    mockJson({ id: 'abc', code: 'WEEK' });
    await getPromocode('abc');
    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toContain('/api/v1/admin/promocodes/abc');
  });

  it('createPromocode — fixed_amount converts rubles to kopecks', async () => {
    mockJson({ id: 'abc' }, 201);
    const input: PromocodeCreateInput = {
      code: 'WEEK',
      discount_type: 'fixed_amount',
      discount_value_rubles: 500,
      min_order_rubles: 1000,
      valid_from: null,
      valid_until: null,
      max_uses: null,
      max_uses_per_user: null,
    };
    await createPromocode(input);
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(init.body as string);
    expect(body.discount_value).toBe(50000);
    expect(body.min_order_amount).toBe(100000);
    expect(body.discount_type).toBe('fixed_amount');
    expect(body.code).toBe('WEEK');
  });

  it('createPromocode — percent is passthrough integer', async () => {
    mockJson({ id: 'abc' }, 201);
    const input: PromocodeCreateInput = {
      code: 'P10',
      discount_type: 'percent',
      discount_value_rubles: 10,
      min_order_rubles: null,
      valid_from: null,
      valid_until: null,
      max_uses: null,
      max_uses_per_user: null,
    };
    await createPromocode(input);
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(init.body as string);
    expect(body.discount_value).toBe(10);
    expect(body.min_order_amount).toBeUndefined();
  });

  it('updatePromocode — PATCH with kopecks conversion when fields provided', async () => {
    mockJson({ id: 'abc' });
    const patch: PromocodeUpdateInput = {
      discount_type: 'fixed_amount',
      discount_value_rubles: 500,
      min_order_rubles: 1000,
    };
    await updatePromocode('abc', patch);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain('/api/v1/admin/promocodes/abc');
    expect(init.method).toBe('PATCH');
    const body = JSON.parse(init.body as string);
    expect(body.discount_value).toBe(50000);
    expect(body.min_order_amount).toBe(100000);
  });

  it('activatePromocode — POST /activate', async () => {
    mockJson({ id: 'abc', is_active: true });
    await activatePromocode('abc');
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain('/api/v1/admin/promocodes/abc/activate');
    expect(init.method).toBe('POST');
  });

  it('deactivatePromocode — POST /deactivate', async () => {
    mockJson({ id: 'abc', is_active: false });
    await deactivatePromocode('abc');
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain('/api/v1/admin/promocodes/abc/deactivate');
    expect(init.method).toBe('POST');
  });

  it('parseFieldErrors — extracts {field: [detail-code]} from FastAPI 422', () => {
    const err = new ApiError(422, {
      detail: [
        { loc: ['body', 'code'], msg: 'field_locked_after_use', type: 'value_error' },
        { loc: ['body', 'valid_until'], msg: 'dates_inverted', type: 'value_error' },
      ],
    }, 'HTTP 422');
    const parsed = parseFieldErrors(err);
    expect(parsed).toEqual({
      code: 'field_locked_after_use',
      valid_until: 'dates_inverted',
    });
  });
});
