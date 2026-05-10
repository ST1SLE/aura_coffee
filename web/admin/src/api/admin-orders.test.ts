import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  listAdminOrders,
  getAdminOrder,
  retryRefund,
  updateOrderStatus,
  cancelAdminOrder,
  ApiError,
} from './admin-orders';
import { clearAuthTokens, setAccessToken } from './client';

describe('api/admin-orders', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    localStorage.clear();
    clearAuthTokens();
    // Токен для прохождения authenticatedFetch без редиректа на login.
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

  // ── listAdminOrders ────────────────────────────────────────────────────────

  it('listAdminOrders builds URL with all params set', async () => {
    mockJson({ orders: [], total_count: 0, page: 2, per_page: 20 });

    await listAdminOrders({
      status: 'preparing',
      type: 'delivery',
      page: 2,
      per_page: 20,
    });

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toContain('/api/v1/admin/orders');
    expect(url).toContain('status=preparing');
    expect(url).toContain('type=delivery');
    expect(url).toContain('page=2');
    expect(url).toContain('per_page=20');
  });

  it('listAdminOrders omits undefined params', async () => {
    mockJson({ orders: [], total_count: 0, page: 1, per_page: 20 });

    await listAdminOrders({ status: 'active' });

    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toContain('status=active');
    expect(url).not.toContain('type=');
    expect(url).not.toContain('page=');
    expect(url).not.toContain('per_page=');
  });

  it('listAdminOrders with no args hits bare endpoint', async () => {
    mockJson({ orders: [], total_count: 0, page: 1, per_page: 20 });

    await listAdminOrders();

    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toMatch(/\/api\/v1\/admin\/orders$/);
  });

  it('listAdminOrders sends the failed-refund exception filter', async () => {
    mockJson({ orders: [], total_count: 0, page: 1, per_page: 20 });

    await listAdminOrders({ status: 'refund_failed' });

    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toContain('status=refund_failed');
  });

  it('listAdminOrders propagates 403 as ApiError', async () => {
    mockJson({ detail: 'forbidden' }, 403);

    const err = await listAdminOrders().catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(403);
  });

  // ── getAdminOrder ──────────────────────────────────────────────────────────

  it('getAdminOrder issues GET to detail URL', async () => {
    mockJson({ id: '00000000-0000-0000-0000-000000000001' });

    await getAdminOrder('00000000-0000-0000-0000-000000000001');

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit | undefined];
    expect(url).toContain('/api/v1/admin/orders/00000000-0000-0000-0000-000000000001');
    // GET не передаёт init.method — это дефолт fetch.
    expect(init?.method ?? 'GET').toBe('GET');
  });

  // ── retryRefund ───────────────────────────────────────────────────────────

  it('retryRefund POSTs to the admin refund retry endpoint', async () => {
    mockJson({
      order_id: 'order-uuid-1',
      payment_id: 'payment-uuid-1',
      payment_status: 'refund_failed',
      queued: true,
    }, 202);

    await retryRefund('order-uuid-1');

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain('/api/v1/admin/orders/order-uuid-1/refund/retry');
    expect(init.method).toBe('POST');
  });

  // ── updateOrderStatus ──────────────────────────────────────────────────────

  it('updateOrderStatus PATCHes /status with {new_status}', async () => {
    mockJson({ id: 'abc', status: 'preparing' });

    await updateOrderStatus('abc', 'preparing');

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain('/api/v1/orders/abc/status');
    expect(init.method).toBe('PATCH');
    expect(JSON.parse(init.body as string)).toEqual({ new_status: 'preparing' });
  });

  // ── cancelAdminOrder ───────────────────────────────────────────────────────

  it('cancelAdminOrder with no reason sends null', async () => {
    mockJson({ id: 'abc', status: 'cancelled' });

    await cancelAdminOrder('abc');

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain('/api/v1/orders/abc/cancel');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body as string)).toEqual({ reason: null });
  });

  it('cancelAdminOrder passes the provided reason', async () => {
    mockJson({ id: 'abc', status: 'cancelled' });

    await cancelAdminOrder('abc', 'customer asked');

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({ reason: 'customer asked' });
  });
});
