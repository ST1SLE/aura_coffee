// Типы зеркалят Pydantic-схемы из services/core-api/src/core_api/schemas/order_history.py
// (admin-orders-api) и schemas/order.py (staff-transitions + cancel).
// Клиент — тонкий, без state-machine: UI решает какую кнопку показать,
// сервер решает легитимность перехода (INV-016).

import { authenticatedFetch, ApiError } from './client';

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

export const listAdminOrders = (
  params?: ListAdminOrdersParams,
): Promise<OrderListResponse> =>
  json(`/api/v1/admin/orders${buildListQuery(params)}`);

export const getAdminOrder = (orderId: string): Promise<OrderResponse> =>
  json(`/api/v1/admin/orders/${orderId}`);

export const updateOrderStatus = (
  orderId: string,
  newStatus: OrderStatus,
): Promise<OrderResponse> =>
  json(`/api/v1/orders/${orderId}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ new_status: newStatus }),
  });

export const cancelAdminOrder = (
  orderId: string,
  reason?: string | null,
): Promise<OrderResponse> =>
  json(`/api/v1/orders/${orderId}/cancel`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason: reason ?? null }),
  });
