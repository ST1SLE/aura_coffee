import { authenticatedFetch } from './client';

// START_MODULE_CONTRACT
//   PURPOSE: Customer notification feed REST client with runtime shape checks.
//   SCOPE:   NotificationChannel/Type/Status unions, NotificationFeedItem,
//            NotificationFeedResponse, NotificationApiError,
//            listNotifications.
//   DEPENDS: M-CORE-API (HTTP /api/v1/profile/notifications),
//            ./client (authenticatedFetch).
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §5.2 notifications;
//            INV-013 (own-user scoped feed, no user_id/PII projection).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   NotificationChannel      - in_app | sms
//   NotificationType         - order_status_change | otp
//   NotificationStatus       - pending | sent | failed
//   NotificationFeedItem     - one customer-visible notification row
//   NotificationFeedResponse - paginated wrapper
//   NotificationApiError     - Error subclass with HTTP status + detail
//   listNotifications        - GET /profile/notifications?page&per_page
// END_MODULE_MAP

export type NotificationChannel = 'in_app' | 'sms';
export type NotificationType = 'order_status_change' | 'otp';
export type NotificationStatus = 'pending' | 'sent' | 'failed';

export interface NotificationFeedItem {
  id: string;
  order_id: string | null;
  channel: NotificationChannel;
  type: NotificationType;
  status: NotificationStatus;
  message_ru: string;
  message_en: string;
  sent_at: string | null;
  created_at: string;
}

export interface NotificationFeedResponse {
  notifications: NotificationFeedItem[];
  total_count: number;
  page: number;
  per_page: number;
}

// START_CONTRACT: NotificationApiError
//   PURPOSE: Carry HTTP status + detail for notification-feed UI failures.
//   INPUTS:  status: number
//            detail?: string
//   OUTPUTS: NotificationApiError instance.
//   SIDE_EFFECTS: none.
// END_CONTRACT: NotificationApiError
export class NotificationApiError extends Error {
  constructor(
    public status: number,
    public detail?: string,
  ) {
    super(detail ?? `HTTP ${status}`);
    this.name = 'NotificationApiError';
  }
}

async function parseError(res: Response): Promise<NotificationApiError> {
  let detail: string | undefined;
  try {
    const body = (await res.json()) as { detail?: string };
    detail = body?.detail;
  } catch {
    // non-json body
  }
  return new NotificationApiError(res.status, detail);
}

function isNotificationItem(value: unknown): value is NotificationFeedItem {
  if (!value || typeof value !== 'object') return false;
  const row = value as NotificationFeedItem;
  return (
    typeof row.id === 'string' &&
    (typeof row.order_id === 'string' || row.order_id === null) &&
    typeof row.channel === 'string' &&
    typeof row.type === 'string' &&
    typeof row.status === 'string' &&
    typeof row.message_ru === 'string' &&
    typeof row.message_en === 'string' &&
    (typeof row.sent_at === 'string' || row.sent_at === null) &&
    typeof row.created_at === 'string'
  );
}

function assertNotificationPage(
  body: unknown,
): asserts body is NotificationFeedResponse {
  if (
    !body ||
    typeof body !== 'object' ||
    !Array.isArray((body as NotificationFeedResponse).notifications) ||
    !(body as NotificationFeedResponse).notifications.every(isNotificationItem) ||
    typeof (body as NotificationFeedResponse).total_count !== 'number' ||
    typeof (body as NotificationFeedResponse).page !== 'number' ||
    typeof (body as NotificationFeedResponse).per_page !== 'number'
  ) {
    throw new NotificationApiError(500, 'Invalid notification feed payload');
  }
}

// START_CONTRACT: listNotifications
//   PURPOSE: Fetch one page of the current customer's in-app notification feed.
//   INPUTS:  page: number, per_page: number.
//   OUTPUTS: Promise<NotificationFeedResponse>.
//   SIDE_EFFECTS: HTTP GET /api/v1/profile/notifications?page&per_page;
//                 throws NotificationApiError on non-2xx or schema mismatch.
//   LINKS:   PDD §5.2, INV-002, INV-013.
// END_CONTRACT: listNotifications
export async function listNotifications(
  page = 1,
  per_page = 20,
): Promise<NotificationFeedResponse> {
  const res = await authenticatedFetch(
    `/api/v1/profile/notifications?page=${page}&per_page=${per_page}`,
  );
  if (!res.ok) throw await parseError(res);
  const body = await res.json();
  assertNotificationPage(body);
  return body;
}
