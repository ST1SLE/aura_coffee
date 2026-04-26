// Типы зеркалят Pydantic-схемы из
// services/core-api/src/core_api/schemas/admin_users.py.
// Без zod — паттерн как в api/promocodes.ts.

import { authenticatedFetch, ApiError } from './client';

// START_MODULE_CONTRACT
//   PURPOSE: Typed client for admin user-management endpoints — list, get detail,
//            block/unblock, adjust loyalty balance — plus error parser for the
//            insufficient_balance code returned from /loyalty/adjust.
//   SCOPE:   Wraps /api/v1/admin/users/*; mirrors core-api Pydantic schemas
//            in services/core-api/src/core_api/schemas/admin_users.py.
//   DEPENDS: ./client (authenticatedFetch, ApiError).
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, PDD §6.7 user management,
//            INV-002 (admin scope), INV-013 (PII handling — display_name only,
//            no raw phone numbers in summaries).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   ApiError                    - re-export
//   UserStatus                  - 'active'|'blocked'|'pending_verification'|'deleted'
//   UserStatusFilter            - UserStatus | 'all'
//   LoyaltyTransactionType      - accrual/redemption/reversal/admin_adjustment
//   UserSummary                 - row in users list (no raw PII per INV-013)
//   UserListResponse            - paginated list shape
//   LoyaltyTransactionItem      - single ledger row
//   UserDetailResponse          - per-user detail with transactions and balance
//   BlockUserResponse           - response of /block (cancelled_orders_count)
//   UnblockUserResponse         - response of /unblock
//   LoyaltyAdjustRequest        - {delta, reason} body
//   LoyaltyAdjustResponse       - new balance + transaction id
//   ListUsersParams             - status/search/page/perPage params
//   listUsers                   - GET /api/v1/admin/users
//   getUser                     - GET /api/v1/admin/users/{id}
//   blockUser                   - POST /block (admin only; cancels active orders)
//   unblockUser                 - POST /unblock (admin only)
//   adjustLoyalty               - POST /loyalty/adjust (admin only)
//   parseAdjustError            - extract 'insufficient_balance' code from 422 body
// END_MODULE_MAP

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

// START_CONTRACT: listUsers
//   PURPOSE: Fetch paginated user list with optional status filter and search.
//   INPUTS:  params?: ListUsersParams — status='all' omits the param;
//            search is server-side substring match.
//   OUTPUTS: Promise<UserListResponse>
//   SIDE_EFFECTS: GET; 401/403.
//   LINKS:   INV-002, INV-013.
// END_CONTRACT: listUsers
export const listUsers = (
  params?: ListUsersParams,
): Promise<UserListResponse> =>
  json(`/api/v1/admin/users${buildListQuery(params)}`);

// START_CONTRACT: getUser
//   PURPOSE: Fetch user detail including loyalty transaction history and active
//            order count (used by block-confirmation dialog).
//   INPUTS:  userId: string
//   OUTPUTS: Promise<UserDetailResponse>
//   SIDE_EFFECTS: GET.
//   LINKS:   INV-002, INV-013.
// END_CONTRACT: getUser
export const getUser = (userId: string): Promise<UserDetailResponse> =>
  json(`/api/v1/admin/users/${userId}`);

// START_CONTRACT: blockUser
//   PURPOSE: Block a user (admin only). Server cancels active orders as a side
//            effect and reports cancelled_orders_count for UX feedback.
//   INPUTS:  userId: string
//   OUTPUTS: Promise<BlockUserResponse>
//   SIDE_EFFECTS: POST; cascading order cancellations server-side.
//   LINKS:   INV-002, INV-016 (cancellations are state-machine transitions).
// END_CONTRACT: blockUser
export const blockUser = (userId: string): Promise<BlockUserResponse> =>
  post(`/api/v1/admin/users/${userId}/block`);

// START_CONTRACT: unblockUser
//   PURPOSE: Unblock a previously blocked user (admin only).
//   INPUTS:  userId: string
//   OUTPUTS: Promise<UnblockUserResponse>
//   SIDE_EFFECTS: POST.
//   LINKS:   INV-002.
// END_CONTRACT: unblockUser
export const unblockUser = (userId: string): Promise<UnblockUserResponse> =>
  post(`/api/v1/admin/users/${userId}/unblock`);

// START_CONTRACT: adjustLoyalty
//   PURPOSE: Apply a manual loyalty-balance adjustment (admin only). Delta may
//            be negative, but server rejects with insufficient_balance if it
//            would drop the balance below zero.
//   INPUTS:  userId: string, input: LoyaltyAdjustRequest {delta, reason}
//   OUTPUTS: Promise<LoyaltyAdjustResponse>
//   SIDE_EFFECTS: POST; 422 on insufficient_balance or validation.
//   LINKS:   INV-002.
// END_CONTRACT: adjustLoyalty
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
// START_CONTRACT: parseAdjustError
//   PURPOSE: Detect the 'insufficient_balance' marker inside a 422 ApiError so
//            the LoyaltyAdjustForm can render the dedicated localized message.
//            Tolerant: accepts {code} or substring in {detail}.
//   INPUTS:  err: unknown
//   OUTPUTS: 'insufficient_balance' | null
//   SIDE_EFFECTS: none.
// END_CONTRACT: parseAdjustError
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
