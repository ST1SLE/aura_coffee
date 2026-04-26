// Типы зеркалят Pydantic-схемы из services/core-api/src/core_api/schemas/order_history.py
// (admin-orders-api) и schemas/order.py (staff-transitions + cancel).
// Клиент — тонкий, без state-machine: UI решает какую кнопку показать,
// сервер решает легитимность перехода (INV-016).

import { authenticatedFetch, ApiError } from './client';

// START_MODULE_CONTRACT
//   PURPOSE: Typed client for admin-only order endpoints — list/get/transition/cancel.
//   SCOPE:   Wraps /api/v1/admin/orders/* and /api/v1/orders/{id}/{status,cancel};
//            UI decides which button to show, server enforces transition legality.
//   DEPENDS: ./client (authenticatedFetch, ApiError); mirrors core-api Pydantic schemas.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, PDD §6.1 order state machine,
//            INV-002 (admin scope enforced server-side), INV-014 (order_items
//            include menu_item_name snapshot for historical fidelity),
//            INV-016 (state-machine transitions).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   ApiError                  - re-export from ./client
//   OrderStatus               - PDD §6.1 state union
//   OrderType                 - 'pickup' | 'delivery'
//   AdminOrderStatusFilter    - server statuses + 'active' aggregate + 'all'
//   OrderItemResponse         - one line of an order, name snapshot per INV-014
//   OrderResponse             - full order shape returned by GET endpoints
//   OrderListResponse         - paginated list shape
//   ListAdminOrdersParams     - query params for listAdminOrders
//   listAdminOrders           - GET /api/v1/admin/orders
//   getAdminOrder             - GET /api/v1/admin/orders/{id}
//   updateOrderStatus         - PATCH /api/v1/orders/{id}/status (INV-016)
//   cancelAdminOrder          - POST /api/v1/orders/{id}/cancel (INV-016)
// END_MODULE_MAP

export { ApiError };

// ── Enums ────────────────────────────────────────────────────────────────────

export type OrderStatus =
  | 'created'
  | 'paid'
  | 'preparing'
  | 'ready'
  | 'in_delivery'
  | 'completed'
  | 'cancelled';

export type OrderType = 'pickup' | 'delivery';

// UI-шный фильтр: 'active' и конкретный OrderStatus — серверные значения,
// 'all' — клиентский sentinel, означающий "не передавать status=" (будет
// эквивалентен дефолту сервера). В текущем цикле 'all' не используется
// таб-бэкой, но клиент умеет корректно отбросить значение.
export type AdminOrderStatusFilter = OrderStatus | 'active' | 'all';

// ── Response shapes (mirror core_api.schemas.order_history) ──────────────────

export interface OrderItemResponse {
  id: string;
  menu_item_id: number | null;
  menu_item_name_ru: string;
  menu_item_name_en: string;
  size_option_id: number | null;
  size_label: string | null;
  unit_price: number;
  modifiers_snapshot: unknown[];
  quantity: number;
  line_total: number;
}

export interface OrderResponse {
  id: string;
  user_id: string;
  status: OrderStatus;
  type: OrderType;
  subtotal: number;
  discount_amount: number;
  delivery_fee: number;
  total: number;
  created_at: string;
  items: OrderItemResponse[];
}

export interface OrderListResponse {
  orders: OrderResponse[];
  total_count: number;
  page: number;
  per_page: number;
}

// ── Request params ───────────────────────────────────────────────────────────

export interface ListAdminOrdersParams {
  status?: AdminOrderStatusFilter;
  type?: OrderType;
  page?: number;
  per_page?: number;
}

// ── helpers ──────────────────────────────────────────────────────────────────

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await authenticatedFetch(path, init);
  if (res.status === 204) return undefined as unknown as T;
  return res.json() as Promise<T>;
}

function buildListQuery(params: ListAdminOrdersParams | undefined): string {
  if (!params) return '';
  const usp = new URLSearchParams();
  // 'all' — явное "снять фильтр статуса", пропускаем параметр.
  if (params.status && params.status !== 'all') usp.set('status', params.status);
  if (params.type) usp.set('type', params.type);
  if (params.page != null) usp.set('page', String(params.page));
  if (params.per_page != null) usp.set('per_page', String(params.per_page));
  const qs = usp.toString();
  return qs ? `?${qs}` : '';
}

// ── API functions ────────────────────────────────────────────────────────────

// START_CONTRACT: listAdminOrders
//   PURPOSE: Fetch paginated admin order list with optional status/type filter.
//   INPUTS:  params?: ListAdminOrdersParams — status/type/page/per_page; status='all'
//            means omit the param so the server uses its default.
//   OUTPUTS: Promise<OrderListResponse>
//   SIDE_EFFECTS: GET request; throws ApiError on non-2xx (401 → redirect via client.ts).
//   LINKS:   INV-002 (server enforces admin/barista scope), PDD §6.1.
// END_CONTRACT: listAdminOrders
export const listAdminOrders = (
  params?: ListAdminOrdersParams,
): Promise<OrderListResponse> =>
  json(`/api/v1/admin/orders${buildListQuery(params)}`);

// START_CONTRACT: getAdminOrder
//   PURPOSE: Fetch single order by id (used to refresh after a transition).
//   INPUTS:  orderId: string — UUID of the order
//   OUTPUTS: Promise<OrderResponse>
//   SIDE_EFFECTS: GET request; throws ApiError (404 → not found).
//   LINKS:   INV-002, PDD §6.1.
// END_CONTRACT: getAdminOrder
export const getAdminOrder = (orderId: string): Promise<OrderResponse> =>
  json(`/api/v1/admin/orders/${orderId}`);

// START_CONTRACT: updateOrderStatus
//   PURPOSE: Drive the order state machine forward (paid→preparing→ready→completed).
//            Server validates the transition; client only sends the requested next state.
//   INPUTS:  orderId: string, newStatus: OrderStatus
//   OUTPUTS: Promise<OrderResponse> — updated order with new status.
//   SIDE_EFFECTS: PATCH; 409 on illegal transition, 403 on wrong role, 401 on session.
//   LINKS:   INV-016 (state-machine transitions are server-enforced; this is the only
//            client surface that triggers them via Mark Ready / Hand Out / etc).
// END_CONTRACT: updateOrderStatus
export const updateOrderStatus = (
  orderId: string,
  newStatus: OrderStatus,
): Promise<OrderResponse> =>
  json(`/api/v1/orders/${orderId}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ new_status: newStatus }),
  });

// START_CONTRACT: cancelAdminOrder
//   PURPOSE: Force-cancel an order (admin only). Bypasses the linear state machine
//            but is itself a state-machine transition gated server-side.
//   INPUTS:  orderId: string, reason?: string | null — optional cancel reason text.
//   OUTPUTS: Promise<OrderResponse> — order with status='cancelled'.
//   SIDE_EFFECTS: POST; 409 if order is already finalized, 403 if not admin.
//   LINKS:   INV-002 (admin role enforced server-side), INV-016.
// END_CONTRACT: cancelAdminOrder
export const cancelAdminOrder = (
  orderId: string,
  reason?: string | null,
): Promise<OrderResponse> =>
  json(`/api/v1/orders/${orderId}/cancel`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason: reason ?? null }),
  });
