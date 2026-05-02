import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';

vi.mock('./client', () => ({
  authenticatedFetch: vi.fn(),
}));

import { authenticatedFetch } from './client';
import {
  listNotifications,
  NotificationApiError,
  type NotificationFeedItem,
} from './notifications';

const asOk = (body: unknown, status = 200): Response =>
  ({
    ok: true,
    status,
    json: async () => body,
  }) as unknown as Response;

const asError = (status: number, body: unknown = { detail: 'err' }): Response =>
  ({
    ok: false,
    status,
    json: async () => body,
  }) as unknown as Response;

const notification = (
  over: Partial<NotificationFeedItem> = {},
): NotificationFeedItem => ({
  id: '11111111-1111-1111-1111-111111111111',
  order_id: '22222222-2222-2222-2222-222222222222',
  channel: 'in_app',
  type: 'order_status_change',
  status: 'sent',
  message_ru: 'Заказ готов',
  message_en: 'Order ready',
  sent_at: '2026-05-02T12:00:00Z',
  created_at: '2026-05-02T12:00:00Z',
  ...over,
});

beforeEach(() => {
  vi.clearAllMocks();
});

describe('listNotifications', () => {
  it('GETs the paginated notification feed and returns notifications[]', async () => {
    (authenticatedFetch as Mock).mockResolvedValue(
      asOk({
        notifications: [notification()],
        total_count: 1,
        page: 2,
        per_page: 10,
      }),
    );

    const result = await listNotifications(2, 10);

    expect(authenticatedFetch).toHaveBeenCalledWith(
      '/api/v1/profile/notifications?page=2&per_page=10',
    );
    expect(result.notifications[0].message_en).toBe('Order ready');
    expect(result.total_count).toBe(1);
  });

  it('parses nullable order_id and sent_at', async () => {
    (authenticatedFetch as Mock).mockResolvedValue(
      asOk({
        notifications: [notification({ order_id: null, sent_at: null })],
        total_count: 1,
        page: 1,
        per_page: 20,
      }),
    );

    const result = await listNotifications();

    expect(result.notifications[0].order_id).toBeNull();
    expect(result.notifications[0].sent_at).toBeNull();
  });

  it('throws NotificationApiError on non-ok response', async () => {
    (authenticatedFetch as Mock).mockResolvedValue(
      asError(403, { detail: 'forbidden' }),
    );

    await expect(listNotifications()).rejects.toMatchObject({
      status: 403,
      detail: 'forbidden',
    });
  });

  it('throws NotificationApiError on malformed payload', async () => {
    (authenticatedFetch as Mock).mockResolvedValue(
      asOk({
        items: [notification()],
        total_count: 1,
        page: 1,
        per_page: 20,
      }),
    );

    await expect(listNotifications()).rejects.toBeInstanceOf(
      NotificationApiError,
    );
  });
});
