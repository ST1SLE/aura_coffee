// Типы зеркалят Pydantic-схемы из
// services/core-api/src/core_api/schemas/admin_users.py.
// Без zod — паттерн как в api/promocodes.ts.

import { authenticatedFetch, ApiError } from './client';

export { ApiError };

// ── Enums / literals ─────────────────────────────────────────────────────────

export type UserStatus =
  | 'active'
  | 'blocked'
  | 'pending_verification'
  | 'deleted';

export type UserStatusFilter = UserStatus | 'all';

export type LoyaltyTransactionType =
  | 'accrual'
  | 'redemption'
  | 'reversal'
  | 'admin_adjustment';

// ── Response shapes ──────────────────────────────────────────────────────────

export interface UserSummary {
  id: string;
  status: UserStatus;
  display_name: string;
  loyalty_balance: number;
  created_at: string;
}

export interface UserListResponse {
  items: UserSummary[];
  page: number;
  per_page: number;
  total: number;
}

export interface LoyaltyTransactionItem {
  id: string;
  type: LoyaltyTransactionType;
  amount: number;
  balance_after: number;
  description: string | null;
  created_at: string;
}

export interface UserDetailResponse {
  id: string;
  status: UserStatus;
  display_name: string;
  language: string | null;
  created_at: string;
  loyalty_balance: number;
  loyalty_transactions: LoyaltyTransactionItem[];
  active_orders_count: number;
}

export interface BlockUserResponse {
  user_id: string;
  status: UserStatus;
  cancelled_orders_count: number;
}

export interface UnblockUserResponse {
  user_id: string;
  status: UserStatus;
}

// ── Request shapes ───────────────────────────────────────────────────────────

export interface LoyaltyAdjustRequest {
  delta: number;
  reason: string;
}

export interface LoyaltyAdjustResponse {
  transaction_id: string;
  new_balance: number;
  delta: number;
}

// ── helpers ──────────────────────────────────────────────────────────────────

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await authenticatedFetch(path, init);
  if (res.status === 204) return undefined as unknown as T;
  return res.json() as Promise<T>;
}

function post<T>(path: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method: 'POST' };
  if (body !== undefined) {
    init.headers = { 'Content-Type': 'application/json' };
    init.body = JSON.stringify(body);
  }
  return json<T>(path, init);
}

// ── Query-string builder ─────────────────────────────────────────────────────

export interface ListUsersParams {
  status?: UserStatusFilter;
  search?: string;
  page?: number;
  perPage?: number;
}

function buildListQuery(params: ListUsersParams | undefined): string {
  if (!params) return '';
  const usp = new URLSearchParams();
  if (params.status && params.status !== 'all') usp.set('status', params.status);
  if (params.search) usp.set('search', params.search);
  if (params.page != null) usp.set('page', String(params.page));
  if (params.perPage != null) usp.set('per_page', String(params.perPage));
  const qs = usp.toString();
  return qs ? `?${qs}` : '';
}

// ── API functions ────────────────────────────────────────────────────────────

export const listUsers = (
  params?: ListUsersParams,
): Promise<UserListResponse> =>
  json(`/api/v1/admin/users${buildListQuery(params)}`);

export const getUser = (userId: string): Promise<UserDetailResponse> =>
  json(`/api/v1/admin/users/${userId}`);

export const blockUser = (userId: string): Promise<BlockUserResponse> =>
  post(`/api/v1/admin/users/${userId}/block`);

export const unblockUser = (userId: string): Promise<UnblockUserResponse> =>
  post(`/api/v1/admin/users/${userId}/unblock`);

export const adjustLoyalty = (
  userId: string,
  input: LoyaltyAdjustRequest,
): Promise<LoyaltyAdjustResponse> =>
  post(`/api/v1/admin/users/${userId}/loyalty/adjust`, input);

// ── Error parsing ────────────────────────────────────────────────────────────

// Возвращает 'insufficient_balance' если 422-body содержит такой маркер
// в detail-строке или code-поле. Иначе null. Формат сервера для этого
// конкретного случая не зафиксирован в phase6-plan, поэтому парсер
// гибкий: принимает и {code: 'insufficient_balance'}, и {detail: '...'}.
export function parseAdjustError(err: unknown): 'insufficient_balance' | null {
  if (!(err instanceof ApiError)) return null;
  const body = err.body as
    | { detail?: unknown; code?: unknown }
    | null
    | undefined;
  if (!body) return null;
  if (typeof body.code === 'string' && body.code === 'insufficient_balance') {
    return 'insufficient_balance';
  }
  if (typeof body.detail === 'string' && body.detail.includes('insufficient_balance')) {
    return 'insufficient_balance';
  }
  return null;
}
